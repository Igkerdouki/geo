"""Versioned investigation snapshots. Neon/Postgres when configured; SQLite locally."""
import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4
from app.config import BACKEND_ROOT


def now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connection():
    url = os.getenv('DATABASE_URL')
    if url:
        import psycopg2
        conn = psycopg2.connect(url, connect_timeout=8)
    else:
        directory = BACKEND_ROOT / 'data'
        directory.mkdir(exist_ok=True)
        conn = sqlite3.connect(os.getenv('GEO_EVIDENCE_DB', str(directory / 'evidence.sqlite3')), timeout=10)
    try:
        yield conn, '%s' if url else '?'
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def schema(cur):
    cur.execute('CREATE TABLE IF NOT EXISTS geo_cases (id TEXT PRIMARY KEY, updated_at TEXT NOT NULL, payload TEXT NOT NULL)')
    cur.execute("""CREATE TABLE IF NOT EXISTS geo_case_versions (
        case_id TEXT NOT NULL REFERENCES geo_cases(id),
        version INTEGER NOT NULL, saved_at TEXT NOT NULL,
        fingerprint TEXT NOT NULL, payload TEXT NOT NULL,
        PRIMARY KEY (case_id, version))""")


def save(case):
    case['updated_at'] = now()
    payload = json.dumps(case)
    # Trace-only progress updates must not create duplicate evidence snapshots.
    evidence = {k: v for k, v in case.items() if k not in ('updated_at', 'trace')}
    fingerprint = hashlib.sha256(json.dumps(evidence, sort_keys=True).encode()).hexdigest()
    with connection() as (conn, p):
        cur = conn.cursor()
        schema(cur)
        # This upsert also serializes concurrent writers to the same Postgres case.
        cur.execute(f'INSERT INTO geo_cases (id, updated_at, payload) VALUES ({p},{p},{p}) ON CONFLICT(id) DO UPDATE SET updated_at=excluded.updated_at, payload=excluded.payload', (case['id'], case['updated_at'], payload))
        cur.execute(f'SELECT version, fingerprint FROM geo_case_versions WHERE case_id={p} ORDER BY version DESC LIMIT 1', (case['id'],))
        previous = cur.fetchone()
        if not previous or previous[1] != fingerprint:
            version = previous[0] + 1 if previous else 1
            cur.execute(f'INSERT INTO geo_case_versions (case_id, version, saved_at, fingerprint, payload) VALUES ({p},{p},{p},{p},{p})',
                        (case['id'], version, case['updated_at'], fingerprint, payload))
    return case


def history(case_id):
    with connection() as (conn, p):
        cur = conn.cursor()
        schema(cur)
        cur.execute(f'SELECT version, saved_at, fingerprint FROM geo_case_versions WHERE case_id={p} ORDER BY version DESC LIMIT 100', (case_id,))
        return [dict(version=r[0], saved_at=r[1], fingerprint=r[2]) for r in cur.fetchall()]


def get_version(case_id, version):
    with connection() as (conn, p):
        cur = conn.cursor()
        schema(cur)
        cur.execute(f'SELECT payload FROM geo_case_versions WHERE case_id={p} AND version={p}', (case_id, version))
        row = cur.fetchone()
        return json.loads(row[0]) if row else None


def get(case_id):
    with connection() as (conn, p):
        cur = conn.cursor()
        cur.execute('CREATE TABLE IF NOT EXISTS geo_cases (id TEXT PRIMARY KEY, updated_at TEXT NOT NULL, payload TEXT NOT NULL)')
        cur.execute(f'SELECT payload FROM geo_cases WHERE id={p}', (case_id,))
        row = cur.fetchone()
        return json.loads(row[0]) if row else None


def recent():
    with connection() as (conn, _):
        cur = conn.cursor()
        cur.execute('CREATE TABLE IF NOT EXISTS geo_cases (id TEXT PRIMARY KEY, updated_at TEXT NOT NULL, payload TEXT NOT NULL)')
        cur.execute('SELECT payload FROM geo_cases ORDER BY updated_at DESC LIMIT 30')
        cases = [json.loads(row[0]) for row in cur.fetchall()]
    return [{k: c.get(k) for k in ('id', 'question', 'place', 'status', 'updated_at')} for c in cases]


def create(question, place):
    return save(dict(id=uuid4().hex, question=question, place=place, created_at=now(), status='queued',
                     sources=[], findings=[], gaps=[], trace=[], revisions=[], summary='', errors=[]))
