import test from 'node:test'
import assert from 'node:assert/strict'
import { normalizeWeather } from '../public/weather-client.mjs'

test('weather bearings wrap and calm winds remain unsupported', () => {
  const w = normalizeWeather({speed_ms:0, from_deg:360, source:'Open-Meteo', valid_at_utc:'2026-11-15T06:00'})
  assert.equal(w.from, 0)
  assert.equal(w.speed, 0)
  assert.equal(w.supported, false)
  assert.match(w.label, /model.*UTC/)
})
test('missing wind never becomes a plausible default', () => {
  for (const speed_ms of [null, undefined, NaN, -1, Infinity]) {
    assert.throws(() => normalizeWeather({speed_ms, from_deg:180}))
  }
})
