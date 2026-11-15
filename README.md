# AskGaia — Earth, understood.

AskGaia is an environmental evidence workspace built for SanD Hacks 2026. Ask about a California school, retrieve public documents, inspect source-backed findings, and investigate what is still unknown.

## Run locally

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
# Put server credentials in backend/.env; see .env.example.
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

In another terminal:

```bash
cd frontend
npm ci
npm run dev
```

Open http://localhost:5173. Vite proxies `/api` to port 8001. The previous dashboard remains at `/explorer`.

For a single-server preview, run `npm run build` in `frontend` **before** starting the API. The API serves `frontend/dist` at http://localhost:8001 when present. Bind only to localhost: this hackathon workspace does not implement accounts or multi-user authorization.

## Connections

Only server-side environment variables are used. Never put credentials in frontend variables.

| Variable | Purpose |
| --- | --- |
| `OPENAI_API_KEY` | Structured evidence analysis via OpenAI Responses API |
| `OPENAI_MODEL` | Defaults to `gpt-4.1-mini`; configurable without changing UI |
| `BRIGHTDATA_API_KEY` | Bright Data bearer credential |
| `BRIGHTDATA_SERP_ZONE` | SERP zone for evidence discovery |
| `BRIGHTDATA_UNLOCKER_ZONE` | Web Unlocker zone for retrieving source documents |
| `DATABASE_URL` | Optional Neon/Postgres connection string; evidence otherwise persists in SQLite |
| `GEO_PUR_DATABASE=1` | Enable existing local historical PUR database (separate from evidence storage) |

Bright Data **search** needs its API key and SERP zone. **Retrieval** needs its API key and Web Unlocker zone. Without those, the app labels search as unavailable and reads two official DPR guidance pages directly over HTTPS. Those pages are statewide context, not school-specific application evidence. There is no fabricated demo data fallback.

## Working flow

1. Ask a question about a place. Catalogue coordinates are explicitly provisional; unknown places remain unmapped.
2. Search with Bright Data (when configured), retrieve up to three public documents, and save their provenance and content fingerprints.
3. OpenAI produces findings and unresolved research questions. A deterministic check rejects missing sources, non-matching quotations, and quotations longer than 25 words. This verifies excerpt matching, not the truth of an AI interpretation.
4. Click **Show me the evidence** to inspect the exact excerpt and source.
5. Click **Investigate this gap** to run a focused follow-up search, or add a public HTTPS source URL yourself.
6. Refresh a source to compare its extracted content hash and preserve the previous text before reanalysis.
7. Export JSON or use **PDF** to print the full evidence packet to PDF. Saved investigations survive restarts.

Each investigation has a 12-source budget; the service permits at most three simultaneous investigation jobs. Jobs run in-process; interrupted jobs become retryable after a server restart. Use one API worker for this prototype.

## MCP

AskGaia exposes a real stdio MCP server:

```bash
cd backend
.venv/bin/python -m app.mcp_server
```

Configure an MCP host with the absolute path to `backend/.venv/bin/python`, arguments `["-m", "app.mcp_server"]`, and cwd set to the absolute `backend` directory. The server loads the ignored `backend/.env` itself.

Tools: `find_place`, `discover_public_evidence`, `read_public_source`, `get_county_records`, `get_investigation`, `explain_finding`, and `check_source_change`.

The web app and MCP server share the same implementations. The web app calls those Python functions directly; it does not claim to route its calls over MCP. Mastra is not integrated yet. The MCP server is compatible with hosts that support stdio.

## Scientific boundaries

- Recorded use, planned notices, hypothetical scenarios, and actual exposure are distinct.
- County totals never establish use near a particular school.
- Exact source excerpts are checked; AI interpretations need human review.
- The main workspace is a Three.js procedural neighborhood adapted from the supplied concept scene, with wind trails and a simplified relative Gaussian-plume layer. It is not a calibrated pesticide dispersion model. Buildings provide visual context, not a CFD simulation; no exposure or safety score is shown. A separate geographic map displays provisional catalogue locations.
- Existing experimental drift and dashboard code remains available in the explorer. The synthetic live feed is off unless `GEO_ENABLE_LEGACY_SIMULATOR=1`.
- The previous broad project vision is in `docs/ORIGINAL_README.md`; it is not a statement of implemented capability.

## Tests

```bash
cd backend
.venv/bin/pip install pytest
.venv/bin/python -m pytest tests -q
```

Tests cover citation validation, persistence, private URL rejection, provider failure recovery, source version preservation, REST lifecycle, and MCP tool registration. They mock remote providers and do not demonstrate successful live sponsor requests.

## Team

Ved Panse — engineering. Ioanna Gkerdouki — ideas and branding.


### Neon evidence history

Set `DATABASE_URL` in `backend/.env` to the pooled Postgres URL from your Neon project's **Connect** panel. Preserve its `sslmode=require` and `channel_binding` parameters. Install `backend/requirements.txt` (including `psycopg2-binary`) before running with Neon. The server creates `geo_cases` and `geo_case_versions` on first save. With no URL it uses SQLite; a configured database failure is surfaced rather than silently switching storage.

Each change to investigation evidence or conclusions saves a separate snapshot in the same transaction as the current case. Trace-only progress updates do not duplicate snapshots. `GET /api/investigations/{id}/history` lists the latest 100 versions; `GET /api/investigations/{id}/history/{version}` reads a historical version with full source bodies omitted. This supports comparing what was known before and after a notice changed. Existing SQLite cases are not automatically copied to Neon.

Historical pesticide records are separate: use `PUR_DATABASE_URL` for a database containing the existing PUR tables, or `GEO_PUR_DATABASE=1` for local DB settings. A fresh Neon evidence database does not need those tables.


### Cloud hosting

Vercel project: `askgaia`, project ID `prj_Vp8SiCePOGFRmxivPhWHdlB4VSCO`, team `team_XQsbqm3WNzgg2GDkLIqmV0hq`. `api/index.py` exposes FastAPI; `vercel.json` builds the frontend and routes same-origin API requests. Deployments must exclude `.env`, local data, and virtual environments. Set provider credentials as server-side production environment variables, never frontend variables.

Cloud investigations require Neon `DATABASE_URL`; the 3D scene works without it. Cloud jobs are awaited inside the request (240-second application limit, 300-second platform limit). This demo does not yet provide a durable distributed job queue or per-user case isolation. Legacy historical explorer endpoints also require `PUR_DATABASE_URL` with the historical tables.

### Explore a city in 3D

The default **City + wind** view starts in San Diego. Enter a city, press Explore, and choose the matching region. OpenFreeMap supplies geographic building footprints and height attributes rendered by MapLibre; this is an extrusion map, not a photorealistic city reconstruction. Missing height attributes fall back to 8 m, and mapped coverage varies.

Open-Meteo supplies geocoding and the latest modeled 10 m wind sample for the selected city, independently of the AI keys and Neon. The panel includes its timestamp and refresh control. Wind trails remain aligned to geographic bearings while orbiting the map. Animation uses a disclosed 12× speed and one uniform city-level sample, not simulated flow around buildings, a measured street-level wind field, or a pesticide exposure calculation. Failure to fetch wind is shown explicitly. The original procedural scene remains under **Illustrative lab**.

Run the wind-direction checks with `node --test frontend/tests/windVector.test.mjs`.

### Team ownership and combined MCP server

Ioanna owns UI and visual design; Ved/Codex owns logic, APIs, databases, MCP and tests. Preserve that separation when making changes.

Ioanna's spatial MCP contribution from commit `8f48e13` is integrated into the existing evidence MCP server. Both `cd backend && python mcp_server.py` and `python -m app.mcp_server` now expose all 13 tools: the seven evidence tools plus `geocode`, `pur_records`, `chemical_profile`, `wind`, `run_plume`, and `cite_sources`. Spatial implementations live in `backend/app/spatial_tools.py`; the original entry point remains compatible. Spatial queries require the `pur_monthly`, `chemicals`, and PostGIS `plss_sections` tables via `PUR_DATABASE_URL` (or `DATABASE_URL`). Installing requirements includes psycopg 3; the server can still list tools without database credentials.
