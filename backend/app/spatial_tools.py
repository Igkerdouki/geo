"""
Spatial tools contributed by Ioanna; registered by the shared AskGaia MCP server.

Tools an AI agent can call to investigate a place in California:
  geocode          place or address -> lat/lon
  pur_records      recorded pesticide use near a point (CDPR PUR, 2014-2024, Neon/PostGIS)
  chemical_profile what a chemical is and how hazardous it is
  wind             hourly wind for a place (forecast or a past date)
  run_plume        modelled drift from a source toward a target (Gaussian plume)
  cite_sources     datasets, versions and known limitations

Run: python -m app.mcp_server (or python mcp_server.py from backend).
"""

import math
import os
from datetime import date, datetime

import httpx
from app.config import BACKEND_ROOT  # loads backend/.env

from app.data.chemicals import CHEMICAL_INFO

UA = {"User-Agent": "askgaia-mcp/0.1 (environmental research tool)"}


def _db():
    import psycopg
    url = os.getenv('PUR_DATABASE_URL') or os.getenv('DATABASE_URL')
    if not url:
        raise ValueError('Configure PUR_DATABASE_URL or DATABASE_URL for spatial PUR tools.')
    from app.neon_http import enabled, ReadConnection
    if enabled(): return ReadConnection(url)
    conn = psycopg.connect(url, autocommit=True, connect_timeout=8)
    conn.execute("SET statement_timeout TO '15s'")
    conn.execute("SET search_path TO public")
    return conn


def geocode(query: str) -> dict:
    """Turn an address or place name in California (e.g. "Alisal High School, Salinas CA")
    into latitude/longitude. Use this first whenever the user names a place."""
    with httpx.Client(timeout=15, headers=UA) as c:
        r = c.get(
            "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress",
            params={"address": query, "benchmark": "Public_AR_Current", "format": "json"},
        )
        matches = r.json().get("result", {}).get("addressMatches", [])
        if matches:
            m = matches[0]
            return {"lat": m["coordinates"]["y"], "lon": m["coordinates"]["x"],
                    "matched": m["matchedAddress"], "source": "US Census Geocoder"}
        r = c.get("https://nominatim.openstreetmap.org/search",
                  params={"q": query, "format": "json", "limit": 1, "countrycodes": "us"})
        hits = r.json()
        if hits:
            h = hits[0]
            return {"lat": float(h["lat"]), "lon": float(h["lon"]),
                    "matched": h["display_name"], "source": "OpenStreetMap Nominatim"}
    return {"error": f"Could not find '{query}'. Try a full street address."}


def pur_records(lat: float, lon: float, radius_km: float = 1.25,
                start_year: int = 2020, end_year: int = 2024, top: int = 10) -> dict:
    """Recorded agricultural pesticide use within radius_km of a point, summed per chemical.
    Data: California Pesticide Use Reports 2014-2024, located to ~1 square-mile sections.
    Radius is a user-selected search area, not an exposure threshold."""
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError('Invalid coordinates.')
    if not 0 < radius_km <= 25 or not 1 <= top <= 100 or not 1900 <= start_year <= end_year <= 2100:
        raise ValueError('Use radius (0,25] km, top 1–100, and an ordered year range.')
    from app.coverage import california_location
    california_location(lat, lon)
    radius_m = radius_km * 1000
    deg = radius_km / 80 + 0.02  # generous bounding box for the index
    with _db() as conn:
        rows = conn.execute(
            """
            WITH pt AS (SELECT ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326) g),
            near AS (
              SELECT DISTINCT s.comtrs FROM plss_sections s, pt
              WHERE s.geom && ST_Expand(pt.g, %(deg)s)
                AND ST_DWithin(s.geom::geography, pt.g::geography, %(r)s))
            SELECT p.chem_code, c.chemname, sum(p.lbs) lbs, sum(p.n_apps) apps,
                   sum(p.acres) acres, count(DISTINCT p.comtrs) sections
            FROM pur_monthly p JOIN near USING (comtrs) JOIN chemicals c USING (chem_code)
            WHERE p.year BETWEEN %(y0)s AND %(y1)s
            GROUP BY 1, 2 ORDER BY lbs DESC
            """,
            {"lat": lat, "lon": lon, "deg": deg, "r": radius_m, "y0": start_year, "y1": end_year},
        ).fetchall()
        months = conn.execute(
            """
            WITH pt AS (SELECT ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326) g),
            near AS (
              SELECT DISTINCT s.comtrs FROM plss_sections s, pt
              WHERE s.geom && ST_Expand(pt.g, %(deg)s)
                AND ST_DWithin(s.geom::geography, pt.g::geography, %(r)s))
            SELECT p.month, sum(p.lbs) FROM pur_monthly p JOIN near USING (comtrs)
            WHERE p.year BETWEEN %(y0)s AND %(y1)s GROUP BY 1 ORDER BY 2 DESC LIMIT 3
            """,
            {"lat": lat, "lon": lon, "deg": deg, "r": radius_m, "y0": start_year, "y1": end_year},
        ).fetchall()
    total = sum(r[2] or 0 for r in rows)
    return {
        "radius_km": radius_km, "years": [start_year, end_year],
        "total_lbs": round(total), "chemicals_found": len(rows),
        "top_chemicals": [
            {"chem_code": r[0], "name": r[1], "lbs": round(r[2] or 0),
             "applications": r[3], "acres_treated": round(r[4] or 0), "sections": r[5]}
            for r in rows[:top]],
        "peak_months": [{"month": datetime(2000, m, 1).strftime("%B"), "lbs": round(l or 0)}
                        for m, l in months],
        "note": "Recorded use, not measured exposure. Locations are ~1 sq mile sections.",
    }


def chemical_profile(chemical: str) -> dict:
    """Look up a pesticide by name (partial match) or CDPR chem_code: hazard class,
    carcinogen status, restrictions. Use after pur_records to explain what was sprayed."""
    with _db() as conn:
        if chemical.isdigit():
            rows = conn.execute("SELECT chem_code, chemname FROM chemicals WHERE chem_code=%s",
                                (int(chemical),)).fetchall()
        else:
            rows = conn.execute("SELECT chem_code, chemname FROM chemicals WHERE chemname ILIKE %s "
                                "ORDER BY length(chemname) LIMIT 5", (f"%{chemical}%",)).fetchall()
    if not rows:
        return {"error": f"No chemical matching '{chemical}'."}
    out = []
    for code, name in rows:
        info = CHEMICAL_INFO.get(code)
        out.append({"chem_code": code, "name": name,
                    **({k: info[k] for k in ("type", "chemical_class", "epa_toxicity_category",
                                             "signal_word", "carcinogen", "restricted_use", "notes")
                        if k in info} if info else {"profile": "No curated hazard profile yet; "
                                                    "check EPA/CDPR label data."})})
    return {"matches": out}


def wind(lat: float, lon: float, day: str = "") -> dict:
    """Hourly wind (speed m/s, direction it blows FROM) for a place.
    day='' gives the next 48 h forecast; day='YYYY-MM-DD' gives that past day."""
    params = {"latitude": lat, "longitude": lon, "hourly": "wind_speed_10m,wind_direction_10m",
              "wind_speed_unit": "ms", "timezone": "America/Los_Angeles"}
    if day and date.fromisoformat(day) < date.today():
        url = "https://archive-api.open-meteo.com/v1/archive"
        params |= {"start_date": day, "end_date": day}
    else:
        url = "https://api.open-meteo.com/v1/forecast"
        params |= {"forecast_days": 2}
    h = httpx.get(url, params=params, timeout=15, headers=UA).json()["hourly"]
    hours = [{"time": t, "speed_ms": s, "from_deg": d}
             for t, s, d in zip(h["time"], h["wind_speed_10m"], h["wind_direction_10m"])
             if s is not None and d is not None]
    if not hours:
        return {"error": "No wind observations returned", "source": "Open-Meteo"}
    day_hours = [x for x in hours if 6 <= int(x["time"][11:13]) <= 18] or hours
    mean_s = sum(x["speed_ms"] for x in day_hours) / len(day_hours)
    vx = sum(math.sin(math.radians(x["from_deg"])) for x in day_hours)
    vy = sum(math.cos(math.radians(x["from_deg"])) for x in day_hours)
    return {"daytime_mean_speed_ms": round(mean_s, 1),
            "daytime_prevailing_from_deg": round(math.degrees(math.atan2(vx, vy)) % 360),
            "hours": hours[::3], "source": "Open-Meteo (ERA5 archive / forecast)"}


# Briggs rural dispersion (sigma_y, sigma_z as functions of downwind distance x in metres)
_SIG = {
    "A": (0.22, lambda x: 0.20 * x),
    "B": (0.16, lambda x: 0.12 * x),
    "C": (0.11, lambda x: 0.08 * x / math.sqrt(1 + 0.0002 * x)),
    "D": (0.08, lambda x: 0.06 * x / math.sqrt(1 + 0.0015 * x)),
    "E": (0.06, lambda x: 0.03 * x / (1 + 0.0003 * x)),
    "F": (0.04, lambda x: 0.016 * x / (1 + 0.0003 * x)),
}


def _ground_conc(x, y, u, cls, h=2.0):
    if x <= 1:
        return 0.0
    ay, sz_f = _SIG[cls]
    sy = ay * x / math.sqrt(1 + 0.0001 * x)
    sz = max(sz_f(x), 0.5)
    return math.exp(-y * y / (2 * sy * sy)) * 2 * math.exp(-h * h / (2 * sz * sz)) / (
        2 * math.pi * u * sy * sz)


def run_plume(source_lat: float, source_lon: float, target_lat: float, target_lon: float,
              wind_from_deg: float, wind_speed_ms: float, stability: str = "D") -> dict:
    """Modelled ground-level drift from a field (source) toward a place (target) using a
    Gaussian plume (Pasquill-Gifford stability A-F, Briggs rural dispersion).
    Returns a RELATIVE index 0-1 (1 = the modeled concentration at 100 m directly downwind)."""
    stability = stability.upper() if stability else "D"
    if stability not in _SIG:
        raise ValueError('Stability must be A, B, C, D, E, or F.')
    if not all(math.isfinite(v) for v in [source_lat, source_lon, target_lat, target_lon, wind_from_deg, wind_speed_ms]) or wind_speed_ms < 0:
        raise ValueError('Coordinates and wind must be finite; speed must be nonnegative.')
    dy = (target_lat - source_lat) * 111_320
    dx = (target_lon - source_lon) * 111_320 * math.cos(math.radians(source_lat))
    to = math.radians((wind_from_deg + 180) % 360)  # direction the wind blows TO
    along = dx * math.sin(to) + dy * math.cos(to)
    cross = -dx * math.cos(to) + dy * math.sin(to)
    u = max(wind_speed_ms, 0.5)
    c = _ground_conc(along, cross, u, stability)
    ref = _ground_conc(100, 0, u, stability)
    idx = min(1.0, c / ref) if ref else 0.0
    level = "not downwind" if along <= 0 or idx < 0.01 else (
        "low" if idx < 0.1 else "moderate" if idx < 0.4 else "high")
    return {"distance_m": round(math.hypot(dx, dy)), "downwind_m": round(along),
            "crosswind_m": round(abs(cross)), "relative_index": round(idx, 3), "level": level,
            "assumptions": ["flat terrain", "2 m release height", "steady wind",
                            f"stability class {stability}"],
            "note": "Modelled scenario, not measured exposure."}


def water_nearby(lat: float, lon: float, radius_km: float = 2.0) -> dict:
    """Water near a place in California and what has been MEASURED in it.
    Returns rivers, streams, irrigation canals and lakes (OpenStreetMap) plus CDPR SURF
    surface-water monitoring sites within radius_km, with pesticide detections (2010-2025)."""
    r = int(radius_km * 1000)
    q = f"""[out:json][timeout:20];
    (way["waterway"~"river|stream|canal|drain|ditch"](around:{r},{lat},{lon});
     way["natural"="water"](around:{r},{lat},{lon});
     relation["natural"="water"](around:{r},{lat},{lon}););
    out tags center 200;"""
    bodies = {}
    try:
        els = httpx.post("https://overpass-api.de/api/interpreter", data={"data": q},
                         timeout=25, headers=UA).json().get("elements", [])
        for e in els:
            t = e.get("tags", {})
            kind = t.get("waterway") or t.get("water") or t.get("natural")
            name = t.get("name") or f"unnamed {kind}"
            c = e.get("center") or {}
            d = (math.hypot((c.get("lat", lat) - lat) * 111_320,
                            (c.get("lon", lon) - lon) * 111_320 * math.cos(math.radians(lat))))
            if name not in bodies or d < bodies[name]["approx_distance_m"]:
                bodies[name] = {"name": name, "type": kind, "approx_distance_m": round(d)}
    except Exception as ex:  # Overpass can be busy; the measured data below still works
        bodies = {"error": {"name": f"water map unavailable: {type(ex).__name__}",
                            "type": "error", "approx_distance_m": 0}}
    with _db() as conn:
        sites = conn.execute(
            """
            SELECT site_code, name, county, samples, detections, last::date,
                   round(ST_Distance(ST_MakePoint(lon, lat)::geography,
                                     ST_MakePoint(%(lon)s, %(lat)s)::geography)) d
            FROM surf_sites
            WHERE ST_DWithin(ST_MakePoint(lon, lat)::geography,
                             ST_MakePoint(%(lon)s, %(lat)s)::geography, %(r)s)
            ORDER BY d LIMIT 8
            """, {"lat": lat, "lon": lon, "r": r}).fetchall()
        out_sites = []
        for code, name, county, n, det, last, d in sites:
            chems = conn.execute(
                "SELECT chemical, n, round(max_ppb::numeric, 3) FROM surf_site_chems "
                "WHERE site_code=%s ORDER BY n DESC LIMIT 5", (code,)).fetchall()
            out_sites.append({"site": name, "distance_m": int(d), "samples": n,
                              "detections": det, "last_sample": str(last),
                              "most_detected": [{"chemical": c, "times": k, "max_ppb": float(m)}
                                                for c, k, m in chems]})
    return {"radius_km": radius_km,
            "water_bodies": sorted(bodies.values(), key=lambda b: b["approx_distance_m"])[:12],
            "monitoring_sites": out_sites,
            "note": "Detections are measured in surface water by CDPR and partner agencies (SURF). "
                    "Surface water is not the same as drinking water."}



def cite_sources() -> dict:
    """Datasets, versions and limitations to attach to any answer built from these tools."""
    return {
        "sources": [
            {"name": "California Pesticide Use Reports (PUR)", "publisher": "CA Dept. of Pesticide Regulation",
             "years": "2014-2024", "url": "https://www.cdpr.ca.gov/docs/pur/purmain.htm"},
            {"name": "PLSS sections", "publisher": "CDPR CalPIP", "version": "2025",
             "url": "https://calpip.cdpr.ca.gov/plssFiles.cfm"},
            {"name": "Surface Water Database (SURF)", "publisher": "CDPR", "years": "2010-2025",
             "url": "https://www.cdpr.ca.gov/environmental-monitoring/surface-water/"},
            {"name": "Water bodies", "publisher": "OpenStreetMap contributors"},
            {"name": "Wind", "publisher": "Open-Meteo (ERA5 reanalysis / forecast)", "url": "https://open-meteo.com"},
            {"name": "Geocoding", "publisher": "US Census Geocoder / OpenStreetMap Nominatim"},
        ],
        "limitations": [
            "PUR locates applications to ~1 square mile, not exact fields.",
            "Recorded use is not measured exposure; health studies are observational.",
            "The plume model is a screening estimate (flat terrain, steady wind), relative not absolute.",
            "Home/garden pesticide use and diet are not captured.",
        ],
    }


