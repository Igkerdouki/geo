from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.spatial import router

app = FastAPI()
app.include_router(router, prefix='/api')
client = TestClient(app)


def test_plume_display_uses_downwind_bearing_and_keeps_existing_scale():
    r = client.post('/api/spatial/plume', json={
        'speed': 2, 'direction': 270, 'stability': 'D',
        'points': [{'east':150,'north':0}, {'east':-150,'north':0}, {'east':150,'north':1000}],
    })
    assert r.status_code == 200
    d = r.json()
    assert d['display_values'] == [1, 0, 0]
    assert len(d['values']) == 3
    assert '100 m' in d['normalization']
    assert '150 m' in d['display_normalization']


def test_calm_wind_is_rejected_instead_of_clamped():
    r = client.post('/api/spatial/plume', json={
        'speed':0, 'direction':270, 'points':[{'east':150,'north':0}],
    })
    assert r.status_code == 422
