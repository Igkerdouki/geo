from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api import farmers, realtime


def test_farmer_auth_requires_configured_secret(monkeypatch):
    monkeypatch.delenv('FARMER_JWT_SECRET',raising=False)
    app=FastAPI();app.include_router(farmers.router);c=TestClient(app)
    assert c.post('/farmers/login',json={'email':'test@example.com','password':'test'}).status_code==503
    first=farmers.hash_password('example');second=farmers.hash_password('example')
    assert first!=second
    assert farmers.password_matches('example',first)
    assert not farmers.password_matches('incorrect',first)


def test_legacy_feed_never_fabricates_spraying():
    app=FastAPI();app.include_router(realtime.router);c=TestClient(app)
    assert c.post('/spray-events/simulate').status_code==410
    assert c.post('/spray-events/report').status_code==410
    assert c.get('/spray-events/sites').json()['sites']==[]
