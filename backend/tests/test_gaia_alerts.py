import asyncio
import time
from unittest.mock import AsyncMock
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app import gaia_alerts as a
from app.gaia import Context
from app.api.gaia_alerts import router

@pytest.fixture
def db(monkeypatch,tmp_path):
    monkeypatch.delenv('DATABASE_URL',raising=False)
    monkeypatch.setenv('GEO_EVIDENCE_DB',str(tmp_path/'alerts.db'))

def context():return Context(location={'name':'Biola','lat':36.80457,'lon':-120.01737})
def report(lbs=10,speed=2,direction=350):return {'id':'a'*32,'evidence':[{'tool':'pur_records','status':'complete','result':{'total_lbs':lbs,'chemicals_found':2}},{'tool':'wind_conditions','status':'complete','result':{'speed_ms':speed,'from_deg':direction}}]}

def test_thresholds_wrap_and_missing():
    assert not a.changes(a.snapshot(report()),a.snapshot(report(direction=10)))
    assert len(a.changes(a.snapshot(report()),a.snapshot(report(lbs=20,speed=5))))==2
    assert not a.changes(a.snapshot(report()),{})

def test_auth_and_stop(db):
    app=FastAPI();app.include_router(router);c=TestClient(app)
    w=c.post('/gaia/watches',json=context().model_dump()).json();url='/gaia/watches/'+w['id']
    assert c.get(url).status_code==401
    assert c.get(url,headers={'Authorization':'Bearer '+'0'*64}).status_code==404
    h={'Authorization':'Bearer '+w['token']}
    assert c.get(url,headers=h).json()['enabled']
    assert c.delete(url,headers=h).status_code==200
    assert not c.get(url,headers=h).json()['enabled']
    assert c.get('/gaia/alerts/check').status_code==401

def test_durable_checks_and_preserved_baseline(db,monkeypatch):
    w=a.create(context());build=AsyncMock(return_value=report());monkeypatch.setattr(a,'build_report',build)
    assert asyncio.run(a.check_due())==1
    assert asyncio.run(a.check_due())==0
    state=a.read(w['id'],w['token']);assert len(state['alerts'])==1
    a.query('UPDATE geo_gaia_watches SET due=%s WHERE id=%s',(time.time()-1,w['id']))
    build.return_value=report(lbs=20,speed=5)
    asyncio.run(a.check_due());state=a.read(w['id'],w['token']);assert len(state['alerts'])==3
    a.query('UPDATE geo_gaia_watches SET due=%s WHERE id=%s',(time.time()-1,w['id']))
    build.side_effect=RuntimeError('offline');asyncio.run(a.check_due())
    state=a.read(w['id'],w['token']);assert state['baseline']['records']['reported_lbs']==20
    assert state['status']=='unavailable'
    a.disable(w['id'],w['token']);assert asyncio.run(a.check_due())==0
