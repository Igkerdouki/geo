"""Run from backend: .venv/bin/python scripts/verify_integrations.py [--live].

Prints status only, never credentials or provider exception messages.
--live makes a small OpenAI planner request and read-only provider calls.
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import BACKEND_ROOT
from app.orchestration import MCPTools, InvestigationRequest, plan_workflow
from app.spray_transport import SprayScenario, simulate_spray


def checked(name, operation):
    try:
        result=operation()
        return {'name':name,'status':'unavailable' if isinstance(result,dict) and result.get('error') else 'ok'}
    except Exception as exc: return {'name':name,'status':'unavailable','error_class':type(exc).__name__}


async def main(live):
    results=[]
    scenario=dict(source_lat=36.7378,source_lon=-119.7871,start_at='2026-11-15T04:00:00Z',
        event_source='Synthetic integration smoke',location_uncertainty_m=20,duration_minutes=1,horizon_minutes=5,
        ingredients=[dict(name='Test tracer',applied_kg=1,airborne_fraction=.01,assumption_source='Synthetic smoke only')],
        wind=[dict(minute=0,speed_ms=2,from_deg=270)])
    results.append(checked('transport',lambda:simulate_spray(SprayScenario(**scenario))))
    try:
        async with MCPTools() as bridge:
            assert {'simulate_spray_event','nws_observation','epa_air_quality','epa_drinking_water'}<=bridge.tools.keys()
            response=await bridge.call('simulate_spray_event',{'scenario':scenario})
            assert response['snapshots'][0]['minute']==5
            results.append({'name':'two_mcp_servers_and_transport','status':'ok'})
    except Exception as exc: results.append({'name':'mcp','status':'unavailable','error_class':type(exc).__name__})
    if live:
        from app.simulation import wind_conditions
        from app.environment import nws_observation
        from app.models.seasonal import load_model
        from app.epa_mcp_server import air_quality, drinking_water
        from openai import AsyncOpenAI
        for name,fn in [('neon_saved_model',lambda:load_model()),('open_meteo',lambda:wind_conditions(36.7378,-119.7871)),
                        ('nws',lambda:nws_observation(36.7378,-119.7871)),('epa_airnow',lambda:air_quality(36.7378,-119.7871)),
                        ('epa_echo',lambda:drinking_water(36.7378,-119.7871))]:
            results.append(await asyncio.to_thread(checked,name,fn))
        try:
            async with AsyncOpenAI(timeout=8,max_retries=0) as client:
                await plan_workflow(InvestigationRequest(place='Fresno, California',question='What is known from historical pesticide records?'),client)
            results.append({'name':'openai_planner','status':'ok'})
        except Exception as exc: results.append({'name':'openai_planner','status':'unavailable','error_class':type(exc).__name__})
    print(json.dumps({'checks':results,'live_requested':live,'real_measurement_validation':'No field dataset supplied'},indent=2))
    return 0 if all(r['status']=='ok' for r in results) else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--live',action='store_true')
    raise SystemExit(asyncio.run(main(parser.parse_args().live)))
