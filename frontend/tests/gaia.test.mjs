import test from 'node:test';import assert from 'node:assert/strict';
import {validContext,scenarioFrom,reportSummary} from '../public/gaia-widget.mjs';
test('location context rejects invalid coordinates',()=>{assert.ok(validContext({location:{name:'School',lat:36,lon:-120}}));assert.ok(!validContext({location:{name:'School',lat:NaN,lon:-120}}))});
test('only completed source-bound simulations accompany reports',()=>{assert.equal(scenarioFrom({status:'no_source',scenario:{speed:2}}),null);assert.deepEqual(scenarioFrom({status:'complete',scenario:{source_lat:36,source_lon:-120}}),{source_lat:36,source_lon:-120})});
test('unavailable records do not turn into a zero watch baseline',()=>{assert.equal(reportSummary({evidence:[{tool:'pur_records',status:'unavailable'}]}),null);assert.equal(reportSummary({context:{start_year:2020,end_year:2024},evidence:[{tool:'pur_records',status:'complete',result:{total_lbs:0,chemicals_found:0}}]}).reported_lbs,0)});
