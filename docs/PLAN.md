# Build plan: SanD Hacks 2026

## Event rules (don't break these)
- Hacking: **Sat Nov 14, 10:30am → Sun Nov 15, 12:00pm.** The room is closed Sat 10pm – Sun 7am.
- **All code is written during the event.** No commits before 10:30am Sat or after 12:00pm Sun. Nothing is copied
  from earlier projects. Public datasets are fine.
- Submit: 3-minute video + write-up + this GitHub repo on Devpost.
- Judging: Sun 12:30–2:30pm, science-fair style. **Both of us must be at the table** or that judge scores 0.

## Prize tracks we're aiming at
| Track | Our angle |
|---|---|
| Bright Data "Data for Good" | Protecting farmworker families; scrape SprayDays (no public API) |
| Neon best DB / agent backend | Spray + toxicity data in Neon Postgres + PostGIS; agent queries it through MCP |
| Best Use of ElevenLabs | Spoken EN/ES alerts + a phone call the judge can talk back to |
| Most Innovative / Best Overall | MCP agent + live wind and plume map |

## MCP tools
| Tool | Returns | Source |
|---|---|---|
| `find_place(name)` | lat/lon, type (school, home) | schools table / geocoder |
| `upcoming_sprays(lat, lon, radius_mi)` | notices in the next 48h | SprayDays (scraped) |
| `past_sprays(lat, lon, radius_mi, years)` | lbs by chemical, peak months | Neon (PUR subset) |
| `chemical_risk(name)` | toxicity class, health effects, plain-language summary | Neon |
| `wind_forecast(lat, lon, start, end)` | hourly speed and direction | api.weather.gov |
| `drift_check(spray, target, time)` | downwind? distance, risk level, safe window | Gaussian plume (written fresh) |

## Wow features (priority order)
1. **Live tool-call panel:** shows each tool call and result as the agent works (about 1h)
2. **Phone call:** a judge enters their number and gets a call with the alert. They can ask follow-ups ("¿en español?").
   ElevenLabs agent + Twilio (about 3h)
3. **Wind map:** animated wind particles, a 3D plume bending over the school, the school glows red when hit,
   time slider for tomorrow's hours (about 3–4h)
4. **Satellite view:** Map/Satellite toggle (Esri World Imagery, free, no key). Clicking a school or field flies
   down to real imagery with the plume on top and opens a card: the field, crop, upcoming spray, wind window
   (about 1.5h). Stretch on Sunday: Google Photorealistic 3D Tiles with the plume floating over the real building.
5. **Your hometown:** a judge types where they grew up and the map flies there showing 10 years of spraying as
   columns (about 1h)

Skip: login, mobile app, 3D buildings.

## Data scope
Not all 55.7M rows. **One or two counties (e.g. Monterey, Kern), 2022–2023** → fits Neon's free tier (~0.5 GB).
Pre-pick 3 demo schools and check they give interesting answers.

## Schedule
| When | Ioanna | Ved |
|---|---|---|
| Sat 10:30–12:00 | Neon setup, load county subset | **Test SprayDays scraping first** (riskiest part) |
| Sat 12:00–15:00 | MCP server: 6 tools | Wind forecast + drift_check |
| Sat 15:00–18:00 | Agent + web chat + tool-call panel | Map: fly-to, spray columns |
| Sat 18:00–22:00 | ElevenLabs voice + phone call | Wind particles + plume |
| Sun 07:00–10:00 | End-to-end test on 3 demo schools, fix bugs | Polish UI, Spanish answers |
| Sun 10:00–12:00 | Record 3-min video, Devpost write-up | Backup recording, table setup |

Fallback if SprayDays scraping fails: use historical PUR patterns ("this field is usually sprayed in May") plus a
recorded SprayDays example, labelled as such.

## Demo script (90 seconds at the table)
1. Hook: one striking number about spraying near schools, big on screen.
2. "California built an alert system. About 3,700 people use it. Here's why." Show a raw SprayDays notice.
3. Ask Downwind: "Is Lincoln Elementary safe tomorrow?" → tool-call panel lights up → map flies in → plume drifts
   over the school.
4. "Give me your phone number." The judge's phone rings, and they ask a follow-up in Spanish.
5. "Where did you grow up?" → their hometown's 10 years of spraying.

## Table setup
Laptop with the map, phone on a stand for the call demo, printed card with a QR code: "Get alerts for your school".
