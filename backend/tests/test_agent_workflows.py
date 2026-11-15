import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.coverage import california_location
from app.models.seasonal import fit, predict
from app.simulation import simulate_grid
from app import orchestration as workflow
from app.api.agent_workflows import router


def test_california_polygon_not_bounding_box():
    assert california_location(32.7157,-117.1611)['county_cd']=='37'
    assert california_location(36.6002,-121.8947)['county_cd']=='27'
    for lat,lon in [(36.1699,-115.1398),(40.7128,-74.0060),(float('nan'),-120)]:
        with pytest.raises(ValueError): california_location(lat,lon)


def training_rows():
    return [dict(year=y,month=m,county_cd='27',lbs=10 if y<2023 else 1000) for y in [2021,2022,2023] for m in range(1,13)]


def test_training_has_temporal_holdout_no_leakage():
    model=fit(training_rows())
    assert model['validation']['training_years']==[2021,2022]
    assert model['validation']['heldout_year']==2023
    assert model['validation']['mae_lbs']==pytest.approx(990)
    result=predict(model,'27',6)
    assert result['label']=='modelled' and result['expected_reported_lbs']==340
    assert result['scope'].startswith('California county-month')


def test_missing_months_are_not_zero_and_bad_data_rejected():
    rows=[r for r in training_rows() if r['month']!=7]
    model=fit(rows)
    with pytest.raises(ValueError,match='No observations'): predict(model,'27',7)
    with pytest.raises(ValueError,match='No trained county'): predict(model,'10',1)
    with pytest.raises(ValueError): fit(rows[:2])
    with pytest.raises(ValueError): fit(rows+[rows[0]])


def test_geographic_plume_is_relative_and_calm_wind_is_rejected():
    result=simulate_grid(36.7378,-119.7871,36.7368,-119.7871,wind_speed_ms=2,wind_from_deg=0,cells=5)
    assert result['target']['relative_index']>0
    assert len(result['grid']['features'])==25
    assert all(f['geometry']['coordinates'][0][0]==f['geometry']['coordinates'][0][-1] for f in result['grid']['features'])
    upwind=simulate_grid(36.7378,-119.7871,36.7388,-119.7871,wind_speed_ms=2,wind_from_deg=0,cells=5)
    assert upwind['target']['relative_index']==0
    with pytest.raises(ValueError,match='0.5'): simulate_grid(36.7378,-119.7871,36.7388,-119.7871,wind_speed_ms=0,wind_from_deg=0)
    with pytest.raises(ValueError,match='both'): simulate_grid(36.7378,-119.7871,36.7388,-119.7871,wind_speed_ms=2)


def test_no_fake_weather_on_provider_failure(monkeypatch):
    def fail(*args): raise RuntimeError('provider unavailable')
    monkeypatch.setattr('app.simulation.wind_conditions',fail)
    with pytest.raises(RuntimeError): simulate_grid(36.7378,-119.7871,36.7388,-119.7871)


def test_tool_arguments_cannot_move_the_user_scenario():
    req=workflow.InvestigationRequest(place='Fresno CA',question='What is known?',scenario=workflow.Scenario(source_lat=36.73,source_lon=-119.78))
    loc=california_location(36.7378,-119.7871)
    args=workflow.bound_arguments('simulation','simulate_grid',{'source_lat':40,'target_lon':0},req,loc)
    assert args['source_lat']==36.73 and args['target_lon']==loc['lon']
    assert workflow.bound_arguments('location','resolve_california',{'query':'New York'},req,None)=={'query':req.place}
    req.scenario=None
    with pytest.raises(ValueError): workflow.bound_arguments('simulation','simulate_grid',{},req,loc)


def test_verifier_rejects_fabricated_references_and_observed_weather():
    claims=[workflow.Claim(text='Measured exposure',label='observed',evidence_ids=['weather']),
            workflow.Claim(text='Unsupported',label='observed',evidence_ids=['fake']),
            workflow.Claim(text='Modeled wind',label='modelled',evidence_ids=['weather'])]
    accepted,rejected=workflow.verify_claims(claims,[{'id':'weather','tool':'wind_conditions','status':'complete'}])
    assert len(accepted)==1 and rejected==2


def test_agent_executes_tool_loop_with_bound_arguments():
    report=workflow.AgentReport(summary='California place resolved',claims=[],limitations=[])
    call=SimpleNamespace(type='function_call',name='resolve_california',arguments='{"query":"wrong place"}',call_id='call-1')
    client=SimpleNamespace(responses=SimpleNamespace(parse=AsyncMock(side_effect=[SimpleNamespace(output=[call]),SimpleNamespace(output=[],output_parsed=report)])))
    bridge=SimpleNamespace(epa_status='Not configured',schemas=lambda allowed: [],call=AsyncMock(return_value=california_location(36.7378,-119.7871)))
    req=workflow.InvestigationRequest(place='Fresno CA',question='What is known?')
    evidence=[]
    out=asyncio.run(workflow.run_agent('location',req,None,{},bridge,evidence,client))
    assert out==report and evidence[0]['status']=='complete'
    bridge.call.assert_awaited_once_with('resolve_california',{'query':'Fresno CA'})


def test_orchestrator_runs_all_roles_and_stops_on_bad_location(monkeypatch):
    seen=[]
    async def agent(role,request,location,context,bridge,evidence,client):
        seen.append(role)
        if role=='location': evidence.append({'id':'loc','tool':'resolve_california','status':'complete','result':california_location(36.7378,-119.7871)})
        return workflow.AgentReport(summary=role,claims=[],limitations=[])
    monkeypatch.setattr(workflow,'run_agent',agent)
    req=workflow.InvestigationRequest(place='Fresno CA',question='What is known?')
    result=asyncio.run(workflow.orchestrate(req,SimpleNamespace(epa_status='Not configured'),object()))
    assert seen==['location','data','simulation','verifier'] and result['status']=='complete'
    async def fail(*args): raise ValueError('outside California')
    monkeypatch.setattr(workflow,'run_agent',fail)
    result=asyncio.run(workflow.orchestrate(req,SimpleNamespace(epa_status='Not configured'),object()))
    assert result['status']=='partial' and list(result['agents'])==['location']


def test_api_validation_and_geojson_contract():
    app=FastAPI();app.include_router(router,prefix='/api')
    with TestClient(app) as c:
        assert c.get('/api/workflows/coverage?lat=36.1699&lon=-115.1398').status_code==422
        response=c.post('/api/workflows/simulate',json={'source_lat':36.7378,'source_lon':-119.7871,'target_lat':36.7368,'target_lon':-119.7871,'wind_speed_ms':2,'wind_from_deg':0,'cells':5})
        assert response.status_code==200 and response.json()['grid']['type']=='FeatureCollection'


def test_selected_map_location_survives_location_agent_failure(monkeypatch):
    seen=[]
    async def agent(role,request,location,context,bridge,evidence,client):
        seen.append((role,location['lat'],location['lon']))
        if role=='location': raise RuntimeError('provider unavailable')
        return workflow.AgentReport(summary=role,claims=[],limitations=[])
    monkeypatch.setattr(workflow,'run_agent',agent)
    req=workflow.InvestigationRequest(place='Biola',question='Review map',selected_location={'lat':36.802,'lon':-120.016})
    result=asyncio.run(workflow.orchestrate(req,SimpleNamespace(epa_status='Not configured'),object()))
    assert len(seen)==4 and all(lat==36.802 and lon==-120.016 for _,lat,lon in seen)
    assert result['status']=='partial'
    assert result['evidence'][0]['tool']=='validate_selected_location'
    req.selected_location=workflow.SelectedLocation(lat=36.1699,lon=-115.1398)
    with pytest.raises(ValueError): asyncio.run(workflow.orchestrate(req,SimpleNamespace(epa_status='Not configured'),object()))
    assert len(seen)==4
