import test from 'node:test'
import assert from 'node:assert/strict'
import { windVector } from '../src/windVector.mjs'
for (const [bearing, east, north] of [[0,0,-5],[90,-5,0],[180,0,5],[270,5,0]]) {
  test(`wind from ${bearing} travels downwind`, () => {
    const vector = windVector(bearing, 5)
    assert.ok(Math.abs(vector.east-east)<1e-10)
    assert.ok(Math.abs(vector.north-north)<1e-10)
  })
}
test('calm wind has no motion', () => {
  const v=windVector(253,0); assert.equal(Math.hypot(v.east,v.north),0)
})
