"""Headless contracts for Ioanna's UI: bounded workflows and geographic scenarios."""
import asyncio
import os
import json
from contextlib import suppress
from fastapi.responses import StreamingResponse
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.orchestration import InvestigationRequest, Scenario, orchestrate, ROLES, progress_sink
from app import workflow_store
from app.llm import configured, provider, model_name
from app.coverage import california_location
from app.simulation import simulate_grid
from app.spray_transport import SprayScenario, simulate_spray
from app.model_validation import ValidationRequest, validate_measurements

router=APIRouter(prefix='/workflows')


@router.post('/validate-transport')
async def validate_transport(body: ValidationRequest):
    try: return await asyncio.to_thread(validate_measurements,body)
    except ValueError as exc: raise HTTPException(422,str(exc)) from None
    except Exception: raise HTTPException(503,'Validation unavailable; no metrics inferred.') from None


@router.get('/weather')
async def weather_for_scenario(lat: float, lon: float, provider: str = 'open-meteo'):
    from app.simulation import wind_conditions
    from app.environment import nws_observation
    if provider not in {'open-meteo','nws'}: raise HTTPException(422,'Choose open-meteo or nws.')
    try:
        return await asyncio.to_thread(nws_observation if provider=='nws' else wind_conditions,lat,lon)
    except ValueError as exc: raise HTTPException(422,str(exc)) from None
    except Exception: raise HTTPException(503,'Weather provider unavailable. No fallback generated.') from None


@router.get('/model-status')
def model_status(chemical: int | None = None):
    from app.models.seasonal import load_model
    try:
        model=load_model(chemical)
        return {'status':'trained', **{k:model[k] for k in ('model_type','version','trained_at','years','validation','scope','reporting_coverage','coverage_warning')}}
    except ValueError:
        return {'status':'untrained','detail':'No saved model for this chemical.'}
    except Exception:
        return {'status':'unavailable','detail':'Cannot verify training: database or model table unavailable.'}


@router.post('/investigate/stream')
async def investigate_stream(body: InvestigationRequest):
    if not configured(): raise HTTPException(503, 'Configure GEMINI_API_KEY in backend/.env or the project .env.')
    if body.start_year > body.end_year: raise HTTPException(422, 'Invalid year range.')
    async def events():
        queue=asyncio.Queue(maxsize=100)
        async def run():
            token=progress_sink.set(queue.put)
            try:
                result=await asyncio.wait_for(orchestrate(body), timeout=220)
                result['request']=body.model_dump(mode='json')
                try:
                    await asyncio.to_thread(workflow_store.save, 'workflow', result)
                    result['saved']=True
                except Exception:
                    result['saved']=False
                    result['warnings'].append('History storage unavailable. Download JSON to retain this result.')
                await queue.put({'type':'result','result':result})
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                await queue.put({'type':'error','message':f'Workflow unavailable ({type(exc).__name__}); no result inferred.'})
            finally:
                progress_sink.reset(token)
        task=asyncio.create_task(run())
        try:
            while True:
                try: item=await asyncio.wait_for(queue.get(),timeout=10)
                except asyncio.TimeoutError:
                    if task.done(): break
                    yield json.dumps({'type':'heartbeat'})+'\n'
                    continue
                yield json.dumps(item, default=str)+'\n'
                if item['type'] in {'result','error'}: break
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError): await task
    return StreamingResponse(events(), media_type='application/x-ndjson', headers={'Cache-Control':'no-store','X-Accel-Buffering':'no'})


@router.get('/history')
def workflow_history():
    try:
        return [{k:r.get(k) for k in ('id','request','status','updated_at')} for r in workflow_store.list_items('workflow')]
    except Exception:
        raise HTTPException(503, 'Workflow history unavailable.') from None


@router.get('/history/{item_id}')
def workflow_record(item_id: str):
    try: items=workflow_store.list_items('workflow',item_id)
    except Exception: raise HTTPException(503, 'Workflow history unavailable.') from None
    if not items: raise HTTPException(404, 'Workflow not found.')
    return items[0]


class CompareRequest(BaseModel):
    places: list[InvestigationRequest] = Field(min_length=2, max_length=2)


@router.post('/compare')
async def compare_places(body: CompareRequest):
    if not configured(): raise HTTPException(503, 'Configure GEMINI_API_KEY in backend/.env or the project .env.')
    a,b=body.places
    if (a.start_year,a.end_year,a.month,a.chemical,a.radius_km)!=(b.start_year,b.end_year,b.month,b.chemical,b.radius_km):
        raise HTTPException(422,'Comparison requires matching years, month, chemical and search radius.')
    async def one(request):
        try: return await asyncio.wait_for(orchestrate(request),timeout=220)
        except Exception: return {'status':'error','request':request.model_dump(mode='json'),'warnings':['Investigation unavailable.']}
    results=await asyncio.gather(*(one(p) for p in body.places))
    return {'places':results,'comparison_scope':'Same search radius and reporting window; recorded-use totals do not rank exposure or safety.'}


@router.post('/simulate-spray')
async def spray_scenario(body: SprayScenario):
    try:
        return await asyncio.wait_for(asyncio.to_thread(simulate_spray, body), timeout=30)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    except Exception:
        raise HTTPException(503, 'Spray scenario unavailable; no fallback weather generated.') from None


class SimulationRequest(Scenario):
    target_lat: float = Field(ge=32,le=42.1)
    target_lon: float = Field(ge=-125,le=-114)
    extent_m: int = Field(default=1500,ge=100,le=3000)
    cells: int = Field(default=21,ge=5,le=31)
    month: int | None = Field(default=None,ge=1,le=12)
    chemical: int | None = Field(default=None,ge=0)


@router.get('/capabilities')
def capabilities():
    return {'region':'California','agents':list(ROLES),'transport':'MCP stdio',
            'llm_configured':configured(), 'llm_provider':provider(), 'model':model_name(),
            'openai_configured':bool(os.getenv('OPENAI_API_KEY')),
            'neon_configured':bool(os.getenv('DATABASE_URL') or os.getenv('PUR_DATABASE_URL')),
            'epa_mcp_configured':bool(os.getenv('EPA_MCP_URL')),
            'epa_mode':'external MCP' if os.getenv('EPA_MCP_URL') else 'local EPA API adapter over MCP',
            'model_status':'Use training CLI to fit and evaluate; configuration does not prove trained status.',
            'modes':['investigate','what_if','spray_timeline','compare'], 'maximum_workflow_seconds':220,
            'weather_providers':['Open-Meteo model','NWS station observations'],
            'spraydays_status':'Structured notification import; automatic feed not configured',
            'airnow_configured':bool(os.getenv('AIRNOW_API_KEY'))}


@router.post('/investigate')
async def investigate(body: InvestigationRequest):
    if not configured(): raise HTTPException(503,'Configure GEMINI_API_KEY in backend/.env or the project .env.')
    if body.start_year>body.end_year: raise HTTPException(422,'Invalid year range.')
    try:
        return await asyncio.wait_for(orchestrate(body),timeout=220)
    except asyncio.TimeoutError:
        raise HTTPException(504,'Workflow reached its time limit; no completed answer is available.') from None
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from None
    except Exception:
        raise HTTPException(503,'Workflow unavailable. Check MCP/provider configuration.') from None


@router.post('/simulate')
async def simulate(body: SimulationRequest):
    try:
        return await asyncio.wait_for(asyncio.to_thread(simulate_grid,**body.model_dump()),timeout=55)
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from None
    except Exception:
        raise HTTPException(503,'Simulation inputs or weather/model providers are unavailable. No fallback data generated.') from None


@router.get('/coverage')
def coverage(lat: float, lon: float):
    try: return california_location(lat,lon)
    except ValueError as exc: raise HTTPException(422,str(exc)) from None


from app.map_workflow import MapScenario, map_simulation

@router.post('/map-simulation')
async def map_simulation_stage(body: MapScenario):
    try:
        return await asyncio.to_thread(map_simulation, body)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None

@router.get('/map-context')
async def map_context(lat: float, lon: float):
    from app.api.spatial import sections_near
    import math
    try:
        california_location(lat, lon)
        data = await asyncio.to_thread(sections_near, lat=lat, lon=lon, radius_km=4, start_year=2020, end_year=2024, limit=80)
        def score(s):
            distance = math.hypot((s['lon']-lon)*111320*math.cos(math.radians(lat)), (s['lat']-lat)*111320)
            return (s['fumigant_lbs'] or s['lbs']*.05)/(1+(distance/700)**3)
        source = max((s for s in data['sections'] if s['lbs']>0), key=score, default=None)
        return {'location':{'lat':lat,'lon':lon},'source':source,'records':data}
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from None
    except Exception:
        raise HTTPException(503,'Map records unavailable; no source inferred.') from None
