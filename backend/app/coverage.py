"""California coverage gate using the project's county polygons, not a bounding box."""
import json
import math
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def counties():
    return json.loads((Path(__file__).parent / 'data/california_counties.geojson').read_text())['features']


def in_ring(lon, lat, ring):
    inside = False
    for a, b in zip(ring, ring[1:] + ring[:1]):
        x1, y1 = a[:2]; x2, y2 = b[:2]
        if (y1 > lat) != (y2 > lat) and lon < (x2-x1)*(lat-y1)/(y2-y1)+x1:
            inside = not inside
    return inside


def california_location(lat: float, lon: float) -> dict:
    """Confirm a point lies in the California dataset's county coverage."""
    if not math.isfinite(lat) or not math.isfinite(lon) or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError('Invalid coordinates.')
    for f in counties():
        g = f['geometry']; polygons = g['coordinates'] if g['type'] == 'MultiPolygon' else [g['coordinates']]
        if any(in_ring(lon, lat, p[0]) and not any(in_ring(lon, lat, h) for h in p[1:]) for p in polygons):
            name = f['properties']['county'].upper()
            # CDPR county codes are alphabetical 01–58, unlike odd-numbered FIPS.
            codes = {n: str(i+1).zfill(2) for i,n in enumerate(sorted(x['properties']['county'].upper() for x in counties()))}
            code = codes.get(name)
            if code is None: raise ValueError('County code not mapped.')
            return {'lat': lat, 'lon': lon, 'state': 'California', 'county': name, 'county_cd': code,
                    'coverage': 'California county polygon; boundary approximation, not parcel geometry'}
    raise ValueError('Outside California dataset coverage, or too close to an approximate coastal boundary.')


def resolve_california(query: str) -> dict:
    """Geocode a place, then enforce California polygon coverage before using PUR data."""
    from app.spatial_tools import geocode
    result = geocode(query)
    if 'error' in result: raise ValueError('Location could not be resolved. Supply a full California address.')
    return {**result, **california_location(result['lat'], result['lon'])}
