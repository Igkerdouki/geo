"""Section-level pesticide data for the 3D map (CDPR PUR summarised in Neon/PostGIS)."""
from fastapi import APIRouter, HTTPException, Query

from app.spatial_tools import _db

router = APIRouter()

FUMIGANTS = (136, 385, 573, 616, 970)  # chloropicrin, methyl bromide, 1,3-D, metam-sodium, metam-potassium


def _outer_ring(gj):
    import json
    g = json.loads(gj) if gj else None
    if not g:
        return []
    poly = g["coordinates"][0] if g["type"] == "MultiPolygon" else g["coordinates"]
    return poly[0]  # [[lon, lat], ...]


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
              SELECT DISTINCT ON (s.comtrs) s.comtrs, s.lat, s.lon, ST_AsGeoJSON(ST_SimplifyPreserveTopology(s.geom, 0.0002), 6) gj
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
            SELECT n.comtrs, n.lat, n.lon, a.lbs, a.fum, t.chemname, n.gj
            FROM near n JOIN agg a USING (comtrs) LEFT JOIN top t USING (comtrs)
            ORDER BY a.lbs DESC LIMIT %(lim)s
            """,
            {"lat": lat, "lon": lon, "deg": deg, "r": radius_km * 1000, "y0": start_year, "y1": end_year,
             "fum": list(FUMIGANTS), "lim": limit},
        ).fetchall()
    return {
        "years": [start_year, end_year], "radius_km": radius_km,
        "sections": [{"comtrs": c, "lat": la, "lon": lo, "lbs": round(l or 0), "fumigant_lbs": round(f or 0),
                      "top_chemical": ch, "ring": _outer_ring(gj)} for c, la, lo, l, f, ch, gj in rows],
        "source": "CDPR Pesticide Use Reports, summarised by PLSS section",
        "note": "Recorded use located to ~1 square mile; not measured exposure.",
    }


_COUNTY_CACHE = {}
# CDPR county codes are the 58 California counties in alphabetical order (01 = Alameda … 58 = Yuba)
COUNTY_NAMES = {f"{i:02d}": n for i, n in enumerate("""Alameda Alpine Amador Butte Calaveras Colusa Contra_Costa Del_Norte El_Dorado Fresno Glenn Humboldt
Imperial Inyo Kern Kings Lake Lassen Los_Angeles Madera Marin Mariposa Mendocino Merced Modoc Mono Monterey Napa Nevada Orange
Placer Plumas Riverside Sacramento San_Benito San_Bernardino San_Diego San_Francisco San_Joaquin San_Luis_Obispo San_Mateo
Santa_Barbara Santa_Clara Santa_Cruz Shasta Sierra Siskiyou Solano Sonoma Stanislaus Sutter Tehama Trinity Tulare Tuolumne
Ventura Yolo Yuba""".split(), start=1)}
COUNTY_NAMES = {k: v.replace("_", " ") for k, v in COUNTY_NAMES.items()}


@router.get("/spatial/counties")
def county_totals(start_year: int = Query(2020, ge=2014, le=2024), end_year: int = Query(2024, ge=2014, le=2024)):
    """Pounds applied per county with a representative point, for the statewide view."""
    key = (start_year, end_year)
    if key in _COUNTY_CACHE:
        return _COUNTY_CACHE[key]
    with _db() as conn:
        conn.execute("SET statement_timeout TO '60s'")
        rows = conn.execute(
            """
            WITH tot AS (
              SELECT left(comtrs, 2) cd, sum(lbs) lbs,
                     coalesce(sum(lbs) FILTER (WHERE chem_code = ANY(%(fum)s)), 0) fum
              FROM pur_monthly WHERE year BETWEEN %(y0)s AND %(y1)s GROUP BY 1),
            sec AS (SELECT comtrs, sum(lbs) lbs FROM pur_monthly WHERE year BETWEEN %(y0)s AND %(y1)s GROUP BY 1),
            pts AS (  -- pound-weighted centre: where the spraying actually happens, not the county's geographic middle
              SELECT left(s.comtrs, 2) cd, sum(p.lat * s.lbs) / nullif(sum(s.lbs), 0) lat, sum(p.lon * s.lbs) / nullif(sum(s.lbs), 0) lon
              FROM sec s JOIN (SELECT DISTINCT ON (comtrs) comtrs, lat, lon FROM plss_sections) p USING (comtrs) GROUP BY 1)
            SELECT t.cd, p.lat, p.lon, t.lbs, t.fum FROM tot t JOIN pts p USING (cd) ORDER BY t.lbs DESC
            """, {"y0": start_year, "y1": end_year, "fum": list(FUMIGANTS)}).fetchall()
    out = {"years": [start_year, end_year],
           "counties": [{"county_cd": c, "name": COUNTY_NAMES.get(c, c), "lat": la, "lon": lo, "lbs": round(l or 0), "fumigant_lbs": round(f or 0)}
                        for c, la, lo, l, f in rows if la is not None],
           "source": "CDPR Pesticide Use Reports"}
    _COUNTY_CACHE[key] = out
    return out


_GRID_CACHE = {}  # cleared on restart


@router.get("/spatial/grid")
def grid(cell_deg: float = Query(0.08, ge=0.03, le=0.5), start_year: int = Query(2020, ge=2014, le=2024),
         end_year: int = Query(2024, ge=2014, le=2024)):
    """Statewide heat grid: pounds applied per ~cell_deg cell, for the California overview."""
    key = (cell_deg, start_year, end_year)
    if key in _GRID_CACHE:
        return _GRID_CACHE[key]
    with _db() as conn:
        conn.execute("SET statement_timeout TO '90s'")
        rows = conn.execute(
            """
            WITH sec AS (SELECT comtrs, sum(lbs) lbs,
                                coalesce(sum(lbs) FILTER (WHERE chem_code = ANY(%(fum)s)), 0) fum
                         FROM pur_monthly WHERE year BETWEEN %(y0)s AND %(y1)s GROUP BY 1),
            pts AS (SELECT DISTINCT ON (comtrs) comtrs, lat, lon FROM plss_sections)
            SELECT floor(p.lat / %(c)s) gy, floor(p.lon / %(c)s) gx, sum(s.lbs), sum(s.fum), left(min(s.comtrs), 2),
                   sum(p.lat * s.lbs) / nullif(sum(s.lbs), 0), sum(p.lon * s.lbs) / nullif(sum(s.lbs), 0)
            FROM sec s JOIN pts p USING (comtrs) GROUP BY 1, 2 HAVING sum(s.lbs) > 1000
            """, {"y0": start_year, "y1": end_year, "c": cell_deg, "fum": list(FUMIGANTS)}).fetchall()
    out = {"cell_deg": cell_deg, "years": [start_year, end_year],
           "cells": [{"lat": round((gy + 0.5) * cell_deg, 4), "lon": round((gx + 0.5) * cell_deg, 4), "lbs": round(l),
                      "fumigant_lbs": round(f), "county": COUNTY_NAMES.get(cd, cd),
                      "hot_lat": round(wl, 5) if wl else None, "hot_lon": round(wo, 5) if wo else None}  # pound-weighted centre
                     for gy, gx, l, f, cd, wl, wo in rows]}
    _GRID_CACHE[key] = out
    return out
