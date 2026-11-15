"""Durable hourly watches. Lease claims prevent duplicate checks across workers."""
import asyncio
import hashlib
import json
import logging
import math
import os
import secrets
import time
from app import neon_http
from app.evidence_store import connection
from app.gaia import Context, build_report

SCHEMA='''CREATE TABLE IF NOT EXISTS geo_gaia_watches (
 id TEXT PRIMARY KEY, secret_hash TEXT NOT NULL, enabled INTEGER NOT NULL,
 due DOUBLE PRECISION NOT NULL, lease TEXT NOT NULL, payload TEXT NOT NULL)'''
INTERVAL=86400 if os.getenv('VERCEL') else 3600

def query(sql,params=()):
    if neon_http.enabled() and os.getenv('DATABASE_URL'):
        return neon_http.batch(os.environ['DATABASE_URL'],[(SCHEMA,()),(sql,params)])[-1]
    with connection() as (conn,p):
        cur=conn.cursor();cur.execute(SCHEMA);cur.execute(sql.replace('%s',p),params)
        return cur.fetchall() if cur.description else []

def create(context):
    token=secrets.token_hex(32);wid=secrets.token_hex(16)
    data={'id':wid,'context':context.model_dump(exclude={'scenario'}),'alerts':[],'baseline':{},'status':'pending','checked_at':None,'report_id':None}
    inserted=query('INSERT INTO geo_gaia_watches SELECT %s,%s,1,%s,%s,%s WHERE (SELECT COUNT(*) FROM geo_gaia_watches WHERE enabled=1)<20 RETURNING id',(wid,hashlib.sha256(token.encode()).hexdigest(),time.time(),' ',json.dumps(data)))
    if not inserted:raise ValueError('The automatic monitoring beta is at capacity (20 active watches). Manual checks remain available.')
    return {**data,'token':token,'enabled':True,'interval_seconds':INTERVAL}

def read(wid,token):
    rows=query('SELECT enabled,due,payload FROM geo_gaia_watches WHERE id=%s AND secret_hash=%s',(wid,hashlib.sha256(token.encode()).hexdigest()))
    if not rows:return None
    enabled,due,payload=rows[0]
    return {**json.loads(payload),'enabled':bool(enabled),'next_check_at':due,'interval_seconds':INTERVAL}

def disable(wid,token):
    return bool(query('UPDATE geo_gaia_watches SET enabled=0 WHERE id=%s AND secret_hash=%s RETURNING id',(wid,hashlib.sha256(token.encode()).hexdigest())))

def snapshot(report):
    out={}
    for e in report['evidence']:
        if e['status']!='complete':continue
        r=e['result']
        if e['tool']=='pur_records':out['records']={'reported_lbs':r.get('total_lbs'),'chemicals':r.get('chemicals_found')}
        if e['tool']=='wind_conditions':
            speed=r.get('speed_ms');direction=r.get('from_deg')
            if isinstance(speed,(float,int)) and isinstance(direction,(float,int)) and math.isfinite(speed) and math.isfinite(direction):out['weather']={'speed':speed,'direction':direction%360}
    return out

def changes(previous,current):
    messages=[]
    if 'records' in previous and 'records' in current and previous['records']!=current['records']:
        messages.append(f"Reported-use summary changed: {previous['records']['reported_lbs']} → {current['records']['reported_lbs']} lb; {previous['records']['chemicals']} → {current['records']['chemicals']} chemicals. Historical records, not current spraying.")
    if 'weather' in previous and 'weather' in current:
        a,b=previous['weather'],current['weather'];angle=abs((b['direction']-a['direction']+180)%360-180)
        if abs(a['speed']-b['speed'])>=2 or (min(a['speed'],b['speed'])>=1 and angle>=45):
            messages.append(f"Weather-model wind changed from {a['speed']:.1f} m/s, {a['direction']:.0f}° to {b['speed']:.1f} m/s, {b['direction']:.0f}°. Not an exposure or spraying alert.")
    return messages

async def check_due(limit=20):
    now=time.time()
    rows=await asyncio.to_thread(query,'SELECT id FROM geo_gaia_watches WHERE enabled=1 AND due<=%s ORDER BY due LIMIT %s',(now,limit))
    semaphore=asyncio.Semaphore(10)
    async def process(wid):
        async with semaphore:return await check_one(wid,now)
    return sum(await asyncio.gather(*(process(wid) for (wid,) in rows)))

async def check_one(wid,now):
    lease=secrets.token_hex(16)
    claimed=await asyncio.to_thread(query,'UPDATE geo_gaia_watches SET due=%s,lease=%s WHERE id=%s AND enabled=1 AND due<=%s RETURNING payload',(time.time()+300,lease,wid,now))
    if not claimed:return 0
    data=json.loads(claimed[0][0]);old_status=data['status'];messages=[];report=None
    try:
        report=await asyncio.wait_for(build_report(Context(**data['context'])),120)
        current=snapshot(report);messages=changes(data['baseline'],current)
        status='complete' if all(k in current for k in ('records','weather')) else 'partial'
        if not data['checked_at'] and current:messages.insert(0,'Monitoring started. Initial evidence baseline saved.')
        if status=='partial' and old_status!='partial':messages.append('Some monitored sources are unavailable. Previous values are preserved; missing data is not zero.')
        if status=='complete' and old_status in ('partial','unavailable'):messages.append('Monitored evidence sources are available again.')
        data['baseline'].update(current);data['report_id']=report['id'];data['status']=status
    except asyncio.CancelledError:raise
    except Exception:
        data['status']='unavailable'
        if old_status!='unavailable':messages=['Automatic check could not finish. Previous evidence is preserved; the next check will retry.']
    checked=time.time();data['checked_at']=checked
    for message in messages:
        data['alerts'].insert(0,{'id':secrets.token_hex(12),'created_at':checked,'message':message,'report_id':report['id'] if report else None})
    data['alerts']=data['alerts'][:50]
    await asyncio.to_thread(query,'UPDATE geo_gaia_watches SET payload=%s,due=%s WHERE id=%s AND lease=%s',(json.dumps(data),((int(checked//86400)+1)*86400 if os.getenv('VERCEL') else checked+INTERVAL),wid,lease))
    return 1

async def scheduler():
    while True:
        try:await check_due()
        except asyncio.CancelledError:raise
        except Exception:logging.getLogger(__name__).warning('Gaia watch scheduler could not access storage; retrying.')
        await asyncio.sleep(30)
