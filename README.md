# Downwind

**Someone is always downwind. Downwind tells you when it's you.**

California announces restricted pesticide applications up to 48 hours ahead through
[SprayDays](https://www.cdpr.ca.gov/docs/pesticide_notification_network). Almost nobody uses it:
about 3,700 people signed up in its first year. A notice also only says *"a restricted pesticide will be applied
somewhere in this square mile"*. It doesn't say which way it will drift, how dangerous it is, or whether your kid's
school is in its path.

Downwind is an AI agent that answers one question in plain English or Spanish, by text or a phone call:

> **"Is my kid's school safe tomorrow?"**
>
> *"Tomorrow at 7am, 1,3-D (a soil fumigant) will be applied 0.6 miles from Lincoln Elementary. The wind will carry it toward
> the school. Keep the kids inside until 11."*

Built at **SanD Hacks 2026** (UC San Diego, Nov 14–15).

## How it works

```
 Parent asks (chat, voice, or phone call)
          ↓
      LLM agent
          ↓  calls tools over MCP
 ┌──────────────────────────────────────────────┐
 │            Downwind MCP server               │
 │ find_place("Lincoln Elementary")  schools / geocoder
 │ upcoming_sprays(place, radius)    SprayDays notices
 │ past_sprays(place, years)         Neon Postgres (PUR data)
 │ chemical_risk(name)               Neon (toxicity table)
 │ wind_forecast(place, time)        National Weather Service API
 │ drift_check(spray, target, time)  plume model
 └──────────────────────────────────────────────┘
          ↓
 Answer → text + ElevenLabs voice (EN/ES) + map flies to the school
```

## Stack
- **MCP server:** Python (FastMCP)
- **Database:** [Neon](https://neon.tech) serverless Postgres + PostGIS
- **Data:** California Pesticide Use Reports (public), SprayDays notices, NWS forecasts
- **Voice:** ElevenLabs (text-to-speech + phone agent)
- **Map:** deck.gl wind particles and 3D drift plume

## Team
- Ioanna Gkerdouki
- Ved Panse

See [`docs/PLAN.md`](docs/PLAN.md) for the build plan and [`docs/RESEARCH.md`](docs/RESEARCH.md) for background.
