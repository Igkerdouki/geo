# AskGaia architecture implementation status

## Use locally

Start/restart the backend so it loads the new routes (a previously started server
without `--reload` will retain the old Python modules):

```sh
cd /Users/vedpanse/geo/backend
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

The existing Vite frontend hot-reloads changes. If it is not running:

```sh
cd /Users/vedpanse/geo/frontend
npm run dev -- --host 127.0.0.1
```

Open http://localhost:5173. **Ask a question** starts the four-agent workflow.
Enable **Compare two places** to investigate two California places with the same
2020–2024 reporting window and 1.25 km search radius. **Simulation** in the header
opens the spray form, map playback, notice/report tools, training status and
measurement evaluation. A completed scenario can be attached to an investigation.
The existing procedural **Lab** remains an independent illustration; geographic
backend results appear in **Map**, which retains the existing 3D building design.

The new workflow supports streaming progress, Stop, source/evidence inspection,
JSON download, and database-backed history. When history cannot be saved, the
result is still returned with `saved: false` and a warning. Stopped runs are not
resumable. The two-place UI streams each place separately; failure of a later
place preserves earlier results. Results do not rank health or safety.

## Completion matrix

| Item | Implementation | Remaining external work / limitations |
| --- | --- | --- |
| Frontend → four agents | Research uses `/workflows/investigate/stream` | Live OpenAI round trip could not connect in this restricted execution session |
| Progress / sources / labels | Streaming agent and tool events, reports, evidence IDs, separate claim classes | Evidence-reference checks do not prove factual entailment |
| Simulation → map | Geographic plume cells, colored ingredient parcels, dispersion ellipses, sensitivity extents | Browser verification blocked by browser-session error; build and logic tests pass |
| Scenario controls / playback | Source, local start, duration, ingredients, assumed fate, weather, receptors and timeline | Parameters must be supplied accurately |
| Simulation agent transport tool | `simulate_spray_event` registered and user-bound | Verified with actual MCP subprocess transport |
| Neon training | CLI with schema checks, county mapping, held-out metrics, persisted model versions; UI reports actual model status | Training attempted; database connection failed. No successful Neon model training claimed |
| Scheduled applications | Persistent structured SprayDays notification import, uncertainty and four-day latest-start default, immutable revisions | Automatic official-feed adapter is NOT connected; no verified machine-readable feed contract obtained |
| Actual application reports | Manual reports and bearer-authenticated telemetry endpoint | Equipment credential and a real equipment/applicator source are not provisioned; authenticated caller is not independent field verification |
| Chemical/application properties | Ingredient-specific explicit assumptions, source description, droplet/residual size, density, release height, formulation/method metadata | No curated transport-property dataset; no values inferred from a chemical name or historical mass |
| Transport physics | Optional Gaussian puff dilution; mixed-layer settling, D-squared evaporation, vapor transfer, rain removal, planar-grade sensitivity | Screening approximations, NOT AgDRIFT. No real terrain grid, building airflow, nozzle droplet spectrum, reaction products or validated deposition map |
| Uncertainty | 11-member one-at-a-time source/time/wind/removal sensitivity | Not a joint probability distribution or confidence bound; time range is ±120 min maximum, not the full possible four-day notice window |
| Measurement validation | Exact receptor/time/ingredient matching; bias, MAE, RMSE on supplied independent samples | No measured field dataset supplied. Cannot claim validated drift accuracy |
| EPA MCP | Separate local EPA API adapter MCP, or configured external MCP | Local MCP startup verified; EPA HTTP services not reachable here; AirNow key absent |
| NWS | Nearby station observations, unit conversion, distance and freshness checks | Live provider unreachable here; no automatic substitution of observations for future forecast weather |
| Dynamic orchestration | LLM planner chooses specialist ordering and tasks; location first/verifier last; fixed fallback explicitly reported | Bounded planner, not arbitrary multi-agent graph generation |
| Two-place comparison | Matching-scope API and frontend results | Same source when attaching a scenario; no unsupported exposure ranking |
| End-to-end verification | Backend unit/integration tests, streamed API + storage tests, actual MCP call, frontend stream tests/build/lint | Live providers and browser flow remain unverified for the reasons above |

## Training and service verification

From `backend`:

```sh
.venv/bin/python scripts/train_seasonal.py --save-neon --end-year 2023
.venv/bin/python scripts/verify_integrations.py --live
.venv/bin/python -m pytest tests -q
```

Choose the final reporting year after checking reporting completeness. The
example does not certify that 2023 is complete in the connected database. The
training command reads county-month totals, accepts `county_cd` or derives the
county from the first two characters of CDPR `comtrs`, checks California codes,
holds out the final selected year and compares against a county-mean baseline.
It excludes held-out cells with no training observations and never fills missing
months with zero. It does not train transport physics.

`verify_integrations.py --live` makes one small paid OpenAI planning request,
read-only provider/database checks, and a synthetic scenario through real MCP
transport. It prints no keys or raw exception strings. A configured key is not
proof of provider connectivity. Current local verification found both MCP servers
and the transport functional, but all external providers unavailable.

## New API contracts

All routes below use the `/api` prefix. OpenAPI is at `/docs`.

- `POST /workflows/investigate/stream`: NDJSON `agent`, `plan`, `tool`, `evidence`,
  `heartbeat`, `result`, `error` records. Disconnect cancels the request's agent
  task. Max 220 seconds. The result is saved when storage is available.
- `GET /workflows/history`, `GET /workflows/history/{id}`: stored workflows.
- `POST /workflows/compare`: two investigation requests with identical dates,
  month, chemical and radius; independent evidence per place.
- `POST /workflows/simulate-spray`: explicit `SprayScenario`; missing forecasts
  return errors, not synthetic data. See SPRAY_TRANSPORT.md for the base body.
- `GET /workflows/weather?lat=...&lon=...&provider=nws`: fresh nearby station data.
  `provider=open-meteo` returns model weather including hourly humidity, temperature
  and precipitation. Observation timestamps, distance and origin are retained.
- `GET /workflows/model-status?chemical=...`: trained/untrained/unavailable, with
  actual saved metrics when accessible. Never reports configuration as training.
- `POST /workflows/validate-transport`: scenario, independent measurements,
  `dataset_id`, `held_out`. Metrics evaluate only the supplied samples.
- `GET /application-events`: up to 100 most recently updated stored events.
- `POST /application-events/reports`: manually reported actual start/completion.
- `POST /application-events/telemetry`: same body, `Authorization: Bearer <token>`;
  requires configured `GEO_INGEST_TOKEN`. No token means writes are disabled.
- `POST /application-events/spraydays/import`: `{ "events": [...] }`; each event
  must be `kind: scheduled`, source `SprayDays`, an HTTPS SprayDays URL, and at
  least 1140 m location uncertainty. This is a user import, not source authentication.

An application event contains `source_id`, `source`, optional `source_url`,
`start_at` (timezone-aware), optional `latest_start_at`, `lat`, `lon`,
`location_uncertainty_m`, `ingredients: [{name, applied_kg?}]`, `status`, and
optional `application_method`, `duration_minutes`, `notes`. Scheduled records
allow only `scheduled`/`cancelled`; reports allow `started`/`completed`/`cancelled`.
A notice's time passing never automatically changes it to an actual spray event.
Updates preserve revisions in `geo_work_items` (`event_revision`). The local
workspace is not a public multi-user reporting service; it has no user accounts
or field ownership verification for manual reports.

A measurement upload in Simulation contains:

```json
{
  "dataset_id": "YOUR_INDEPENDENT_DATASET",
  "held_out": true,
  "measurements": [
    {
      "receptor_id": "target",
      "ingredient": "EXACT_INGREDIENT_NAME",
      "at": "2026-11-15T04:05:00Z",
      "concentration_ug_m3": 0,
      "source": "REPLACE_WITH_REAL_MEASUREMENT_REFERENCE",
      "sample_kind": "instantaneous"
    }
  ]
}
```

The zero above is a schema placeholder, not a field measurement. Replace it with
real independent observations. UI attaches the current scenario. Only exact
snapshot times (five-minute boundaries and the final frame) are accepted. Averaged,
censored/below-detection-limit, deposition or different-unit samples are not
silently converted into instantaneous air concentrations. `held_out` and provenance
are caller declarations; the service does not independently authenticate them.

## Physics interpretation

The baseline remains a passive tracer. Extended physics requires explicit mixing
height, release height, horizontal/vertical diffusivity, wind-height exponent and
assumption source. First-order losses compete and conserve released airborne mass.
Volatilization transfers mass to vapor, not a loss. The vapor shares advection
and degrades; it does not undergo the droplet settling term. Applied mass not
released into air is outside the atmospheric budget.

Settling uses spherical-particle drag and a mixed-layer removal rate, not resolved
individual droplet impact trajectories. D-squared evaporation uses a supplied
coefficient referenced to 20°C/dry air and an explicit temperature/humidity
sensitivity law; an explicit nonvolatile residual diameter prevents water loss
from deleting active ingredient. Rain removal is a supplied coefficient times
rainfall. A planar terrain grade changes the assumed mixing depth/height; there
is no elevation-grid or terrain-flow model. Missing required weather is an error.
Application method/formulation identify assumptions; they do not select a fitted
method-specific model. Gaussian receptor estimates are instantaneous modeled
values, not exposure or safety recommendations.

Colored ellipses use mixture second moments and two standard deviations; they are
illustrations, not calibrated probability regions. Sensitivity rectangles enclose
final parcel centers across one-at-a-time perturbations; they do not bound all
possible aerosol spread. Failed ensemble members are shown, not dropped silently.
The engine rejects trajectories beyond 30 km and oversized computation requests.

Scientific context (these sources do not validate this implementation):

- https://www.epa.gov/pesticide-science-and-assessing-pesticide-risks/models-pesticide-risk-assessment
- https://www.jstage.jst.go.jp/article/jpestics/38/3/38_D12-064/_article
- https://www.weather.gov/documentation/services-web-api
- https://open-meteo.com/en/docs
- https://spraydays.cdpr.ca.gov/Home/About
- https://docs.airnowapi.org/webservices
- https://echo.epa.gov/tools/web-services/facility-search-drinking-water


## Ioanna frontend integration and Gemini (2026-11-15)

- Earth keeps Ioanna's presentation and uses backend section records, database totals,
  current model weather and the shared Gaussian plume evaluator. Its particles are
  illustrative; a historical section centroid is only a hypothetical source.
- Explorer chat calls `/api/chat` with bounded conversation history. Removed canned
  chemical, exposure and safety claims. County context is retrieved from the database;
  the response identifies the reporting year and does not imply live spraying.
- Server-side `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) takes priority over OpenAI.
  `GEMINI_MODEL` defaults to `gemini-2.5-flash`. Both four-agent investigations and
  evidence analysis share this provider routing. Secrets never enter frontend builds.
- Environment loading supports `backend/.env` and project `.env`; existing environment
  values take precedence. Restart the backend after changing keys.
- Verified mocked Gemini tool round trips, chat failures and plume direction contract.
  Live Gemini could not be verified: this execution environment cannot reach its API.
- Frontend dependency installation is blocked by DNS/network restrictions. Run
  `cd frontend && npm install` locally to install Ioanna's declared pbf 5 and 3D tiles
  dependencies. The current stale pbf 4 installation prevents a production build.
