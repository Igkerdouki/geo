import asyncio
from unittest.mock import MagicMock

from app import database
from app.evidence_tools import county_records


def test_neon_monthly_records_keep_aggregate_semantics(monkeypatch):
    conn = MagicMock()
    cur = conn.cursor.return_value.__enter__.return_value
    cur.fetchone.side_effect = [
        {'monthly': True},
        {'records': 85315, 'pounds': 8392766.0, 'application_count': 477252},
    ]
    monkeypatch.setattr(database, 'get_pur_connection', lambda: conn)
    result = asyncio.run(county_records('Monterey County', 2023))
    sql, params = cur.execute.call_args.args
    assert 'public.pur_monthly' in sql
    assert params == ('27', 2023)
    assert result['records'] == 85315
    assert result['application_count'] == 477252
    assert result['granularity'] == 'Monthly section/chemical aggregates'
    assert 'not individual spray events' in result['scope']
    conn.close.assert_called_once()


def test_empty_year_does_not_claim_zero_pesticide_use(monkeypatch):
    conn = MagicMock()
    cur = conn.cursor.return_value.__enter__.return_value
    cur.fetchone.side_effect = [
        {'monthly': True},
        {'records': 0, 'pounds': None, 'application_count': None},
    ]
    monkeypatch.setattr(database, 'get_pur_connection', lambda: conn)
    result = asyncio.run(county_records('Monterey', 2026))
    assert result['records'] == 0
    assert result['pounds'] is None
    assert result['application_count'] is None


def test_original_sprays_database_remains_supported(monkeypatch):
    conn = MagicMock()
    cur = conn.cursor.return_value.__enter__.return_value
    cur.fetchone.side_effect = [{'monthly': False}, {'records': 2, 'pounds': 4}]
    monkeypatch.setattr(database, 'get_pur_connection', lambda: conn)
    result = asyncio.run(county_records('Monterey', 2023))
    assert 'FROM sprays' in cur.execute.call_args.args[0]
    assert result['table'] == 'sprays'
    assert result['application_count'] is None
