"""Local EPA data adapter over MCP. It is not an EPA-operated MCP server."""
import os
import logging
from datetime import datetime, timezone
import httpx
from mcp.server.fastmcp import FastMCP
from app.config import BACKEND_ROOT
from app.coverage import california_location

mcp=FastMCP('AskGaia EPA adapter')
# AirNow authenticates via a query parameter. Never log provider request URLs.
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)


@mcp.tool()
def air_quality(lat: float, lon: float) -> dict:
    """AirNow regional AQI observations, NOT measurements of pesticide exposure."""
    california_location(lat,lon)
    key=os.getenv('AIRNOW_API_KEY')
    if not key: return {'error':'AirNow requires AIRNOW_API_KEY; no data inferred.'}
    # Do not expose request URLs containing the credential in exceptions or logs.
    try:
        response=httpx.get('https://www.airnowapi.org/aq/observation/latLong/current/',
            params={'format':'application/json','latitude':lat,'longitude':lon,'distance':25,'API_KEY':key},timeout=12)
        response.raise_for_status(); rows=response.json()
    except Exception:
        return {'error':'AirNow unavailable; no data inferred.'}
    if not isinstance(rows,list): return {'error':'Unexpected AirNow response.'}
    return {'label':'observed','source':'EPA AirNow reporting-area AQI','source_url':'https://www.airnow.gov/',
        'retrieved_at':datetime.now(timezone.utc).isoformat(),'observations':rows,
        'scope':'Regional criteria-pollutant AQI, not pesticide concentrations. Provider timestamps retained.'}


@mcp.tool()
def drinking_water(lat: float, lon: float) -> dict:
    """EPA ECHO county water-system records; not tap-water quality at a point."""
    location=california_location(lat,lon)
    try:
        response=httpx.get('https://echodata.epa.gov/echo/sdw_rest_services.get_systems',
            params={'output':'JSON','p_st':'CA','p_co':location['county']},timeout=15)
        response.raise_for_status(); data=response.json()
    except Exception: return {'error':'EPA ECHO drinking-water service unavailable.'}
    if not isinstance(data,dict) or not isinstance(data.get('Results'),dict):
        return {'error':'Unexpected EPA ECHO response.'}
    results=data['Results']
    if results.get('Error') or results.get('ErrorMessage'):
        return {'error':'EPA ECHO returned a service error.'}
    return {'label':'observed','source':'EPA ECHO / SDWIS','county':location['county'],
        'source_url':'https://echo.epa.gov/tools/web-services/facility-search-drinking-water',
        'retrieved_at':datetime.now(timezone.utc).isoformat(),'data':results,
        'scope':'County public-water-system administrative/compliance records. Not current tap-water concentrations or proof of the system serving a given property.'}


if __name__=='__main__': mcp.run(transport='stdio')
