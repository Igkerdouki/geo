# Spray event scenarios

`POST /api/workflows/simulate-spray` adds time-resolved passive-tracer scenarios
without changing the UI. Snapshots contain GeoJSON parcel centers every five
minutes (and at the final minute), plus per-ingredient airborne/deposited/degraded
mass budgets. The Simulation panel renders these geographic snapshots with playback on the existing map. This is an illustrative transport
baseline, not a calibrated pesticide drift or exposure prediction.

Example body (deliberately fictional ingredient and assumptions):

```json
{
  "source_lat": 36.7378,
  "source_lon": -119.7871,
  "start_at": "2026-11-15T04:00:00Z",
  "event_kind": "hypothetical",
  "event_source": "User-created demo",
  "location_uncertainty_m": 50,
  "duration_minutes": 10,
  "horizon_minutes": 60,
  "ingredients": [{
    "name": "Example tracer",
    "applied_kg": 1,
    "airborne_fraction": 0.01,
    "airborne_half_life_minutes": 30,
    "deposition_half_life_minutes": 15,
    "assumption_source": "Illustrative user assumptions, not measured properties"
  }],
  "wind": [
    {"minute": 0, "speed_ms": 2, "from_deg": 270},
    {"minute": 30, "speed_ms": 3, "from_deg": 300}
  ]
}
```

Omit `wind` to use Open-Meteo hourly forecast winds matched to the event's
timezone-aware timestamp. Unsupported dates and provider failures are rejected;
there is no synthetic fallback. Explicit winds are held constant until the next
step. Forecast winds are weather-model estimates at 10 m, not field measurements.

Each ingredient releases `applied_kg * airborne_fraction / duration_minutes`
per minute. New parcels have half a minute of transport at the first step, then
full-minute steps. Competing first-order deposition and degradation conserve the
released airborne mass. Unreleased/non-airborne application mass is outside the
transport budget. Missing half-lives disable that removal process. Coordinates
use a local flat-earth approximation. Calm winds keep parcels stationary; they
do not establish absence of atmospheric dispersion.

## Event sourcing and next integration

California SprayDays publishes **scheduled restricted-material applications**,
active ingredients and approximate one-square-mile sections. Scheduled start
times can shift by up to four days and events may be cancelled. It is not an
actual-start sensor or a complete feed of all pesticide use:
https://spraydays.cdpr.ca.gov/Home/About

This change does not ingest SprayDays automatically, persist reports, or verify
reported events. `scheduled` and `reported` describe caller-supplied provenance.
Exact live starts require a trusted applicator/equipment reporting integration.
Do not substitute a section center for a known nozzle location without recording
uncertainty. Current uncertainty is metadata only, not an uncertainty envelope.

Neon historical use supports seasonal activity estimates, not identification of
current spray events or training chemical fate without relevant observations.
To graduate beyond this baseline, obtain release fraction, droplet distribution,
equipment/release height and formulation-specific fate measurements; validate
against observed drift/deposition. Temperature, humidity, rain, turbulence,
terrain, volatilization and droplet physics are not yet modeled. Ingredients
share paths unless a future validated transport model gives a physical reason
for different trajectories. Do not render these points as a plume boundary or
use their masses as concentrations or health thresholds.

## Extended implementation

See IMPLEMENTATION_STATUS.md for extended physics, uncertainty, measured-sample evaluation, event import/reporting contracts, and the precise remaining external blockers. Extended physics is optional and still unvalidated; the baseline request above remains a passive-tracer scenario.
