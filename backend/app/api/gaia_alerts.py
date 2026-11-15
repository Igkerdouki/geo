import hmac
import os
import re
from fastapi import APIRouter, Header, HTTPException
from app import gaia_alerts as alerts
from app.gaia import Context
from app.api.gaia import check

router=APIRouter(prefix='/gaia')

def token_value(authorization):
    if not authorization or not re.fullmatch(r'Bearer [a-f0-9]{64}',authorization):raise HTTPException(401,'Watch access token required.')
    return authorization[7:]

@router.post('/watches')
def create_watch(body:Context):
    check(body)
    if os.getenv('VERCEL') and not os.getenv('CRON_SECRET'):
        raise HTTPException(503,'Automatic alerts need the production scheduler configured. Manual checks remain available.')
    try:return alerts.create(body)
    except ValueError as e:raise HTTPException(429,str(e)) from None

@router.get('/watches/{watch_id}')
def get_watch(watch_id:str,authorization:str|None=Header(default=None)):
    result=alerts.read(watch_id,token_value(authorization))
    if not result:raise HTTPException(404,'Watch not found.')
    return result

@router.delete('/watches/{watch_id}')
def stop_watch(watch_id:str,authorization:str|None=Header(default=None)):
    if not alerts.disable(watch_id,token_value(authorization)):raise HTTPException(404,'Watch not found.')
    return {'enabled':False}

@router.get('/alerts/check')
async def scheduled_check(authorization:str|None=Header(default=None)):
    secret=os.getenv('CRON_SECRET')
    if not secret or not hmac.compare_digest(authorization or '',f'Bearer {secret}'):
        raise HTTPException(401,'Scheduler authorization required.')
    return {'checked':await alerts.check_due()}
