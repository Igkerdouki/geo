# Background research

## SprayDays California
- Launched March 24, 2025 by the California Department of Pesticide Regulation (CDPR). It gives notice before
  **restricted material** pesticides are applied in production agriculture, at about square-mile resolution, in
  English and Spanish.
- First year: ~72,000 website views, **~3,700 text/email sign-ups**.
- Advocacy groups have published concerns about usability and coverage.
- No public API found, so the data has to be scraped. Contact: spraydays@cdpr.ca.gov

Sources:
- https://www.cdpr.ca.gov/docs/pesticide_notification_network
- https://spraydays.cdpr.ca.gov/Home/About
- https://www.cdpr.ca.gov/2025/03/24/state-launches-spraydays-california-a-first-of-its-kind-notification-system-for-pesticide-applications
- https://www.cdpr.ca.gov/wp-content/uploads/2026/03/spraydays_first_annual_status_update_appendix.pdf
- https://www.pesticidereform.org/wp-content/uploads/2026/02/FINAL-Challenges_Concerns-SprayDays-Feb-2026.pdf
- https://www.pesticidereform.org/wp-content/uploads/2026/05/20260501-Spraydays-First-Annual-Report-Comment-Letter.pdf

## Pesticide Use Reports (PUR)
- CDPR's public record of agricultural pesticide applications, located by section (≈1 square mile, the
  township/range/section grid). Yearly downloads: https://www.cdpr.ca.gov/docs/pur/purmain.htm
- Precision caveat to state honestly: "near the school" means within about a mile, not exact fields.

## Wind forecasts
- National Weather Service API, free, no key: `https://api.weather.gov/points/{lat},{lon}` → hourly forecast URL.

## Drift model
- Gaussian plume dispersion with Pasquill–Gifford stability classes (A–F) from wind speed and time of day.
  Written fresh for this project.

## Neon
- Serverless Postgres, PostGIS supported, free tier ~0.5 GB. Also has an official MCP server
  (useful for an open-ended "research mode").

## Why this matters
- Farmworker communities and rural schools sit next to treated fields. Chlorpyrifos (a neurotoxin linked to
  developmental harm in children) was banned in California in 2020 after years of use near homes and schools.
