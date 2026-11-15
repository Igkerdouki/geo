"""Location-aware chat, evidence packets, PDF and inquiry downloads."""
import asyncio
import re
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from app.gaia import ChatRequest, Context, conversation, build_report, validate_context
from app import workflow_store
from app.gaia_report import render_pdf, inquiry
from app.llm import configured

router=APIRouter(prefix='/gaia')

def check(body):
    try:validate_context(body)
    except ValueError as e:raise HTTPException(422,str(e)) from None

@router.post('/chat')
async def chat(body: ChatRequest):
    check(body)
    if not configured():raise HTTPException(503,'Gaia needs a configured AI provider.')
    try:return await asyncio.wait_for(conversation(body),timeout=180)
    except Exception:raise HTTPException(503,'Gaia could not finish. Please retry; reports can still be generated without AI.') from None

@router.post('/reports')
async def report(body: Context):
    check(body)
    try:return await asyncio.wait_for(build_report(body),timeout=120)
    except Exception:raise HTTPException(503,'Report could not be saved. Retry when evidence sources and history storage are available.') from None

def load(report_id):
    if not re.fullmatch(r'[a-f0-9]{32}',report_id):raise HTTPException(404,'Report not found.')
    try:rows=workflow_store.list_items('gaia_report',report_id)
    except Exception:raise HTTPException(503,'Report storage unavailable.') from None
    if not rows:raise HTTPException(404,'Report not found.')
    return rows[0]

@router.get('/reports/{report_id}')
def get_report(report_id: str):return load(report_id)

@router.get('/reports/{report_id}/pdf')
def pdf(report_id: str):
    return Response(render_pdf(load(report_id)),media_type='application/pdf',headers={'Content-Disposition':f'attachment; filename="askgaia-{report_id}.pdf"','Cache-Control':'no-store'})

@router.get('/reports/{report_id}/inquiry')
def draft(report_id: str):return inquiry(load(report_id))
