# Geo Project Progress

## Data Downloads

### PUR Data (Pesticide Use Reports)
- [x] pur2023.zip (248 MB) - Downloaded & unzipped
- [x] pur2022.zip (155 MB) - Downloaded
- [x] pur2021.zip (163 MB) - Downloaded
- [x] pur2020.zip (179 MB) - Downloaded
- [x] pur2019.zip (176 MB) - Downloaded
- [ ] pur2018.zip (175 MB) - Downloading...
- [ ] pur2017.zip (165 MB) - Downloading...
- [ ] pur2016.zip (170 MB) - Downloading...
- [ ] pur2015.zip (166 MB) - Downloading...
- [ ] pur2014.zip (148 MB) - Downloading...

Source: https://files.cdpr.ca.gov/pub/outgoing/pur_archives/

### Other Data Sources
- [ ] CalEnviroScreen 4.0 - Not downloaded
- [ ] California School Directory - Not downloaded
- [ ] OpenWeatherMap API key - Not set up

---

## Local Setup

### PostgreSQL
- [x] Installed via Homebrew (postgresql@15)
- [x] Service started
- [x] Database created: `geo`
- [ ] PostGIS extension - Installing...
- [ ] Tables created - Not done
- [ ] PUR data loaded - Not done

### Render (Production)
- [ ] PostgreSQL created on Render
- [ ] Connection string saved
- [ ] PostGIS enabled
- [ ] Data loaded

---

## GitLab

- [x] SSH key created (~/.ssh/id_ed25519_gitlab)
- [x] SSH key added to GitLab
- [x] Cloned brainstorming repo
- [x] Pushed Geo_README.md to geo-proposal branch
- [x] Added system architecture diagram
- [ ] Create geo project repo (private)

---

## Code Progress

### Backend (FastAPI)
- [ ] Project structure created
- [ ] /api/drift endpoint
- [ ] /api/sprays endpoint
- [ ] /api/exposure endpoint
- [ ] /api/dosage endpoint
- [ ] /api/alerts endpoint
- [ ] /api/weather endpoint

### Frontend (React + Vite)
- [ ] Project initialized
- [ ] MapLibre setup
- [ ] Spray markers
- [ ] Drift overlay
- [ ] Sidebar/filters

### ML Models
- [ ] Drift predictor (Gaussian plume)
- [ ] Dosage optimizer (XGBoost)
- [ ] Risk scorer

---

## Files Created

- ~/Desktop/Geo_README.md
- ~/Desktop/Geo_Build_Plan.txt
- ~/Desktop/Geo_Data_Sources.txt
- ~/Desktop/Geo_User_Stories.txt
- ~/Desktop/ESPINA_email.txt
- ~/Desktop/brainstorming/Geo_README.md (pushed to GitLab)
- ~/Desktop/brainstorming/geo_mockup.html
- ~/Desktop/brainstorming/geo_architecture.html
- ~/Desktop/geo_data/ (PUR data folder)

---

## Team

**Runtime Terror** - SDSC RDS Summer 2026

| Dev | Role |
|-----|------|
| Ioanna | Backend + Drift Model Lead |
| Dev 2 | Frontend Lead |
| Dev 3 | Frontend Support |
| Dev 4 | Backend + Data |
| Dev 5 | Integrations |

---

## Next Steps

1. [ ] Set up Render PostgreSQL
2. [ ] Load PUR data into database
3. [ ] Create FastAPI project structure
4. [ ] Build /api/sprays endpoint first
5. [ ] Set up React + Vite frontend

---

Last updated: June 24, 2026

## Evidence workspace implementation — November 14, 2026

- Added the default investigation UI; preserved the old dashboard at `/explorer`.
- Implemented OpenAI structured evidence analysis, Bright Data SERP + Web Unlocker adapters, direct public guidance retrieval fallback, exact-excerpt validation, source version comparisons, saved investigations, JSON and print-to-PDF packets.
- Added a stdio MCP server exposing seven shared evidence tools.
- Added optional Neon/Postgres persistence, with SQLite for local development; historical county queries do not claim school proximity.
- Disabled the legacy synthetic spray stream by default. Wind UI is explicitly an uncalibrated illustration.
- Verification: backend tests and frontend build with compatible locally cached dependencies. Live provider calls require network access. Bright Data configuration and Neon connection were not present during implementation; Mastra is not integrated.

### 3D reference UI

- Ported the supplied concept's Three.js neighborhood into a React component, with orbit/zoom, procedural buildings and trees, school marker, relative plume layer, and wind trails.
- Reworked the default workspace into a dark full-viewport scene with compact research and wind overlays, a collapsible evidence drawer, and a separate geographic-map view. Removed promotional banner text.
- Added animation pause/reset, reduced-motion handling, mobile controls, resize observation, and WebGL resource cleanup. Replaced per-particle full-building scans with a spatial lookup.
- Removed the concept's school risk percentage; retained visible illustrative/model limitations.
- Frontend production build passed using locally cached compatible dependencies. Preview assets refreshed. Browser visual verification is still unavailable in this restricted session.


## Neon evidence persistence and credential repair

- Fixed surplus boundary quote in local Bright Data API key; dotenv now parses all configured provider keys. SERP zone is `serp_api`.
- Added transactional versioned case snapshots and history endpoints, using Neon/Postgres via `DATABASE_URL` or SQLite locally. Trace-only saves are deduplicated.
- Separated historical PUR database configuration (`PUR_DATABASE_URL`) from Neon evidence storage.
- 19 backend tests pass, including historical snapshot preservation and API source-text redaction.
- Neon remains unconnected: `DATABASE_URL` is absent. Live Bright Data check failed with ConnectError in restricted runtime; credential validity and zone activation are not verified remotely.

## AskGaia rename and hosting

- Renamed visible app, explorer landing page, page title, evidence downloads, and MCP/API display names to AskGaia. Existing internal CSS, database names, and GEO_* configuration stay compatible.
- Vercel team: team_XQsbqm3WNzgg2GDkLIqmV0hq; project: prj_Vp8SiCePOGFRmxivPhWHdlB4VSCO (askgaia).
- Added api/index.py, vercel.json, root Python requirements and .vercelignore. Deployment excludes local secrets and data.
- Cloud investigations require DATABASE_URL and await jobs inside the request. 21 backend tests pass; renamed frontend build succeeds using documented offline-compatible toolchain.
- Automatic approval review blocked sending OpenAI/Bright Data credentials to Vercel; explicit destination approval remains required. No credentials transferred.
- askgaia.co registry lookup returned available. Vercel domain associations for apex and www are configured; www redirects to apex. Registrar redemption and authoritative DNS still pending. No registrar/browser tool is available for the sponsor checkout.
- Production deployment READY: dpl_CrHUaYwGJGfoooXBF1DSsN8JMMfJ. URL: https://askgaia-ved-panses-projects.vercel.app . Homepage, /health, and /api/investigations/capabilities all returned HTTP 200 through authenticated Vercel fetch. No browser rendering check available.
- Hosted capabilities confirm provider keys absent and Neon connection needed. Vercel authentication protection remains enabled for the Vercel URL.
- Required registrar DNS from Vercel lookup: apex A records 216.198.79.1 and 64.29.17.1; www CNAME 50bf00d031a6219e.vercel-dns-017.com. DNS still misconfigured pending registration/setup.

## City search and geographic wind overlay

- Default workspace is now City + wind: Open-Meteo geocoding with disambiguated city choices, OpenFreeMap vector tiles, MapLibre 3D building extrusions, pan/orbit/zoom, and current model wind at city coordinates.
- Buildings use mapped footprints and render heights; missing heights fall back to 8 m. This is not photogrammetry or verified building geometry.
- Geographic wind particles use meteorological FROM bearings, project correctly with map rotation/pitch, and animate at a disclosed 12x scale. One 10 m city-level wind sample; no airflow around buildings or pesticide concentration inferred.
- Wind retrieval is independent of the legacy simulated weather endpoint and of provider/Neon credentials. Errors remain errors; no synthetic fallback. Source timestamp, pause and refresh available; reduced motion starts paused.
- Procedural scene retained as Illustrative lab and lazy-loaded. Corrected evidence panel CSS class names accidentally changed during branding.
- Five cardinal-direction/calm-wind tests pass. Browser visual/provider integration check remains unavailable in this environment.

## City 3D readability correction

User screenshot showed barely visible low-rise extrusions against a black basemap. Updated city view from zoom 15/pitch 60 to zoom 17/pitch 65, set explicit white directional lighting, opaque pale building volumes and vertical shading, softened the ground/road colors, and hid dense symbol labels. Zero/missing render heights now use the disclosed 8 m fallback. Added Reset 3D view. Production frontend build and diff checks pass; browser rendering remains unverified here.

## Public demo access

Removed Vercel SSO deployment protection after the user encountered a Request Sent gate despite the temporary sharing link. Vercel confirms ssoProtection.enabled=false. Use the normal project URL without a share token: https://askgaia-ved-panses-projects.vercel.app/ . Provider secret transfer remains unapproved and unchanged.

## Compact UI and typography refresh

- Consistent system sans-serif type, restrained weights/spacing, slim header; removed visible tagline and workspace status badge.
- City search now a compact top-left field. Wind is a single-line disclosure with controls/source details on demand; map guidance is another small disclosure.
- Research and evidence controls are compact bottom actions; Map/Lab switch centered. Removed provider configuration clutter from the research form.
- Mobile layout uses smaller controls and an accessible icon-only research action to avoid overlap. Map credits remain available through compact attribution.
- Production frontend build passes; no browser visual verification available.

## Combine teammate work on main

Integrated Ioanna's six spatial tools from 8f48e13005afed198b38b6e2cfbbc858542d27aa into the shared 13-tool MCP server, preserving her original launch command via backend/mcp_server.py. Moved spatial implementations to app/spatial_tools.py, reused the existing MCP SDK, added lazy psycopg 3 database access, and validated radius/stability inputs. Added AGENTS.md ownership guidance: Ioanna handles UI; Ved/Codex handles logic/data/backend. Backend suite: 27 passed; wind suite: 5 passed. Existing frontend build passed in the offline-compatible toolchain. GitHub integration preserves Ioanna's commit as parent; the sandbox prevents updating the local .git metadata.

Publishing attempt was blocked: GitHub create_tree returned 403 Resource not accessible by integration even though repository metadata reports account push access. Remote main remains at Ioanna's 8f48e13. Local .git metadata is read-only in this environment. scripts/publish-reviewed-merge.sh prepares a normal-terminal path with remote-head and local-file checks, preserves both histories, and never force-pushes.
