"""Real-town model data on demand: OSM buildings/roads/water/POIs (OpenFreeMap tiles) + CDPR sections + SURF water sites."""
import json
import math

import httpx
import mapbox_vector_tile as mvt
from fastapi import APIRouter, Query

from app.spatial_tools import _db

router = APIRouter()
_CACHE = {}
OFM = "https://tiles.openfreemap.org/planet/20261101_080013_pt/{z}/{x}/{y}.pbf"
FUMIGANTS = (136, 385, 573, 616, 970)


@router.get("/spatial/place")
def place(lat: float = Query(..., ge=32, le=42.5), lon: float = Query(..., ge=-125, le=-114),
          radius_m: float = Query(1000, ge=300, le=1500), name: str = "Selected place"):
    key = (round(lat, 4), round(lon, 4), radius_m)
    if key in _CACHE:
        return _CACHE[key]
    z, M, C, R = 14, 111320, math.cos(math.radians(lat)), radius_m

    def tile(la, lo):
        n = 2 ** z
        s = math.log(math.tan(math.pi / 4 + math.radians(la) / 2))
        return int((lo + 180) / 360 * n), int((1 - s / math.pi) / 2 * n)

    def ll(x, y, px, py, ext):
        n = 2 ** z
        yy = math.pi * (1 - 2 * (y + py / ext) / n)
        return math.degrees(math.atan(math.sinh(yy))), (x + px / ext) / n * 360 - 180

    def loc(la, lo):
        return [round((lo - lon) * M * C, 1), round((la - lat) * M, 1)]

    def inside(p):
        return abs(p[0]) < R and abs(p[1]) < R

    def rings(g, x, y, ext):
        cs = g["coordinates"]
        polys = [cs] if g["type"] == "Polygon" else cs if g["type"] == "MultiPolygon" else []
        return [[[loc(*ll(x, y, p[0], p[1], ext)) for p in r] for r in poly] for poly in polys]

    def lines(g, x, y, ext):
        cs = g["coordinates"]
        ls = [cs] if g["type"] == "LineString" else cs if g["type"] == "MultiLineString" else []
        return [[loc(*ll(x, y, p[0], p[1], ext)) for p in l] for l in ls]

    out = {"name": name, "center": [lat, lon], "radius_m": R, "buildings": [], "roads": [], "water": [], "waterways": [],
           "landuse": [], "pois": [], "sections": [], "street_names": [], "surf": []}
    cx, cy = tile(lat, lon)
    with httpx.Client(timeout=20) as c:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                x, y = cx + dx, cy + dy
                r = c.get(OFM.format(z=z, x=x, y=y))
                if r.status_code != 200:
                    continue
                d = mvt.decode(r.content, default_options={"y_coord_down": True})
                for L, dst in (("building", "buildings"), ("water", "water"), ("landuse", "landuse"), ("landcover", "landuse")):
                    if L not in d:
                        continue
                    ext = d[L]["extent"]
                    for f in d[L]["features"]:
                        for poly in rings(f["geometry"], x, y, ext):
                            if poly and poly[0] and inside(poly[0][0]):
                                p = f["properties"]
                                item = {"rings": poly}
                                if L == "building":
                                    item["h"] = p.get("render_height", 6)
                                else:
                                    item["class"], item["subclass"] = p.get("class"), p.get("subclass")
                                out[dst].append(item)
                if "transportation_name" in d:
                    ext = d["transportation_name"]["extent"]
                    for f in d["transportation_name"]["features"]:
                        nm = f["properties"].get("name")
                        for l in lines(f["geometry"], x, y, ext) if nm else []:
                            if l and any(inside(p) for p in l):
                                out["street_names"].append({"name": nm, "pts": l})
                for L, dst in (("transportation", "roads"), ("waterway", "waterways")):
                    if L not in d:
                        continue
                    ext = d[L]["extent"]
                    for f in d[L]["features"]:
                        for l in lines(f["geometry"], x, y, ext):
                            if l and any(inside(p) for p in l):
                                out[dst].append({"class": f["properties"].get("class"), "name": f["properties"].get("name"), "pts": l})
                if "poi" in d:
                    ext = d["poi"]["extent"]
                    for f in d["poi"]["features"]:
                        p, co = f["properties"], f["geometry"]["coordinates"]
                        while isinstance(co[0], list):
                            co = co[0]
                        pt = loc(*ll(x, y, co[0], co[1], ext))
                        if inside(pt) and p.get("class") in ("school", "fuel", "fire_station", "place_of_worship", "hospital", "park", "grocery", "shop", "water_tower", "drinking_water"):
                            out["pois"].append({"class": p.get("class"), "subclass": p.get("subclass"), "name": p.get("name"), "pt": pt})
    # the nearest school is the focus; if none, the clicked point
    sch = sorted([p for p in out["pois"] if p["class"] == "school"], key=lambda p: math.hypot(*p["pt"]))
    if not sch:
        out["pois"].insert(0, {"class": "school", "name": name, "pt": [0, 0]})
    else:
        out["pois"] = [sch[0]] + [p for p in out["pois"] if p["class"] != "school"]
    out["pois"] = [p for p in out["pois"] if p["class"] != "shop" or p.get("subclass") in ("supermarket", "convenience")][:20]
    out["buildings"] = out["buildings"][:2500]
    with _db() as conn:
        rows = conn.execute(
            """WITH pt AS (SELECT ST_SetSRID(ST_MakePoint(%s,%s),4326) g),
            near AS (SELECT DISTINCT ON (s.comtrs) s.comtrs, ST_AsGeoJSON(s.geom) gj FROM plss_sections s, pt
                     WHERE s.geom && ST_Expand(pt.g,0.05) AND ST_DWithin(s.geom::geography, pt.g::geography, %s))
            SELECT n.comtrs, n.gj, coalesce(sum(p.lbs),0), coalesce(sum(p.lbs) FILTER (WHERE chem_code = ANY(%s)),0),
              (SELECT c.chemname FROM pur_monthly q JOIN chemicals c USING (chem_code) WHERE q.comtrs=n.comtrs AND q.year BETWEEN 2020 AND 2024 GROUP BY 1 ORDER BY sum(q.lbs) DESC LIMIT 1)
            FROM near n LEFT JOIN pur_monthly p ON p.comtrs=n.comtrs AND p.year BETWEEN 2020 AND 2024 GROUP BY 1,2""",
            (lon, lat, R * 1.6, list(FUMIGANTS))).fetchall()
        for comtrs, gj, lbs, fum, top in rows:
            g = json.loads(gj)
            ring = g["coordinates"][0][0] if g["type"] == "MultiPolygon" else g["coordinates"][0]
            out["sections"].append({"comtrs": comtrs, "lbs": round(lbs), "fumigant_lbs": round(fum), "top_chemical": top,
                                    "ring": [loc(p[1], p[0]) for p in ring]})
        tot = conn.execute(
            """WITH pt AS (SELECT ST_SetSRID(ST_MakePoint(%s,%s),4326) g),
            near AS (SELECT s.comtrs FROM plss_sections s, pt WHERE s.geom && ST_Expand(pt.g,0.04) AND ST_DWithin(s.geom::geography, pt.g::geography, 1250))
            SELECT coalesce(sum(lbs),0) FROM pur_monthly JOIN near USING (comtrs) WHERE year BETWEEN 2020 AND 2024""", (lon, lat)).fetchone()
        out["lbs_1250"] = round(tot[0])
        for code, nm, la, lo, n, det, last in conn.execute(
                """SELECT site_code,name,lat,lon,samples,detections,last FROM surf_sites
                WHERE ST_DWithin(ST_MakePoint(lon,lat)::geography, ST_MakePoint(%s,%s)::geography, 6000) ORDER BY detections DESC LIMIT 6""",
                (lon, lat)).fetchall():
            chems = conn.execute("SELECT chemical,n,max_ppb FROM surf_site_chems WHERE site_code=%s ORDER BY n DESC LIMIT 3", (code,)).fetchall()
            out["surf"].append({"name": nm, "pt": loc(la, lo), "samples": n, "detections": det, "last": str(last),
                                "chems": [{"c": c2, "n": k, "max": round(m, 3)} for c2, k, m in chems]})
    _CACHE[key] = out
    return out
