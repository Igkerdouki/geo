import asyncio
import os
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from app import evidence_store as store
from app import investigator
from app.evidence_tools import capabilities, find_places, county_records, ToolError

router = APIRouter(prefix='/investigations')
TASKS = {}


def require_storage():
    if os.getenv('VERCEL') and not os.getenv('DATABASE_URL'):
        raise HTTPException(503, 'Cloud investigations need the Neon DATABASE_URL. The 3D scene is available now.')


async def finish_cloud_task(case):
    # Keep cloud work inside the request lifetime instead of a detached task.
    if os.getenv('VERCEL'):
        try:
            await asyncio.wait_for(TASKS[case['id']], timeout=240)
        except asyncio.TimeoutError:
            latest = store.get(case['id'])
            latest['status'] = 'error'
            latest['errors'].append('Investigation reached the cloud time limit. Saved evidence is retained.')
            store.save(latest)
        return store.get(case['id'])
    return case


class Start(BaseModel):
    question: str = Field(min_length=8, max_length=1500)
    place: str = Field(min_length=2, max_length=150)


class Followup(BaseModel):
    gap_id: str | None = None
    source_url: str | None = Field(default=None, max_length=2000)
    refresh_id: str | None = None


def public_case(case):
    # Full source text stays on the server; excerpts and metadata are returned.
    return {**case, 'sources': [{k:v for k,v in s.items() if k != 'text'} for s in case['sources']],
            'revisions': [{k:v for k,v in r.items() if k != 'previous_source'} for r in case['revisions']]}


def start_task(case, **kwargs):
    if case['id'] in TASKS:
        raise HTTPException(409, 'An investigation is already running.')
    if len(TASKS) >= 3:
        raise HTTPException(429, 'Three investigations are already running. Try again shortly.')
    case['status'] = 'queued'
    store.save(case)
    task = asyncio.create_task(investigator.run(case['id'], **kwargs))
    TASKS[case['id']] = task
    task.add_done_callback(lambda _: TASKS.pop(case['id'], None))


@router.get('/capabilities')
def status():
    return capabilities()


@router.get('/places')
def places(q: str = ''):
    return find_places(q)


@router.get('/county-records')
async def historical_county_records(county: str = Query(min_length=1, max_length=60),
                                    year: int = Query(default=2023, ge=1900, le=2100)):
    """Read imported historical totals, not live spray or exposure measurements."""
    try:
        return await county_records(county, year)
    except ToolError as exc:
        raise HTTPException(503, str(exc)) from None


@router.get('')
def list_cases():
    if os.getenv('VERCEL') and not os.getenv('DATABASE_URL'):
        return []
    return store.recent()


@router.post('', status_code=202)
async def create_case(body: Start):
    require_storage()
    if not capabilities()['llm_configured']:
        raise HTTPException(503, 'Configure GEMINI_API_KEY in backend/.env or the project .env to start an investigation.')
    if len(TASKS) >= 3:
        raise HTTPException(429, 'Three investigations are already running.')
    matches = find_places(body.place)
    place = next((p for p in matches if p['name'].lower() == body.place.lower()), None)
    if place is None:
        place = dict(name=body.place, coordinate_precision='Location not resolved; no point placed on map')
    case = store.create(body.question, place)
    start_task(case)
    return public_case(await finish_cloud_task(case))


@router.get('/{case_id}')
def read_case(case_id: str):
    case = store.get(case_id)
    if not case:
        raise HTTPException(404, 'Investigation not found.')
    if not os.getenv('VERCEL') and case['status'] in ('queued', 'running') and case_id not in TASKS:
        case['status'] = 'error'
        case['errors'].append('The server restarted during this investigation. Retry to continue with saved evidence.')
        store.save(case)
    return public_case(case)


@router.post('/{case_id}/followup', status_code=202)
async def followup(case_id: str, body: Followup):
    require_storage()
    case = store.get(case_id)
    if not case:
        raise HTTPException(404, 'Investigation not found.')
    gap = next((g for g in case['gaps'] if g['id'] == body.gap_id), None)
    if body.gap_id and not gap:
        raise HTTPException(404, 'Evidence gap not found.')
    if body.refresh_id and not any(s['id'] == body.refresh_id for s in case['sources']):
        raise HTTPException(404, 'Source not found.')
    if sum(bool(x) for x in (body.gap_id, body.source_url, body.refresh_id)) > 1:
        raise HTTPException(422, 'Choose one follow-up action.')
    if len(case['sources']) >= 12 and not body.refresh_id:
        raise HTTPException(422, 'This investigation has reached its 12-source budget. Start another investigation.')
    start_task(case, gap=gap, source_url=body.source_url, refresh_id=body.refresh_id)
    return public_case(await finish_cloud_task(case))


@router.get('/{case_id}/export')
def export_case(case_id: str):
    case = store.get(case_id)
    if not case:
        raise HTTPException(404, 'Investigation not found.')
    from fastapi.responses import Response
    import json
    return Response(json.dumps(public_case(case), indent=2), media_type='application/json',
                    headers={'Content-Disposition': f'attachment; filename="askgaia-evidence-{case_id[:8]}.json"'})



@router.get('/{case_id}/history')
def case_history(case_id: str):
    if not store.get(case_id):
        raise HTTPException(404, 'Investigation not found.')
    return store.history(case_id)


@router.get('/{case_id}/history/{version}')
def case_version(case_id: str, version: int):
    case = store.get_version(case_id, version)
    if not case:
        raise HTTPException(404, 'Investigation version not found.')
    return public_case(case)
