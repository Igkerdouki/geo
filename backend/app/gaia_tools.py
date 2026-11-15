"""Location-bound MCP tools for Gaia conversations and reports."""
import httpx
import math
from concurrent.futures import ThreadPoolExecutor
from app.coverage import california_location
from app.spatial_tools import _db


def environmental_trends(lat: float, lon: float, radius_km: float = 4, start_year: int = 2020, end_year: int = 2024) -> dict:
    """Annual reported pesticide pounds in intersecting sections. Missing years are not zero."""
    california_location(lat,lon)
    if not 0 < radius_km <= 10 or not 2014 <= start_year <= end_year <= 2024:
        raise ValueError('Use radius (0,10] km and years 2014-2024.')
    with _db() as conn:
        rows=conn.execute('''WITH pt AS (SELECT ST_SetSRID(ST_MakePoint(%s,%s),4326) g), near AS (
          SELECT DISTINCT comtrs FROM plss_sections,pt WHERE ST_DWithin(geom::geography,g::geography,%s))
          SELECT year,SUM(lbs)::double precision,COUNT(*) FROM pur_monthly JOIN near USING(comtrs)
          WHERE year BETWEEN %s AND %s GROUP BY year ORDER BY year''',(lon,lat,radius_km*1000,start_year,end_year)).fetchall()
    return {'years':[{'year':y,'reported_lbs':round(lbs,2),'rows':n} for y,lbs,n in rows],
            'missing_years':[y for y in range(start_year,end_year+1) if y not in {r[0] for r in rows}],
            'scope':'Entire intersecting PLSS sections; reporting completeness unverified. Not exposure or a health trend.'}


def nearby_schools(lat: float, lon: float, radius_km: float = 4) -> dict:
    """OpenStreetMap schools; incomplete community map, not an official school registry."""
    california_location(lat,lon)
    if not 0 < radius_km <= 10: raise ValueError('School radius must be (0,10] km.')
    query=f'[out:json][timeout:20];nwr["amenity"="school"](around:{radius_km*1000},{lat},{lon});out center tags;'
    try:
        r=httpx.post('https://overpass-api.de/api/interpreter',data={'data':query},timeout=8);r.raise_for_status()
    except Exception:
        return tile_schools(lat,lon,radius_km)
    schools=[]
    for e in r.json().get('elements',[]):
        p=e.get('center',e)
        if 'lat' in p and 'lon' in p:
            schools.append({'name':e.get('tags',{}).get('name','Unnamed school'), 'lat':p['lat'],'lon':p['lon'],
                            'url':f"https://www.openstreetmap.org/{e['type']}/{e['id']}"})
    return {'schools':schools[:40],'scope':'OpenStreetMap entries; coverage may be incomplete. No exposure inference.'}


def tile_schools(lat,lon,radius_km):
    """Reduced-radius fallback from actual OSM POIs, never synthetic school pins."""
    import mapbox_vector_tile as mvt
    from app.api.place import OFM
    z=14;n=2**z;radius=min(radius_km,1.5)
    cx=int((lon+180)/360*n);cy=int((1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*n)
    def fetch(tile):
        x,y=tile
        r=httpx.get(OFM.format(z=z,x=x,y=y),timeout=8);r.raise_for_status()
        layer=mvt.decode(r.content,default_options={'y_coord_down':True}).get('poi',{})
        out=[];extent=layer.get('extent',4096)
        for f in layer.get('features',[]):
            if f['properties'].get('class')!='school' or f['geometry']['type']!='Point':continue
            px,py=f['geometry']['coordinates'][:2]
            la=math.degrees(math.atan(math.sinh(math.pi*(1-2*(y+py/extent)/n))))
            lo=(x+px/extent)/n*360-180
            distance=math.hypot((la-lat)*111320,(lo-lon)*111320*math.cos(math.radians(lat)))
            if distance<=radius*1000:out.append({'name':f['properties'].get('name') or 'Unnamed school','lat':la,'lon':lo,'url':f'https://www.openstreetmap.org/#map=17/{la}/{lo}'})
        return out
    with ThreadPoolExecutor(max_workers=6) as pool:
        results=list(pool.map(fetch,[(cx+x,cy+y) for x in [-1,0,1] for y in [-1,0,1]]))
    schools={ (s['name'],round(s['lat'],4),round(s['lon'],4)):s for group in results for s in group}
    return {'schools':list(schools.values()),'coverage_radius_km':radius,'requested_radius_km':radius_km,
        'scope':f'Overpass unavailable. Actual OpenStreetMap/OpenFreeMap POIs within {radius:g} km only; incomplete community map, not an official registry. No exposure inference.'}
