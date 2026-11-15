"""Opt-in Neon SQL-over-HTTPS for environments without raw PostgreSQL TCP.

Batch queries execute in one Neon transaction. Only server-held connection URLs
are accepted; this is not an arbitrary SQL endpoint exposed to the browser.
"""
import json
import os
import re
from urllib.parse import urlsplit
import httpx


def enabled():return os.getenv('GEO_NEON_HTTP')=='1'

def parameters(sql,values=()):
    params=[]
    if isinstance(values,dict):
        def replace(match):
            params.append(values[match.group(1)]);return '$'+str(len(params))
        sql=re.sub(r'%\((\w+)\)s',replace,sql)
    else:
        iterator=iter(values)
        def replace(match):
            params.append(next(iterator));return '$'+str(len(params))
        sql=re.sub(r'%s',replace,sql)
    def encode(v):
        if v is None:return None
        if isinstance(v,(list,tuple)):
            return '{'+','.join('NULL' if x is None else json.dumps(str(x)) for x in v)+'}'
        if isinstance(v,dict):return json.dumps(v)
        if isinstance(v,bool):return 'true' if v else 'false'
        return str(v)
    return {'query':sql,'params':[encode(v) for v in params]}

def batch(url,queries):
    host=urlsplit(url).hostname
    if not host or not host.endswith('.neon.tech'):raise ValueError('HTTPS SQL requires a Neon database hostname.')
    response=httpx.post('https://'+host+'/sql',headers={'Neon-Connection-String':url,'Neon-Array-Mode':'true','Neon-Raw-Text-Output':'true'},json={'queries':[parameters(q,p) for q,p in queries]},timeout=35)
    if not response.is_success:raise RuntimeError('Neon HTTPS query unavailable (HTTP '+str(response.status_code)+').')
    results=response.json()['results']
    def value(v,oid):
        if v is None:return None
        if oid in {20,21,23}:return int(v)
        if oid in {700,701,1700}:return float(v)
        if oid==16:return v=='t'
        if oid in {114,3802}:return json.loads(v)
        return v
    return [[tuple(value(v,f['dataTypeID']) for v,f in zip(row,r['fields'])) for row in r.get('rows',[])] for r in results]

class ReadConnection:
    def __init__(self,url):self.url=url;self.rows=[]
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def execute(self,sql,params=()):
        if sql.strip().upper().startswith('SET '):return self
        self.rows=batch(self.url,[("SET LOCAL statement_timeout = '25s'",()),('SET LOCAL search_path = public',()),(sql,params)])[-1]
        return self
    def fetchall(self):return self.rows
    def fetchone(self):return self.rows[0] if self.rows else None
