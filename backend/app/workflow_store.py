"""Durable workflow/event records, using the configured Neon or local store."""
import json
import os
from app.neon_http import enabled, batch
from datetime import datetime, timezone
from app.evidence_store import connection


def save(kind, record):
    record = {**record, 'updated_at': datetime.now(timezone.utc).isoformat()}
    if enabled() and os.getenv('DATABASE_URL'):
        batch(os.environ['DATABASE_URL'],[(SCHEMA,()),('INSERT INTO geo_work_items VALUES (%s,%s,%s,%s) ON CONFLICT(kind,id) DO UPDATE SET updated_at=excluded.updated_at,payload=excluded.payload',(kind,record['id'],record['updated_at'],json.dumps(record)))])
        return record
    with connection() as (conn, p):
        cur=conn.cursor()
        cur.execute('CREATE TABLE IF NOT EXISTS geo_work_items (kind TEXT NOT NULL, id TEXT NOT NULL, updated_at TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(kind,id))')
        cur.execute(f'INSERT INTO geo_work_items VALUES ({p},{p},{p},{p}) ON CONFLICT(kind,id) DO UPDATE SET updated_at=excluded.updated_at,payload=excluded.payload',
                    (kind,record['id'],record['updated_at'],json.dumps(record)))
    return record


SCHEMA='CREATE TABLE IF NOT EXISTS geo_work_items (kind TEXT NOT NULL, id TEXT NOT NULL, updated_at TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(kind,id))'

def list_items(kind, item_id=None):
    if enabled() and os.getenv('DATABASE_URL'):
        where='kind=%s' + (' AND id=%s' if item_id else '')
        rows=batch(os.environ['DATABASE_URL'],[(SCHEMA,()),(f'SELECT payload FROM geo_work_items WHERE {where} ORDER BY updated_at DESC LIMIT 100',(kind,item_id) if item_id else (kind,))])[-1]
        return [json.loads(r[0]) for r in rows]
    with connection() as (conn,p):
        cur=conn.cursor()
        cur.execute('CREATE TABLE IF NOT EXISTS geo_work_items (kind TEXT NOT NULL, id TEXT NOT NULL, updated_at TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(kind,id))')
        where=f'kind={p}' + (f' AND id={p}' if item_id else '')
        cur.execute(f'SELECT payload FROM geo_work_items WHERE {where} ORDER BY updated_at DESC LIMIT 100',
                    (kind,item_id) if item_id else (kind,))
        return [json.loads(row[0]) for row in cur.fetchall()]
