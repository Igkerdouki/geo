"""Section-level pesticide data for the 3D map (CDPR PUR summarised in Neon/PostGIS)."""
from fastapi import APIRouter, HTTPException, Query

from app.spatial_tools import _db

router = APIRouter()

FUMIGANTS = (136, 385, 573, 616, 970)  # chloropicrin, methyl bromide, 1,3-D, metam-sodium, metam-potassium


@router.get("/spatial/sections")
def sections_near(lat: float = Query(..., ge=32, le=42.5), lon: float = Query(..., ge=-125, le=-114),
                  radius_km: float = Query(4.0, gt=0, le=15),
                  start_year: int = Query(2020, ge=2014, le=2024), end_year: int = Query(2024, ge=2014, le=2024),
                  limit: int = Query(60, ge=1, le=200)):
    """Treated square-mile sections around a point: pounds applied, fumigant pounds, top chemical."""
    if start_year > end_year:
        raise HTTPException(400, "start_year must be <= end_year")
    deg = radius_km / 80 + 0.02
    with _db() as conn:
        rows = conn.execute(
            """
            WITH pt AS (SELECT ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326) g),
            near AS (
              SELECT DISTINCT ON (s.comtrs) s.comtrs, s.lat, s.lon
              FROM plss_sections s, pt
              WHERE s.geom && ST_Expand(pt.g, %(deg)s)
                AND ST_DWithin(s.geom::geography, pt.g::geography, %(r)s)),
            used AS (
              SELECT p.comtrs, p.chem_code, sum(p.lbs) lbs
              FROM pur_monthly p JOIN near USING (comtrs)
              WHERE p.year BETWEEN %(y0)s AND %(y1)s
              GROUP BY 1, 2),
            agg AS (
              SELECT comtrs, sum(lbs) lbs,
                     coalesce(sum(lbs) FILTER (WHERE chem_code = ANY(%(fum)s)), 0) fum
              FROM used GROUP BY 1),
            top AS (
              SELECT DISTINCT ON (u.comtrs) u.comtrs, c.chemname
              FROM used u JOIN chemicals c USING (chem_code)
              ORDER BY u.comtrs, u.lbs DESC)
            SELECT n.comtrs, n.lat, n.lon, a.lbs, a.fum, t.chemname
            FROM near n JOIN agg a USING (comtrs) LEFT JOIN top t USING (comtrs)
            ORDER BY a.lbs DESC LIMIT %(lim)s
            """,
            {"lat": lat, "lon": lon, "deg": deg, "r": radius_km * 1000, "y0": start_year, "y1": end_year,
             "fum": list(FUMIGANTS), "lim": limit},
        ).fetchall()
    return {
        "years": [start_year, end_year], "radius_km": radius_km,
        "sections": [{"comtrs": c, "lat": la, "lon": lo, "lbs": round(l or 0), "fumigant_lbs": round(f or 0),
                      "top_chemical": ch} for c, la, lo, l, f, ch in rows],
        "source": "CDPR Pesticide Use Reports, summarised by PLSS section",
        "note": "Recorded use located to ~1 square mile; not measured exposure.",
    }
