import asyncio
import pytest
from app.mcp_server import mcp
from app.spatial_tools import run_plume, pur_records


def test_both_mcp_tool_sets_are_available():
    names = {t.name for t in asyncio.run(mcp.list_tools())}
    assert {'geocode', 'pur_records', 'chemical_profile', 'wind', 'run_plume', 'water_nearby', 'cite_sources',
            'find_place', 'discover_public_evidence', 'read_public_source', 'get_county_records',
            'get_investigation', 'explain_finding', 'check_source_change'} <= names


def test_plume_bearing_and_validation():
    downwind = run_plume(36, -120, 35.999, -120, 0, 2)
    upwind = run_plume(36, -120, 36.001, -120, 0, 2)
    assert downwind['relative_index'] > 0
    assert upwind['relative_index'] == 0
    with pytest.raises(ValueError, match='Stability'):
        run_plume(36, -120, 36.001, -120, 0, 2, 'invalid')


def test_pur_bounds_rejected_before_database_access():
    with pytest.raises(ValueError, match='radius'):
        pur_records(36, -120, radius_km=-1)
