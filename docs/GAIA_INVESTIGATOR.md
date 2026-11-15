# Gaia investigator and action center

Implemented across the React routes and standalone town pages through `frontend/public/gaia-widget.mjs`. The top-level widget receives the selected place, coordinates, and completed simulation. Changing location clears chat and invalidates the report. Reporting radius and years are editable.

## Checklist

- [x] Location-aware Ask Gaia conversation with bounded, real MCP calls.
- [x] Pesticide records, chemical profiles, weather, schools, and annual trends.
- [x] Evidence IDs, publisher links, tool status, uncertainty, and follow-up questions.
- [x] Map actions use server-derived coordinates and shared backend scenarios.
- [x] Fresh environmental reports saved as immutable workflow snapshots in Neon.
- [x] PDF and JSON downloads, plus a source-linked text summary for sharing.
- [x] Editable county-authority inquiry with official contact directory; no automatic sending.
- [x] Browser-local watch access tokens with manual checks and preserved baselines on source failure.
- [x] Durable automatic watches, evidence-change alerts, and in-app unread badges.

## Backend API

`POST /api/gaia/chat` accepts selected location, radius, year window, optional completed map scenario, message, and bounded conversation history. Coordinates and dates are constrained server-side; model-selected tools cannot change the location. Unsupported evidence IDs are discarded. Chat history stays in the browser tab and is sent to the configured AI provider, but is not saved in report history.

`POST /api/gaia/reports` fetches fresh evidence independently of chat and stores a report snapshot. `GET /api/gaia/reports/{id}`, `/pdf`, and `/inquiry` retrieve JSON, PDF, and inquiry respectively. Reports contain no conversation or symptom history. Report URLs are bearer links: do not include private personal information.

Historical section-level applications are not current spraying or measured exposure. Weather is a model estimate. Dispersion is a hypothetical relative index. School data comes from OSM; if Overpass fails, the bounded OpenFreeMap POI fallback clearly states its smaller coverage and incompleteness. Chemical annotations may be incomplete and require publisher verification.

## Runtime

Uses the existing configured Gemini provider and MCP subprocesses. Subprocesses inherit environment configuration so proxy-backed HTTPS works. Optional `GEO_NEON_HTTP=1` enables Neon HTTPS SQL for hosts where PostgreSQL TCP is unavailable; default remains direct PostgreSQL. Credentials remain server-side in ignored environment files.

Pesticide/trend queries deduplicate intersecting PLSS section IDs before aggregation to avoid counting duplicate section geometries twice.

## Verification

68 backend tests and 14 frontend tests passed; Vite production build passed. Live Neon/MCP chat and report generation verified for Biola-Pershing Elementary. The real three-page PDF was rendered and visually inspected. Hypothetical allergy prompt requested onset, indoor/outdoor context, and location pattern without diagnosing or attributing causation. All reports distinguish missing evidence from zero recorded use.

## Automatic alerts

Enable automatic alerts under Watching. The beta supports 20 active automatic watches. The server checks historical recorded-use totals and chemical counts, plus weather-model wind; changes of at least 2 m/s or 45 degrees (both winds >=1 m/s) generate an evidence-linked alert. It never interprets these as confirmed spraying or exposure. Source outages preserve prior baselines. Alerts and watch state persist in Neon; bearer access tokens stay in browser storage. Stop/remove disables future checks. Clearing browser storage loses access to existing watches.

A long-running backend starts its worker automatically. Vercel requires `CRON_SECRET` and the daily cron configured in vercel.json (compatible with the current Hobby plan). The authenticated endpoint claims up to 20 due watches with database leases; production watches are checked daily; long-running local servers check hourly. In-app alerts are fetched every minute and on opening Watching. They accumulate while the tab is closed; no email, push permission, or external message is sent. Production enablement fails explicitly if the scheduler secret is missing.
