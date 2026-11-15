# AskGaia agent and simulator API

Backend branch: `feat/agent-orchestration-simulator`. The existing frontend now uses the streamed workflow and geographic simulation layers. See IMPLEMENTATION_STATUS.md for verified status and remaining external dependencies.

## Architecture

A bounded orchestrator runs four OpenAI agents. With dynamic_planning enabled, an LLM planner selects data/simulation ordering and focused tasks; Location stays first and Verifier last. Without planning, or when planning fails, the fixed sequence is used. Each agent has a tool allowlist and a four-call budget. The agents call the actual shared MCP server over stdio. Location is checked against California county polygons before downstream work. User location, date range and hypothetical source coordinates are bound in code, not chosen by the model.

The Data agent can use Neon PUR records, chemical profiles, the seasonal model, and Bright Data evidence retrieval. The Simulation agent retrieves Open-Meteo wind and runs a hypothetical plume. The Verifier produces `observed`, `modelled` and `uncertain` claims with evidence IDs. Programmatic checks validate references and reject weather/plume results labelled observed; they do not prove the wording of an AI claim.

An external EPA MCP server is optional through `EPA_MCP_URL` (HTTPS Streamable HTTP, tools named `air_quality` and `drinking_water`). Without an external URL, a separate local EPA API adapter MCP is started. AirNow needs its own key; ECHO is keyless. These are adapters, not EPA-operated MCP servers. The workflow is synchronous, capped at 220 seconds, with streaming progress and durable completed-result history, but no durable resume. Hosting must support subprocesses and the required request duration.

## UI contract

| Endpoint | Purpose |
| --- | --- |
| `GET /api/workflows/capabilities` | Configuration and available roles; configured credentials do not prove connectivity |
| `GET /api/workflows/coverage?lat=36.7378&lon=-119.7871` | Resolve California county or return 422 |
| `POST /api/workflows/investigate` | Run four-agent investigation and return reports, claims and tool traces |
| `POST /api/workflows/simulate` | Return a GeoJSON plume without requiring an LLM |

Investigation request:

```json
{
  "place": "Fresno, California",
  "question": "What do historical pesticide records and current wind tell us about this area?",
  "start_year": 2020,
  "end_year": 2024,
  "month": 11,
  "radius_km": 1.25,
  "scenario": {
    "source_lat": 36.7378,
    "source_lon": -119.7871,
    "wind_speed_ms": 2,
    "wind_from_deg": 0,
    "stability": "D"
  }
}
```

Omit `scenario` if the user has not selected a hypothetical source. Omit both wind fields to request current weather-model wind. A place outside California stops the workflow; it does not imply zero pesticide use. Set the month explicitly. Optional `chemical` selects a chemical-specific trained prior.

Standalone simulation request:

```json
{
  "source_lat": 36.7378,
  "source_lon": -119.7871,
  "target_lat": 36.7368,
  "target_lon": -119.7871,
  "wind_speed_ms": 2,
  "wind_from_deg": 0,
  "stability": "D",
  "extent_m": 1500,
  "cells": 21
}
```

Render the response's `grid` as GeoJSON, colouring `properties.relative_index`. Show `wind`, `target`, `sensitivity`, `historical_prior_status` and limitations. In investigation responses the full grid lives in the successful `simulate_grid` evidence result. Check `status` and individual evidence errors; a partial workflow is not a complete result.

## Historical model training

From the repository root:

```sh
backend/.venv/bin/python backend/scripts/train_seasonal.py --save-neon
```

Optional `--chemical 1855` fits a separate chemical model. Requires `PUR_DATABASE_URL` or `DATABASE_URL` and `public.pur_monthly` columns `year`, `month`, `county_cd`, `lbs`, `chem_code`. Spatial tools additionally require PostGIS, `plss_sections` and `chemicals`.

The CLI aggregates county-month reported pounds, fits a seasonal shrinkage model, evaluates on the latest year against a county-mean baseline, and refits all years after validation. At least three years are required. Missing cells stay missing. Check reporting completeness before trusting the evaluation: the latest year may be partial. Artifacts include observed coverage counts, held-out MAE, baseline MAE, data hash and training timestamp. An improvement over baseline is not guaranteed.

`--save-neon` writes versioned artifacts plus the current pointer into `askgaia_models`. A local JSON copy goes to ignored `backend/data/models`. The inference tool refuses absent models or unobserved county-months. Configuration alone does not mean a model was trained.

## Model interpretation

The trained quantity is historical county-month reported active-ingredient pounds. It is not a model of airborne exposure, field spraying events, or an emission rate. The simulator returns this prior separately from the physics output.

Open-Meteo provides current and forecast weather-model estimates, not a local sensor feed. Provider failure produces an unavailable result, never synthetic wind. Calm conditions below 0.5 m/s are unsupported.

The plume is a steady Gaussian screening scenario with flat terrain and a 2 m release. Values are normalized to 100 m downwind under the same conditions and clipped to 0–1. This normalization cancels the common wind-speed dilution factor; it does not show absolute concentration or speed-dependent travel times. Sensitivity bounds vary direction and stability and are not confidence intervals. Buildings, deposition and chemical fate are not modelled. Neither the historical prior nor the plume establishes current spraying, personal exposure or safety.

## Verification

```sh
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests -q
```

Tests cover geographic rejection, temporal holdout, missing-month handling, source binding, claim-reference checks, workflow sequencing, provider failure, plume geometry and API responses. Mocked agents do not establish live OpenAI/Neon connectivity. Test the configured services separately before deployment.
