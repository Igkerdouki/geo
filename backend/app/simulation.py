"""Geographic, relative Gaussian-plume scenarios with explicit provenance."""
import math
from datetime import datetime, timezone
import httpx
from app.coverage import california_location
from app.spatial_tools import _ground_conc, _SIG


def wind_conditions(lat: float, lon: float) -> dict:
    """Current and next 24 hourly model winds at 10 m; never simulated fallback data."""
    california_location(lat, lon)
    response = httpx.get('https://api.open-meteo.com/v1/forecast', params={
        'latitude': lat, 'longitude': lon, 'current': 'wind_speed_10m,wind_direction_10m,temperature_2m,relative_humidity_2m,precipitation,wind_gusts_10m',
        'hourly': 'wind_speed_10m,wind_direction_10m,temperature_2m,relative_humidity_2m,precipitation,wind_gusts_10m', 'forecast_days': 7,
        'wind_speed_unit': 'ms', 'timezone': 'UTC'}, timeout=15)
    response.raise_for_status(); body = response.json(); c = body.get('current', {})
    speed, direction = c.get('wind_speed_10m'), c.get('wind_direction_10m')
    if not all(isinstance(x, (int,float)) and math.isfinite(x) for x in (speed,direction)):
        raise ValueError('Weather provider returned no valid current wind.')
    h = body.get('hourly', {})
    return {'label': 'modelled', 'source': 'Open-Meteo', 'source_url': 'https://open-meteo.com/en/docs',
            'retrieved_at': datetime.now(timezone.utc).isoformat(), 'valid_at_utc': c.get('time'),
            'speed_ms': speed, 'from_deg': direction, 'height_m': 10,
            'temperature_c':c.get('temperature_2m'),'humidity_pct':c.get('relative_humidity_2m'),
            'precipitation_mm':c.get('precipitation'),'gust_ms':c.get('wind_gusts_10m'),
            'kind': 'Weather-model estimate, not a local wind sensor',
            'hours': [dict(time_utc=t,speed_ms=s,from_deg=d,
                temperature_c=(h.get('temperature_2m') or [None]*len(h.get('time',[])))[i],
                humidity_pct=(h.get('relative_humidity_2m') or [None]*len(h.get('time',[])))[i],
                # Hourly precipitation is the preceding-hour accumulation:
                # t+1 supplies the average rate for the interval [t,t+1].
                rain_mm_hr=(h.get('precipitation') or [])[i+1] if i+1<len(h.get('precipitation') or []) else None)
                for i,(t,s,d) in enumerate(zip(h.get('time',[]),h.get('wind_speed_10m',[]),h.get('wind_direction_10m',[]))) if s is not None and d is not None]}


def relative_at(east, north, speed, direction, stability):
    to = math.radians((direction+180)%360)
    along = east*math.sin(to)+north*math.cos(to)
    cross = -east*math.cos(to)+north*math.sin(to)
    ref = _ground_conc(100,0,speed,stability)
    return min(1.0, _ground_conc(along,cross,speed,stability)/ref) if ref else 0.0


def simulate_grid(source_lat: float, source_lon: float, target_lat: float, target_lon: float,
                  wind_speed_ms: float | None = None, wind_from_deg: float | None = None,
                  stability: str = 'D', extent_m: int = 1500, cells: int = 21,
                  month: int | None = None, chemical: int | None = None) -> dict:
    """Hypothetical source + wind → GeoJSON relative plume and sensitivity range.

    Historical monthly mass is returned separately, never treated as an emission
    rate or allocated to the user-selected field. No exposure/safety classification.
    """
    src = california_location(source_lat,source_lon); california_location(target_lat,target_lon)
    if stability not in _SIG or not 100 <= extent_m <= 3000 or not 5 <= cells <= 31:
        raise ValueError('Use stability A–F, extent 100–3000 m and 5–31 cells.')
    if (wind_speed_ms is None) != (wind_from_deg is None):
        raise ValueError('Supply both wind speed and direction or neither.')
    if month is not None and not 1 <= month <= 12: raise ValueError('Month must be 1–12.')
    if wind_speed_ms is None:
        weather = wind_conditions(source_lat,source_lon)
        speed, direction = weather['speed_ms'], weather['from_deg']
    else:
        speed, direction = wind_speed_ms, wind_from_deg
        weather = {'kind': 'User-specified what-if wind', 'speed_ms': speed, 'from_deg': direction}
    if not math.isfinite(speed) or not math.isfinite(direction) or not 0.5 <= speed <= 60 or not 0 <= direction < 360:
        raise ValueError('Steady-plume model requires wind 0.5–60 m/s and direction [0,360). Calm wind is unsupported.')
    scale = 111320*math.cos(math.radians(source_lat))
    east = (target_lon-source_lon)*scale; north = (target_lat-source_lat)*111320
    if math.hypot(east,north)>10000: raise ValueError('Source and target must be within 10 km for this local approximation.')
    target = relative_at(east,north,speed,direction,stability)
    sensitivity = [relative_at(east,north,speed,(direction+d)%360,s) for d in [-20,0,20] for s in sorted({stability,'C','D','E'})]
    def coord(x,y): return [source_lon+x/scale, source_lat+y/111320]
    features=[]; step=2*extent_m/cells
    for row in range(cells):
        for col in range(cells):
            x=-extent_m+col*step; y=-extent_m+row*step
            value=relative_at(x+step/2,y+step/2,speed,direction,stability)
            features.append({'type':'Feature','properties':{'relative_index':round(value,6)},
                'geometry':{'type':'Polygon','coordinates':[[coord(x,y),coord(x+step,y),coord(x+step,y+step),coord(x,y+step),coord(x,y)]]}})
    prior=None; prior_status='Not requested'
    if month is not None:
        try:
            from app.models.seasonal import seasonal_prior
            prior=seasonal_prior(src['county_cd'],month,chemical); prior_status='Available'
        except Exception:
            prior_status='Trained historical model unavailable; no historical prediction inferred'
    return {'label':'modelled','engine':'Gaussian plume / Briggs rural screening model',
        'source':{**src,'kind':'User-selected hypothetical source; not a verified application'},
        'target':{'lat':target_lat,'lon':target_lon,'relative_index':round(target,6)},
        'wind':weather,'stability':stability,'grid':{'type':'FeatureCollection','features':features},
        'sensitivity':{'minimum':min(sensitivity),'maximum':max(sensitivity),
            'meaning':'Sensitivity to wind ±20° and stability C/D/E plus selected class, not a confidence interval'},
        'historical_prior':prior,'historical_prior_status':prior_status,
        'normalization':'Relative to 100 m directly downwind in the same conditions; clipped to [0,1]. Not a probability.',
        'limitations':['Flat terrain, 2 m release, steady wind; no building airflow, deposition or chemical fate.',
            'County monthly pounds cannot determine source emission rate, application time or personal exposure.',
            'No current spraying established; this scenario cannot determine safety.']}
