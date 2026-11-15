import test from 'node:test'
import assert from 'node:assert/strict'
import { readNDJSON, simulationFromWorkflow } from '../src/workflowClient.mjs'
test('stream decoder preserves split UTF-8 and final unterminated event',async()=>{
  const bytes=new TextEncoder().encode('{"type":"agent","text":"µg"}\n{"type":"result"}')
  const chunks=[bytes.slice(0,25),bytes.slice(25,26),bytes.slice(26)]
  let i=0;const events=[]
  await readNDJSON({read:async()=>i<chunks.length?{value:chunks[i++],done:false}:{done:true}},e=>events.push(e))
  assert.equal(events[0].text,'µg');assert.equal(events[1].type,'result')
})
test('failed simulation evidence cannot replace successful model result',()=>{
  const result={evidence:[{tool:'simulate_grid',status:'complete',result:{grid:'valid'}},{tool:'simulate_spray_event',status:'error'}]}
  assert.deepEqual(simulationFromWorkflow(result),{grid:'valid'})
})
