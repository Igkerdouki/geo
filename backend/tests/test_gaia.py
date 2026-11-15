import asyncio,json
from io import BytesIO
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pypdf import PdfReader
from app import gaia
from app.api.gaia import router


def context(**kw):return gaia.Context(location={'name':'Biola School','lat':36.80457,'lon':-120.01737},**kw)

def test_bound_location_and_years():
    b=context(start_year=2021,end_year=2023)
    assert gaia.bound('pur_records',{'lat':0,'start_year':1990},b)==dict(lat=36.80457,lon=-120.01737,radius_km=4,start_year=2021,end_year=2023)
    with pytest.raises(ValueError):gaia.bound('read_public_source',{},b)
    with pytest.raises(ValueError):gaia.validate_context(context(start_year=2024,end_year=2020))

def test_chat_tools_and_citations():
    bridge=NS(schemas=lambda names:[],call=AsyncMock(return_value={'total_lbs':100}))
    async def parse(**kw):
        if len(kw['input'])==1:return NS(output=[NS(type='function_call',name='pur_records',arguments='{"lat":0}',call_id='one')])
        record=json.loads(kw['input'][-1]['output'])
        return NS(output=[],output_parsed=gaia.Answer(introduction='Records',claims=[gaia.Claim(text='100 lb recorded.',label='observed',evidence_ids=[record['id']]),gaia.Claim(text='Unsupported',label='observed',evidence_ids=['fake'])]))
    r=asyncio.run(gaia.conversation(gaia.ChatRequest(**context().model_dump(),message='What was recorded?'),bridge,NS(responses=NS(parse=parse))))
    assert len(r['answer']['claims'])==1
    assert bridge.call.call_args.args[1]['lat']==36.80457
    assert r['actions'][0]['location']['lat']==36.80457

def test_followup_does_not_require_tool_or_save_health_history():
    bridge=NS(schemas=lambda names:[],call=AsyncMock())
    answer=gaia.Answer(introduction='Records cannot diagnose allergies.',follow_up_questions=['When did symptoms start?','Where do they occur?'])
    client=NS(responses=NS(parse=AsyncMock(return_value=NS(output=[],output_parsed=answer))))
    r=asyncio.run(gaia.conversation(gaia.ChatRequest(**context().model_dump(),message='I have allergies.'),bridge,client))
    assert len(r['answer']['follow_up_questions'])==2
    assert 'message' not in r['context'] and 'history' not in r['context']
    bridge.call.assert_not_awaited()

def test_report_snapshot_pdf_inquiry_and_geo_gate(monkeypatch,tmp_path):
    monkeypatch.delenv('DATABASE_URL',raising=False);monkeypatch.setenv('GEO_EVIDENCE_DB',str(tmp_path/'reports.db'))
    async def call(name,args):
        if name=='pur_records':return {'total_lbs':123,'chemicals_found':0,'top_chemicals':[]}
        if name=='environmental_trends':return {'years':[{'year':2020,'reported_lbs':123,'rows':5}],'scope':'Not exposure','missing_years':[2021]}
        if name=='nearby_schools':raise RuntimeError('offline')
        return {'from_deg':90,'speed_ms':2,'valid_at_utc':'2026-11-15T15:00'}
    r=asyncio.run(gaia.build_report(context(),NS(call=call)));assert r['status']=='partial'
    app=FastAPI();app.include_router(router,prefix='/api');c=TestClient(app);base='/api/gaia/reports/'+r['id']
    assert c.get(base).json()['evidence']==r['evidence']
    pdf=c.get(base+'/pdf');assert pdf.status_code==200
    text=' '.join(p.extract_text() for p in PdfReader(BytesIO(pdf.content)).pages)
    assert '123' in text and r['id'] in text and 'Unavailable' in text
    assert 'Biola School' in c.get(base+'/inquiry').json()['body']
    assert c.get('/api/gaia/reports/invalid/pdf').status_code==404
    assert c.post('/api/gaia/reports',json={**context().model_dump(),'location':{'name':'Vegas','lat':36.17,'lon':-115.14}}).status_code==422
