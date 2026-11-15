"""Provider adapters. Missing observations stay missing; no generated weather."""
import math
from datetime import datetime, timezone
from urllib.parse import urlsplit
import httpx
from app.coverage import california_location


def finite(value):
    return isinstance(value, (int,float)) and not isinstance(value,bool) and math.isfinite(value)


def nws_get(client, url):
    if urlsplit(url).scheme!='https' or urlsplit(url).netloc!='api.weather.gov':
        raise ValueError('Unexpected NWS provider URL.')
    response=client.get(url)
    response.raise_for_status()
    return response.json()


def observation_values(feature):
    props=feature['properties']
    speed=props.get('windSpeed') or {}
    direction=(props.get('windDirection') or {}).get('value')
    factor={'wmoUnit:km_h-1':1/3.6,'wmoUnit:m_s-1':1,'wmoUnit:kn':0.514444}.get(speed.get('unitCode'))
    if factor is None or not finite(speed.get('value')) or not finite(direction):
        raise ValueError('Station has missing or variable wind.')
    timestamp=datetime.fromisoformat(props['timestamp'].replace('Z','+00:00'))
    if timestamp.tzinfo is None: raise ValueError('Station timestamp lacks timezone.')
    age=(datetime.now(timezone.utc)-timestamp).total_seconds()/60
    if not -5 <= age <= 120: raise ValueError('Station observation is stale.')
    return {'speed_ms':speed['value']*factor,'from_deg':direction%360,
        'valid_at_utc':timestamp.isoformat(),'age_minutes':round(age,1),
        'temperature_c':(props.get('temperature') or {}).get('value'),
        'humidity_pct':(props.get('relativeHumidity') or {}).get('value')}


def nws_observation(lat: float, lon: float) -> dict:
    """Nearby station wind, with actual station position, observation age and source."""
    california_location(lat,lon)
    with httpx.Client(timeout=8, headers={'User-Agent':'AskGaia/0.1 environmental research','Accept':'application/geo+json'}) as client:
        point=nws_get(client,f'https://api.weather.gov/points/{lat:.4f},{lon:.4f}')
        stations=nws_get(client,point['properties']['observationStations'])
        features=stations.get('features',[])[:10]
        def distance(f):
            x,y=f['geometry']['coordinates'][:2]
            return math.hypot((x-lon)*111.32*math.cos(math.radians(lat)),(y-lat)*111.32)
        for station in sorted(features,key=distance)[:3]:
            if distance(station)>100: continue
            url=station['id'].rstrip('/')+'/observations/latest'
            try: values=observation_values(nws_get(client,url))
            except (ValueError,KeyError,httpx.HTTPError): continue
            return {**values,'label':'observed','source':'NWS station','source_url':url,
                'station':station['properties'].get('stationIdentifier'),
                'station_coordinates':station['geometry']['coordinates'],
                'distance_km':round(distance(station),2),
                'retrieved_at':datetime.now(timezone.utc).isoformat(),
                'kind':'Nearby station measurement, not field/nozzle-height wind'}
    raise ValueError('No recent nearby NWS station with valid wind.')
