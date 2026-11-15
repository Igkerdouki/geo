import asyncio
import os
from unittest.mock import AsyncMock
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app import evidence_store as store
from app import investigator as agent
from app import evidence_tools as tools
from app.api import investigations as api


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.delenv('BRIGHTDATA_API_KEY', raising=False)
    monkeypatch.delenv('GEO_PUR_DATABASE', raising=False)
    monkeypatch.setenv('GEO_EVIDENCE_DB', str(tmp_path/'evidence.sqlite3'))
    monkeypatch.setenv('OPENAI_API_KEY', 'test-not-a-real-key')


def example_source():
    return dict(id='s1', url='https://example.gov/notice', title='Test fixture', text='A notice describes an intended application, not a completed application.', sha256='abc', provider='Test fixture', retrieved_at=store.now())


def test_rejects_fabricated_citations():
    analysis=agent.Analysis(summary='Test', findings=[
        agent.Finding(claim='Intent',source_id='s1',quote='A notice describes an intended application',scope='general'),
        agent.Finding(claim='Made up',source_id='s1',quote='Children were exposed at school',scope='school'),
        agent.Finding(claim='Missing source',source_id='fake',quote='A notice describes an intended application',scope='general')], gaps=[])
    checked,rejected=agent.validate_findings(analysis,[example_source()])
    assert len(checked)==1 and rejected==2
    assert checked[0]['source_id']=='s1'


def test_persistence_and_version_diff():
    case=store.create('What evidence is missing?',{'name':'Test school'})
    case['sources']=[example_source()];store.save(case)
    assert store.get(case['id'])['sources'][0]['text']==example_source()['text']
    assert store.recent()[0]['id']==case['id']
    original=example_source();new={**original,'text':'The source changed.','sha256':'def'}
    diff=tools.source_changes(original,new)
    assert diff['changed'] and '+The source changed.' in diff['diff']


@pytest.mark.parametrize('url',['http://example.gov','https://localhost/x','https://example.local','https://user:password@example.gov','https://example.gov:8000'])
def test_reject_private_or_non_https_urls(url):
    with pytest.raises(tools.ToolError):asyncio.run(tools.validate_url(url))


def test_reject_private_dns(monkeypatch):
    async def check():
        loop=asyncio.get_running_loop()
        monkeypatch.setattr(loop,'getaddrinfo',AsyncMock(return_value=[(2,1,6,'',('127.0.0.1',443))]))
        with pytest.raises(tools.ToolError):await tools.validate_url('https://example.gov')
    asyncio.run(check())


def test_missing_brightdata_is_explicit():
    with pytest.raises(tools.ToolError,match='BRIGHTDATA_API_KEY'):
        asyncio.run(tools.search_web('test query'))


def test_provider_failure_preserves_evidence(monkeypatch):
    case=store.create('What is missing?',{'name':'Test'})
    case['sources']=[example_source()];store.save(case)
    monkeypatch.setattr(agent,'collect',AsyncMock())
    monkeypatch.setattr(agent,'analyze',AsyncMock(side_effect=RuntimeError('private API key must not leak')))
    asyncio.run(agent.run(case['id']))
    result=store.get(case['id'])
    assert result['status']=='error' and len(result['sources'])==1
    assert 'private API key' not in str(result['errors'])


def test_followup_refresh_preserves_old_evidence(monkeypatch):
    case=store.create('What changed?',{'name':'Test'})
    case['sources']=[example_source()];store.save(case)
    monkeypatch.setattr(agent,'retrieve_source',AsyncMock(return_value={**example_source(),'id':'new','text':'Updated evidence.','sha256':'def'}))
    monkeypatch.setattr(agent,'analyze',AsyncMock())
    asyncio.run(agent.run(case['id'],refresh_id='s1'))
    result=store.get(case['id'])
    assert result['status']=='complete'
    assert result['sources'][0]['id']=='s1'
    assert result['revisions'][0]['previous_source']['sha256']=='abc'


def test_rest_api_hides_full_text_and_validates_followups():
    app=FastAPI();app.include_router(api.router,prefix='/api')
    case=store.create('What is missing?',{'name':'Test'})
    case.update(sources=[example_source()],status='complete');store.save(case)
    with TestClient(app) as client:
        response=client.get('/api/investigations/'+case['id'])
        assert response.status_code==200
        assert 'text' not in response.json()['sources'][0]
        assert client.post('/api/investigations/'+case['id']+'/followup',json={'gap_id':'missing'}).status_code==404
        assert client.get('/api/investigations/'+case['id']+'/export').headers['content-type']=='application/json'
        assert client.get('/api/investigations/missing').status_code==404


def test_create_and_complete_flow(monkeypatch):
    async def fake_collect(case,query,supplied_urls=None):
        case['sources'].append(example_source())
    async def fake_analyze(case):
        case['summary']='A fixture result, not real environmental evidence.'
        case['findings']=[]
    monkeypatch.setattr(agent,'collect',fake_collect)
    monkeypatch.setattr(agent,'analyze',fake_analyze)
    app=FastAPI();app.include_router(api.router,prefix='/api')
    with TestClient(app) as client:
        r=client.post('/api/investigations',json={'question':'What records are available?', 'place':'Chualar Elementary'})
        assert r.status_code==202
        import time
        for _ in range(20):
            out=client.get('/api/investigations/'+r.json()['id']).json()
            if out['status']=='complete':break
            time.sleep(.01)
        assert out['status']=='complete'
        assert out['place']['county']=='MONTEREY'
        assert len(out['sources'])==1


def test_mcp_tools_registered():
    from app.mcp_server import mcp
    names={t.name for t in asyncio.run(mcp.list_tools())}
    assert {'find_place','read_public_source','discover_public_evidence','explain_finding','check_source_change'}<=names


def test_analysis_runs_and_filters_model_output(monkeypatch):
    from types import SimpleNamespace
    case=store.create('What is known?',{'name':'Test'})
    case['sources']=[example_source()]
    parsed=agent.Analysis(summary='The document describes intent.', findings=[agent.Finding(claim='A notice records intent.',source_id='s1',quote='A notice describes an intended application',scope='general')],gaps=[agent.Gap(question='Was it completed?',search_query='completed application record')])
    class FakeClient:
        async def __aenter__(self):
            return SimpleNamespace(responses=SimpleNamespace(parse=AsyncMock(return_value=SimpleNamespace(output_parsed=parsed))))
        async def __aexit__(self,*args):pass
    monkeypatch.setattr(agent,'AsyncOpenAI',lambda **kwargs:FakeClient())
    asyncio.run(agent.analyze(case))
    assert len(case['findings'])==1 and len(case['gaps'])==1
    assert case['trace'][-1]['tool']=='verify_citations'


def test_source_budget_is_enforced(monkeypatch):
    case=store.create('What is known?',{'name':'Test'})
    case['sources']=[{**example_source(),'id':str(i),'url':f'https://example.gov/{i}'} for i in range(11)]
    monkeypatch.setattr(agent,'retrieve_source',AsyncMock(return_value={**example_source(),'id':'last','url':'https://example.gov/new'}))
    asyncio.run(agent.collect(case,'query',['https://example.gov/a','https://example.gov/b','https://example.gov/c']))
    assert len(case['sources'])==12


def test_source_refresh_with_no_change_keeps_identity(monkeypatch):
    case=store.create('What changed?',{'name':'Test'})
    case['sources']=[example_source()];store.save(case)
    monkeypatch.setattr(agent,'retrieve_source',AsyncMock(return_value=example_source()))
    monkeypatch.setattr(agent,'analyze',AsyncMock())
    asyncio.run(agent.run(case['id'],refresh_id='s1'))
    result=store.get(case['id'])
    assert result['revisions']==[]
    assert result['sources'][0]['last_checked_at']


def test_busy_case_rejects_duplicate_work():
    case=store.create('What is known?',{'name':'Test'})
    api.TASKS[case['id']]=object()
    try:
        app=FastAPI();app.include_router(api.router,prefix='/api')
        with TestClient(app) as client:
            assert client.post('/api/investigations/'+case['id']+'/followup',json={}).status_code==409
    finally:
        api.TASKS.pop(case['id'])


def test_snapshot_history_keeps_old_evidence_and_deduplicates_progress():
    case = store.create('What has changed?', {'name': 'Test'})
    case['sources'] = [example_source()]
    store.save(case)
    version = store.history(case['id'])[0]['version']
    case['trace'].append({'message': 'Progress only'})
    store.save(case)
    assert store.history(case['id'])[0]['version'] == version
    case['sources'][0]['text'] = 'Replaced source text'
    store.save(case)
    assert store.history(case['id'])[0]['version'] == version + 1
    assert store.get_version(case['id'], version)['sources'][0]['text'] == example_source()['text']
    assert store.get(case['id'])['sources'][0]['text'] == 'Replaced source text'
    app = FastAPI(); app.include_router(api.router, prefix='/api')
    with TestClient(app) as client:
        base = f"/api/investigations/{case['id']}/history"
        assert client.get(base).status_code == 200
        assert 'text' not in client.get(f'{base}/{version}').json()['sources'][0]
        assert client.get(f'{base}/999').status_code == 404


def test_cloud_requires_durable_storage(monkeypatch):
    monkeypatch.setenv('VERCEL', '1')
    app = FastAPI(); app.include_router(api.router, prefix='/api')
    with TestClient(app) as client:
        assert client.get('/api/investigations').json() == []
        response = client.post('/api/investigations', json={'question': 'What changed near school?', 'place': 'Test school'})
        assert response.status_code == 503
        assert 'Neon' in response.json()['detail']


def test_cloud_job_is_awaited(monkeypatch):
    monkeypatch.setenv('VERCEL', '1')
    case = store.create('What changed?', {'name': 'Test'})
    async def complete():
        case['status'] = 'complete'
        store.save(case)
    async def check():
        task = asyncio.create_task(complete())
        api.TASKS[case['id']] = task
        try:
            result = await api.finish_cloud_task(case)
            assert result['status'] == 'complete'
        finally:
            api.TASKS.pop(case['id'], None)
    asyncio.run(check())
