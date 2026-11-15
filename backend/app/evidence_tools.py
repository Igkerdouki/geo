"""Shared tools used by the web investigator and the standalone MCP server."""
import asyncio
import hashlib
import io
import ipaddress
import json
import os
import socket
from urllib.parse import urlparse, quote
from uuid import uuid4

import httpx
from bs4 import BeautifulSoup
from pypdf import PdfReader
from app.config import BACKEND_ROOT  # loads env
from app.evidence_store import now
from app.data.sensitive_locations import get_all_sensitive_locations

SEEDS = [
 'https://www.cdpr.ca.gov/2026/06/25/your-top-spraydays-questions-answered/',
 'https://www.cdpr.ca.gov/cac-letter/new-notification-and-reporting-requirements-for-pesticide-use-near-schoolsites/',
]
MAX_BYTES = 3_000_000


class ToolError(Exception):
    pass


from app.llm import configured, provider, model_name


def capabilities():
    return dict(llm_configured=configured(), llm_provider=provider(), openai=bool(os.getenv('OPENAI_API_KEY')),
                brightdata_search=bool(os.getenv('BRIGHTDATA_API_KEY') and os.getenv('BRIGHTDATA_SERP_ZONE')),
                brightdata_retrieve=bool(os.getenv('BRIGHTDATA_API_KEY') and os.getenv('BRIGHTDATA_UNLOCKER_ZONE')),
                storage='Neon / Postgres' if os.getenv('DATABASE_URL') else ('Neon connection needed' if os.getenv('VERCEL') else 'Local SQLite'),
                model=model_name())


def find_places(query: str):
    words = query.lower().split()
    return [{**p, 'coordinate_precision': 'Unverified catalogue point; confirm with school boundary data'}
            for p in get_all_sensitive_locations() if all(w in (p['name']+' '+p['county']).lower() for w in words)][:15]


async def validate_url(url):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ToolError('Only public HTTPS source URLs are supported.')
    if parsed.hostname in ('localhost',) or parsed.hostname.endswith(('.local', '.internal')):
        raise ToolError('Private network sources are not allowed.')
    try:
        addresses = await asyncio.get_running_loop().getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
            raise ToolError('Private network sources are not allowed.')
    except socket.gaierror:
        raise ToolError('Source hostname could not be resolved.') from None
    return url


async def bright_request(url, zone):
    async with httpx.AsyncClient(timeout=50) as client:
        response = await client.post('https://api.brightdata.com/request', headers={'Authorization': 'Bearer '+os.environ['BRIGHTDATA_API_KEY']},
                                     json={'zone': zone, 'url': url, 'format': 'raw'})
    if response.status_code != 200:
        raise ToolError(f'Bright Data returned HTTP {response.status_code}. Check the API key, zone, and credits.')
    if len(response.content) > MAX_BYTES:
        raise ToolError('Source exceeded the 3 MB retrieval limit.')
    return response


async def search_web(query: str):
    if not capabilities()['brightdata_search']:
        raise ToolError('Bright Data search needs BRIGHTDATA_API_KEY and BRIGHTDATA_SERP_ZONE in backend/.env.')
    result = await bright_request('https://www.google.com/search?q='+quote(query[:400])+'&brd_json=1', os.environ['BRIGHTDATA_SERP_ZONE'])
    try:
        body = result.json()
        return [{'url': r.get('link') or r.get('url'), 'title': r.get('title', ''), 'snippet': r.get('description', '')}
                for r in body.get('organic', [])[:5] if r.get('link') or r.get('url')]
    except (ValueError, AttributeError):
        raise ToolError('Bright Data returned an unexpected search response. Check that the zone is a SERP zone.') from None


async def retrieve_source(url: str):
    await validate_url(url)
    provider = 'Bright Data Web Unlocker' if capabilities()['brightdata_retrieve'] else 'Direct public HTTPS'
    if capabilities()['brightdata_retrieve']:
        response = await bright_request(url, os.environ['BRIGHTDATA_UNLOCKER_ZONE'])
        content, content_type = response.content, response.headers.get('content-type', '')
    else:
        async with httpx.AsyncClient(timeout=25, follow_redirects=False, trust_env=False) as client:
            current = url
            for _ in range(4):
                await validate_url(current)
                async with client.stream('GET', current, headers={'User-Agent': 'GEO-Research/1.0'}) as response:
                    if response.is_redirect:
                        from urllib.parse import urljoin
                        current = urljoin(current, response.headers['location'])
                        continue
                    if response.status_code != 200:
                        raise ToolError(f'Source returned HTTP {response.status_code}.')
                    chunks, size = [], 0
                    async for part in response.aiter_bytes():
                        size += len(part)
                        if size > MAX_BYTES:
                            raise ToolError('Source exceeded the 3 MB retrieval limit.')
                        chunks.append(part)
                    content, content_type = b''.join(chunks), response.headers.get('content-type', '')
                    url = current
                    break
            else:
                raise ToolError('Too many source redirects.')
    if content.startswith(b'%PDF') or 'application/pdf' in content_type:
        try:
            pdf = PdfReader(io.BytesIO(content))
            text = '\n'.join(page.extract_text() or '' for page in pdf.pages[:20])
            title = urlparse(url).path.split('/')[-1]
        except Exception:
            raise ToolError('Could not extract this PDF.') from None
    else:
        soup = BeautifulSoup(content, 'html.parser')
        title = soup.title.get_text(' ', strip=True) if soup.title else urlparse(url).hostname
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'noscript']):
            tag.decompose()
        main = soup.find('main') or soup.find('article') or soup.body or soup
        text = main.get_text(' ', strip=True)
    text = ' '.join(text.split())[:24000]
    if len(text) < 150:
        raise ToolError('This source has insufficient readable text; it may need browser rendering.')
    return dict(id=uuid4().hex[:12], url=url, title=title, text=text, retrieved_at=now(),
                provider=provider, sha256=hashlib.sha256(text.encode()).hexdigest(),
                scope='Retrieved document; geographic relevance requires verification')


async def county_records(county: str, year: int = 2023):
    """County totals are context ONLY: never a school proximity or exposure query."""
    if not (1900 <= year <= 2100) or len(county) > 60:
        raise ToolError('Invalid county or year.')
    def query():
        from app.database import get_pur_connection
        conn = get_pur_connection()
        try:
            with conn.cursor() as cur:
                cur.execute('SET statement_timeout = 8000')
                cur.execute("SELECT to_regclass('public.pur_monthly') IS NOT NULL AS monthly")
                monthly = cur.fetchone()['monthly']
                if monthly:
                    from app.api.sprays import COUNTY_COORDS
                    name = county.strip().upper().removesuffix(' COUNTY')
                    code = next((k for k, v in COUNTY_COORDS.items() if v['name'] == name), None)
                    if code is None:
                        raise ValueError('Unknown California county')
                    cur.execute("""SELECT COUNT(*) AS records, SUM(lbs::double precision) AS pounds,
                        SUM(n_apps)::bigint AS application_count FROM public.pur_monthly
                        WHERE county_cd=%s AND year=%s""", (code, year))
                else:
                    cur.execute('SELECT COUNT(*) AS records, SUM(lbs_chm_used) AS pounds FROM sprays WHERE UPPER(county)=%s AND year=%s', (county.upper(), year))
                row = cur.fetchone()
                return dict(county=county.upper(), year=year, records=row['records'],
                            pounds=float(row['pounds']) if row['pounds'] is not None else None,
                            application_count=row.get('application_count'),
                            granularity='Monthly section/chemical aggregates' if monthly else 'Imported PUR rows',
                            table='pur_monthly' if monthly else 'sprays',
                            scope='Historical county-wide context only; monthly rows are not individual spray events. Application counts may include chemical-level duplication. Cannot establish current spraying, school proximity or personal exposure.')
        finally:
            conn.close()
    try:
        return await asyncio.to_thread(query)
    except Exception:
        raise ToolError('Historical PUR database unavailable. No county totals have been inferred.') from None


def source_changes(previous, current):
    import difflib
    return dict(changed=previous['sha256'] != current['sha256'], previous_hash=previous['sha256'], current_hash=current['sha256'],
                diff='\n'.join(difflib.unified_diff(previous['text'].split('. '), current['text'].split('. '), fromfile='previous', tofile='current'))[:12000])
