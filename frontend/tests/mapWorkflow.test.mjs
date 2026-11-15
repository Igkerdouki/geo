import test from 'node:test'
import assert from 'node:assert/strict'
import { sampleGrid } from '../public/map-workflow.mjs'

const result={status:'complete',grid:{size:2,extent_m:100,values:[0,1,0,1]}}
test('both renderers interpolate the same east/north field',()=>{
  assert.equal(sampleGrid(result,0,0),.5)
  assert.equal(sampleGrid(result,50,50),1)
  assert.equal(sampleGrid(result,-50,-50),0)
  assert.equal(sampleGrid(result,51,0),0)
})
test('unavailable or calm results never retain old colors',()=>{
  assert.equal(sampleGrid(null,0,0),0)
  assert.equal(sampleGrid({...result,status:'calm'},0,0),0)
})
