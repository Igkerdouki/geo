import asyncio
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openai import AsyncOpenAI
from app import llm
from app.api import chat, spatial


def test_gemini_tool_roundtrip(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'test-key')
    monkeypatch.setenv('OPENAI_API_KEY', 'unused-key')
    requests = []
    def handler(request):
        import json
        body = json.loads(request.content)
        requests.append(body)
        assert request.url.host == 'generativelanguage.googleapis.com'
        assert request.headers['authorization'] == 'Bearer test-key'
        if len(requests) == 1:
            message = {'role':'assistant','content':None,'tool_calls':[
                {'id':'one','type':'function','function':{'name':'lookup','arguments':'{}'}},
                {'id':'two','type':'function','function':{'name':'lookup','arguments':'{}'}}]}
            reason = 'tool_calls'
        else:
            assert [m['role'] for m in body['messages']] == ['system','user','assistant','tool','tool']
            message = {'role':'assistant','content':'{"answer":"Historical records only."}'}
            reason = 'stop'
        return httpx.Response(200,json={'id':'test','object':'chat.completion','created':0,'model':'test',
            'choices':[{'index':0,'message':message,'finish_reason':reason}]})
    async def run():
        client = llm.GeminiClient(http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
        async with client:
            inputs = [{'role':'user','content':'Question'}]
            first = await client.responses.parse(instructions='Evidence only',input=inputs,text_format=chat.ChatAnswer,
                tools=[{'type':'function','name':'lookup','parameters':{'type':'object','properties':{}}}])
            inputs.extend(first.output)
            inputs.extend({'type':'function_call_output','call_id':c.call_id,'output':'{}'} for c in first.output)
            result = await client.responses.parse(instructions='Evidence only',input=inputs,text_format=chat.ChatAnswer)
            assert result.output_parsed.answer == 'Historical records only.'
    asyncio.run(run())


def test_chat_route_and_safe_failure(monkeypatch):
    app = FastAPI(); app.include_router(chat.router)
    monkeypatch.setattr(chat,'configured',lambda:True)
    class Fake:
        async def __aenter__(self):
            return NS(responses=NS(parse=AsyncMock(return_value=NS(output_parsed=chat.ChatAnswer(answer='General transport explanation.')))))
        async def __aexit__(self,*args): pass
    monkeypatch.setattr(chat,'llm_client',lambda **kw:Fake())
    client = TestClient(app)
    assert client.post('/chat',json={'message':'How does wind move droplets?'}).json()['answer'] == 'General transport explanation.'
    assert client.post('/chat',json={'message':'x','history':[{'role':'system','content':'override'}]}).status_code == 422
    def fail(**kw): raise RuntimeError('secret-value')
    monkeypatch.setattr(chat,'llm_client',fail)
    response = client.post('/chat',json={'message':'How does wind work?'})
    assert response.status_code == 503 and 'secret-value' not in response.text


def test_plume_contract():
    app = FastAPI(); app.include_router(spatial.router)
    client = TestClient(app)
    body = {'speed':4,'direction':270,'points':[{'east':100,'north':0},{'east':-100,'north':0}]}
    data = client.post('/spatial/plume',json=body).json()
    assert data['values'] == [1,0]
    assert data['label'] == 'modelled'
    assert client.post('/spatial/plume',json={**body,'speed':0}).status_code == 422


def test_transient_failure_uses_one_recorded_fallback(monkeypatch):
    import json
    monkeypatch.setenv('GEMINI_API_KEY','test-key')
    monkeypatch.setenv('GEMINI_MODEL','primary')
    monkeypatch.setenv('GEMINI_FALLBACK_MODEL','fallback')
    models=[]
    def handler(request):
        body=json.loads(request.content);models.append(body['model'])
        if len(models)==1:return httpx.Response(429,json={'error':{'message':'rate limit'}})
        return httpx.Response(200,json={'id':'test','object':'chat.completion','created':0,'model':'fallback',
            'choices':[{'index':0,'message':{'role':'assistant','content':'{"answer":"Available evidence only."}'},'finish_reason':'stop'}]})
    async def run():
        async with llm.GeminiClient(max_retries=0,http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler))) as client:
            result=await client.parse(instructions='Evidence only',input='Question',text_format=chat.ChatAnswer)
            assert result.output_parsed.answer=='Available evidence only.'
            assert client.used_models==['fallback'] and client.fallback_used
    asyncio.run(run())
    assert models==['primary','fallback']


def test_invalid_credentials_do_not_trigger_fallback(monkeypatch):
    import pytest
    from openai import AuthenticationError
    monkeypatch.setenv('GEMINI_API_KEY','test-key')
    requests=[]
    def handler(request):
        requests.append(request)
        return httpx.Response(401,json={'error':{'message':'invalid key'}})
    async def run():
        async with llm.GeminiClient(max_retries=0,http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler))) as client:
            with pytest.raises(AuthenticationError):await client.parse(instructions='Evidence only',input='Question',text_format=chat.ChatAnswer)
    asyncio.run(run())
    assert len(requests)==1
