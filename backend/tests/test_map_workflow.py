import pytest
from app.map_workflow import MapScenario, map_simulation

def scenario(**kwargs):
    return MapScenario(source_lat=36.80457, source_lon=-120.01737, speed=2, direction=270, **kwargs)

def test_map_field_is_repeatable_and_downwind():
    result = map_simulation(scenario())
    assert result == map_simulation(scenario())
    grid=result['grid']; n=grid['size']; middle=n//2
    assert grid['values'][middle*n+middle+3] > 0
    assert grid['values'][middle*n+middle-3] == 0
    assert len(grid['values']) == n*n
    assert result['label'] == 'modelled'

def test_calm_invalidates_field_and_changes_id():
    active=scenario()
    calm=map_simulation(active.model_copy(update={'speed':0}))
    assert calm['status']=='calm'
    assert calm['grid'] is None
    assert calm['id'] != map_simulation(active)['id']

def test_outside_california_source_is_rejected():
    with pytest.raises(ValueError):
        map_simulation(MapScenario(source_lat=40,source_lon=-115,speed=2,direction=270))
