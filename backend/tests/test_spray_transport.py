from datetime import datetime, timezone
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.spray_transport import SprayScenario, simulate_spray
from app.api.agent_workflows import router


def scenario(**updates):
    data = dict(source_lat=36.7378, source_lon=-119.7871,
        start_at='2026-11-15T04:00:00Z', event_source='Demo input',
        location_uncertainty_m=50, duration_minutes=1, horizon_minutes=10,
        ingredients=[dict(name='Tracer A', applied_kg=10, airborne_fraction=0.1,
                          assumption_source='Hypothetical parameters')],
        wind=[dict(minute=0, speed_ms=2, from_deg=0)])
    data.update(updates)
    return data


def test_transport_direction_duration_and_mass_conservation():
    result=simulate_spray(SprayScenario(**scenario()))
    last=result['snapshots'][-1]
    point=last['parcels']['features'][0]['geometry']['coordinates']
    assert point[0] == pytest.approx(-119.7871)
    assert (36.7378-point[1])*111320 == pytest.approx(2*60*9.5)
    budget=last['mass_balance'][0]
    assert budget['airborne_kg'] == pytest.approx(1)
    assert budget['deposited_kg'] == budget['degraded_kg'] == 0
    assert len(last['parcels']['features']) == 1


def test_wind_turn_and_component_removal():
    ingredients=scenario()['ingredients']
    ingredients += [dict(name='Tracer B', applied_kg=10, airborne_fraction=0.1,
        airborne_half_life_minutes=5, deposition_half_life_minutes=5,
        assumption_source='Test assumption')]
    result=simulate_spray(SprayScenario(**scenario(ingredients=ingredients, wind=[
        dict(minute=0,speed_ms=2,from_deg=0),dict(minute=5,speed_ms=2,from_deg=270)])))
    last=result['snapshots'][-1]
    assert last['parcels']['features'][0]['geometry']['coordinates'][0] > -119.7871
    a,b=last['mass_balance']
    assert b['airborne_kg'] < a['airborne_kg']
    assert b['degraded_kg'] == pytest.approx(b['deposited_kg'])
    assert b['airborne_kg']+b['deposited_kg']+b['degraded_kg'] == pytest.approx(b['released_airborne_kg'])


def test_forecast_time_alignment_and_missing_coverage(monkeypatch):
    monkeypatch.setattr('app.spray_transport.wind_conditions', lambda *args: {
        'hours':[dict(time_utc='2026-11-15T04:00',speed_ms=2,from_deg=90)],
        'source':'mock forecast'})
    result=simulate_spray(SprayScenario(**scenario(wind=None)))
    assert result['snapshots'][-1]['parcels']['features'][0]['geometry']['coordinates'][0] < -119.7871
    with pytest.raises(ValueError, match='does not cover'):
        simulate_spray(SprayScenario(**scenario(wind=None,start_at='2020-01-01T00:00:00Z')))


def test_api_validation_and_no_synthetic_fallback(monkeypatch):
    app=FastAPI(); app.include_router(router)
    with TestClient(app) as client:
        assert client.post('/workflows/simulate-spray',json=scenario()).status_code==200
        for updates in [dict(start_at='2026-11-15T04:00:00'),
                        dict(duration_minutes=11), dict(source_lat=40,source_lon=-74),
                        dict(wind=[dict(minute=1,speed_ms=2,from_deg=90)]),
                        dict(wind=[dict(minute=0,speed_ms=-2,from_deg=90)])]:
            assert client.post('/workflows/simulate-spray',json=scenario(**updates)).status_code==422
        def fail(*args): raise RuntimeError('provider offline')
        monkeypatch.setattr('app.spray_transport.wind_conditions',fail)
        assert client.post('/workflows/simulate-spray',json=scenario(wind=None)).status_code==503
