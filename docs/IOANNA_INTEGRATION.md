# Ioanna frontend integration — 2026-11-15 UTC

Imported source: `Igkerdouki/geo`, branch `ioanna`, commit `f0359350baf73458c7fd908f08156eff2650943c`.
Base: `80dedf118d6e8427dca575d39c44b4ff41938ac3`.

The remote files were retrieved through the GitHub connector and a GitHub archive, then merged with the existing working files. The repository metadata remains at the original base: this environment denied writes to `.git/FETCH_HEAD`. No commit, branch update, push, or deployment was performed. Preserve the existing staged IDE files when finalizing Git history.

## Integrated

- Ioanna's landing page, Earth view, town models, statewide California page, architecture page, reference designs and screenshots.
- Existing backend workflow, transport, chat and evidence tools preserved alongside Ioanna's place, county and grid endpoints.
- Root opens the new landing page. `/earth`, `/investigate` and `/explorer` retain their routes.
- Place selection automatically loads current Open-Meteo wind through the backend. Calm/unavailable weather does not reuse old wind as current data.
- Satellite and town plume colors/readouts use one deterministic backend grid from `/api/workflows/map-simulation`. The parent sends the same result ID, source, target and wind to the town iframe. Town controls update the parent scenario. Animated puffs and lighting remain illustrative.
- Standalone town pages select their source through `/api/workflows/map-context` and use the same simulation endpoint.
- Both views offer the four-agent investigation stream with the selected coordinates and scenario. Reviews identify the simulation snapshot; missing provider results are shown explicitly.
- Ingredient transport/timeline link carries the selected coordinates to the investigation workspace.
- Town rendering tolerates empty geometry arrays and absent historical pesticide sources. No source means no modeled plume; buildings and weather remain available.
- Missing optional water-observation tables do not prevent town geometry from loading.
- Added vector-tile and HTTP SOCKS dependencies in both requirements files.

## Validation

- Frontend production build passes.
- 11 frontend tests pass; all static HTML module scripts pass syntax checks.
- 62 backend tests pass when run from `backend` with `.venv/bin/python -m pytest tests -q`.
- Live local API: Neon historical sections, town geometry, statewide grid and Open-Meteo weather returned successfully.
- Browser: new landing page and Google tiles load; Biola model renders; searching Salinas resolves the location; La Jolla renders 1,942 buildings with current wind and an explicit no-source state.
- Environment files remain ignored and untracked.

## Limits

No automatic confirmed spraying feed or field validation has been added. Historical use, weather-model estimates, shared backend map dispersion, and ingredient transport scenarios are separate. The production deployment has not been updated.

## Shared-map verification

- Browser: Biola model preset changed both views to 5.2 m/s, stability C, with backend result `5ef3b1c36a62a07618d6`.
- Browser: La Jolla still renders 1,942 buildings and current weather, with no inferred plume when source records are absent.
- Selected map coordinates are polygon-validated before the agent workflow and cannot be replaced by a geocoder guess.
- Provider rejected `gemini-2.5-flash` as retired. Its suggested replacement, `gemini-3.8-flash`, and `gemini-3.7-flash` returned demand-related HTTP 503 errors. Verified structured responses from `gemini-3.5-flash` and `gemini-3.5-flash-lite`; configured these as primary and bounded same-provider fallback. Authentication/schema failures do not trigger fallback. Results record successful model choices.
- Installed the already-declared `psycopg2-binary` dependency in the backend environment. Actual server history reads, workflow writes, and ID-based readback now work against Neon.
- Historical seasonal model remains untrained; reviews must explicitly report this missing evidence rather than invent a prediction.

### Provider and persistence repair verification

Live workflow `8ac3918163e147cbb40de7753bb84f14`: location, data, simulation, and verifier all completed. Returned one verified observed claim and two modelled claims; saved to Neon and successfully retrieved through `/api/workflows/history/{id}`. The same-provider fallback was exercised successfully. Overall status remains partial because the seasonal prior is untrained and no uncertain claims survived verification. No provider or history-storage failure remained in this run. Backend suite: 62 passing tests.

## Latest import

Merged ioanna commit `b093865f61746094b75ef9b3af8ba24b4ad74fe3` using a three-way file merge from the prior imported commit. Preserved Gaia/backend integration while adding the no-Google-key town fallback, updated architecture and landing pages, and Devpost screenshots. Git metadata remains unchanged because it is read-only.

Latest check: ioanna `25050c0fa3f648a7befbd9b2b6893c523a3f7420` adds only `docs/devpost/7-neon-spatial-query.png`; imported it. The frontend code already matches her latest source plus our integration fixes.
