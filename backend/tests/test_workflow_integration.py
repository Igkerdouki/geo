import asyncio
import json
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.agent_workflows import router
from app.api.spray_events import router as events_router
from app.spray_transport import SprayScenario, simulate_spray, settling_speed
from app.environment import observation_values
from app.orchestration import InvestigationRequest, WorkflowPlan, orchestrate, bound_arguments
from app.model_validation import ValidationRequest, validate_measurements
from app import workflow_store


def scenario(**kwargs):
    return SprayScenario(**(dict(source_lat=36.7378,source_lon=-119.7871,start_at='2026-11-15T04:00:00Z',
        event_source='Test assumptions',location_uncertainty_m=20,duration_minutes=1,horizon_minutes=10,
        ingredients=[dict(name='A',applied_kg=1,airborne_fraction=.1,assumption_source='Test')],
        wind=[dict(minute=0,speed_ms=2,from_deg=270,temperature_c=20,humidity_pct=50,rain_mm_hr=1)])|kwargs))


def physics():
    return dict(release_height_m=2,mixing_height_m=20,horizontal_diffusivity_m2_s=2,
        vertical_diffusivity_m2_s=.5,wind_height_exponent=.15,assumption_source='Test')


def test_extended_physics_conserves_mass_and_evaporates():
    req=scenario(physics=physics(),ingredients=[dict(name='A',applied_kg=1,airborne_fraction=.1,
        droplet_diameter_um=30,residual_diameter_um=10,evaporation_um2_s=1,
        rain_scavenging_per_mm=.2,volatilization_half_life_minutes=3,airborne_half_life_minutes=10,assumption_source='Test')])
    result=simulate_spray(req)
    for frame in result['snapshots']:
        b=frame['mass_balance'][0]
        assert b['airborne_kg']+b['degraded_kg']+b['deposited_kg']==pytest.approx(b['released_airborne_kg'])
        assert 0<=b['vapor_kg']<=b['airborne_kg']
    assert 10<=result['snapshots'][-1]['parcels']['features'][0]['properties']['droplet_diameter_um']<30
    assert settling_speed(100,1000,20)>settling_speed(10,1000,20)>0


def test_uncertainty_expands_extent():
    result=simulate_spray(scenario(uncertainty={'start_minutes':30}))
    assert len(result['uncertainty']['members'])==11
    ring=result['uncertainty']['extent']['features'][0]['geometry']['coordinates'][0]
    assert ring[0]==ring[-1] and ring[0][0]<ring[2][0] and ring[0][1]<ring[2][1]
    assert result['uncertainty']['mass_ranges'][0]['airborne_kg_min']==pytest.approx(.1)


def test_observation_units_staleness_and_missing_wind():
    props=dict(windSpeed={'value':36,'unitCode':'wmoUnit:km_h-1'},windDirection={'value':90},timestamp=datetime.now(timezone.utc).isoformat())
    assert observation_values({'properties':props})['speed_ms']==10
    props['timestamp']=(datetime.now(timezone.utc)-timedelta(hours=5)).isoformat()
    with pytest.raises(ValueError,match='stale'): observation_values({'properties':props})
    props['windSpeed']['value']=None
    with pytest.raises(ValueError,match='missing'): observation_values({'properties':props})


def test_measured_samples_must_match_time_ingredient_and_receptor():
    req=scenario(physics=physics(),receptors=[dict(id='R',lat=36.7378,lon=-119.78)])
    body=dict(scenario=req,measurements=[dict(receptor_id='R',ingredient='A',at='2026-11-15T04:10:00Z',
        concentration_ug_m3=1,source='Independent field dataset',sample_kind='instantaneous')],dataset_id='test-only',held_out=True)
    metrics=validate_measurements(ValidationRequest(**body))
    assert metrics['sample_count']==1 and metrics['mae_ug_m3']>=0
    body['measurements'][0]['at']='2026-11-15T04:11:00Z'
    with pytest.raises(ValueError,match='exactly match'):validate_measurements(ValidationRequest(**body))


def test_dynamic_plan_changes_specialist_order(monkeypatch):
    from app import orchestration as module
    from app.coverage import california_location
    monkeypatch.setattr(module,'plan_workflow',AsyncMock(return_value=WorkflowPlan(first='simulation',reason='Weather question',data_task='Records',simulation_task='Weather')))
    seen=[]
    async def agent(role,request,location,context,bridge,evidence,client):
        seen.append(role)
        if role=='location':evidence.append({'id':'location','tool':'resolve_california','status':'complete','result':california_location(36.7378,-119.7871)})
        return module.AgentReport(summary=role,claims=[],limitations=[])
    monkeypatch.setattr(module,'run_agent',agent)
    result=asyncio.run(orchestrate(InvestigationRequest(place='Fresno',question='Where will it go?',dynamic_planning=True),SimpleNamespace(epa_status='test'),object()))
    assert seen==['location','simulation','data','verifier'] and result['plan']['first']=='simulation'
    request=InvestigationRequest(place='Fresno',question='Where will it go?',spray_scenario=scenario())
    assert bound_arguments('simulation','simulate_spray_event',{'scenario':{'source_lat':0}},request,{})['scenario']['source_lat']==36.7378


def test_stream_and_history_round_trip(monkeypatch,tmp_path):
    monkeypatch.delenv('DATABASE_URL',raising=False)
    monkeypatch.setenv('GEO_EVIDENCE_DB',str(tmp_path/'evidence.db'))
    monkeypatch.setenv('OPENAI_API_KEY','test')
    from app.api import agent_workflows
    from app.orchestration import progress
    async def fake(body):
        await progress('agent',agent='location',status='running')
        return {'id':'test-workflow','status':'partial','warnings':[],'agents':{},'evidence':[]}
    monkeypatch.setattr(agent_workflows,'orchestrate',fake)
    app=FastAPI();app.include_router(router)
    with TestClient(app) as c:
        response=c.post('/workflows/investigate/stream',json={'place':'Fresno','question':'What is recorded?'})
        records=[json.loads(line) for line in response.text.splitlines()]
        assert records[0]['type']=='agent' and records[-1]['type']=='result'
        assert records[-1]['result']['saved'] is True
        assert c.get('/workflows/history').json()[0]['id']=='test-workflow'
        assert c.get('/workflows/history/test-workflow').json()['request']['place']=='Fresno'


def test_event_classification_import_and_equipment_auth(monkeypatch,tmp_path):
    monkeypatch.delenv('DATABASE_URL',raising=False)
    monkeypatch.setenv('GEO_EVIDENCE_DB',str(tmp_path/'events.db'))
    monkeypatch.setenv('GEO_INGEST_TOKEN','test-token')
    app=FastAPI();app.include_router(events_router)
    notice=dict(kind='scheduled',source_id='N1',source='SprayDays',source_url='https://spraydays.cdpr.ca.gov/Map/GetMap',
        start_at='2026-11-15T04:00:00Z',lat=36.7378,lon=-119.7871,location_uncertainty_m=1140,ingredients=[{'name':'A'}],status='scheduled')
    with TestClient(app) as c:
        assert c.post('/application-events/spraydays/import',json={'events':[notice|{'status':'started'}]}).status_code==422
        saved=c.post('/application-events/spraydays/import',json={'events':[notice]}).json()['events'][0]
        assert saved['kind']=='scheduled' and '2026-11-19' in saved['latest_start_at']
        report=notice|dict(kind='reported',status='started',source='Equipment')
        assert c.post('/application-events/telemetry',json=report).status_code==401
        r=c.post('/application-events/telemetry',json=report,headers={'Authorization':'Bearer test-token'})
        assert r.status_code==200 and r.json()['authentication']=='authenticated_equipment'
        assert len(c.get('/application-events').json()['events'])==2
        assert len(workflow_store.list_items('event_revision'))==2


def test_compare_requires_identical_scope(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','test')
    app=FastAPI();app.include_router(router)
    with TestClient(app) as c:
        body={'places':[{'place':'Fresno','question':'What is recorded?','radius_km':1},{'place':'Salinas','question':'What is recorded?','radius_km':2}]}
        assert c.post('/workflows/compare',json=body).status_code==422


def test_weather_rain_interval_alignment(monkeypatch):
    from app.simulation import wind_conditions
    payload={'current':{'wind_speed_10m':2,'wind_direction_10m':90,'time':'2026-11-15T04:00'},
        'hourly':{'time':['2026-11-15T04:00','2026-11-15T05:00'],
            'wind_speed_10m':[2,3],'wind_direction_10m':[90,180],
            'temperature_2m':[20,21],'relative_humidity_2m':[40,50],'precipitation':[1,4]}}
    monkeypatch.setattr('app.simulation.httpx.get',lambda *a,**kw:SimpleNamespace(raise_for_status=lambda:None,json=lambda:payload))
    result=wind_conditions(36.7378,-119.7871)
    assert result['hours'][0]['rain_mm_hr']==4
    assert result['hours'][1]['rain_mm_hr'] is None


def test_footprints_are_closed_and_extended_inputs_require_physics():
    from pydantic import ValidationError
    result=simulate_spray(scenario(physics=physics()))
    for frame in result['snapshots']:
        polygon=frame['footprints']['features'][0]
        assert polygon['properties']['kind']=='dispersion_moment_ellipse'
        assert polygon['geometry']['coordinates'][0][0]==polygon['geometry']['coordinates'][0][-1]
    with pytest.raises(ValidationError,match='require explicit physics'):
        scenario(ingredients=[dict(name='A',applied_kg=1,airborne_fraction=.1,assumption_source='Test',droplet_diameter_um=50)])
