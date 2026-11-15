import { useState } from 'react'
import { downloadJSON, simulationFromWorkflow } from './workflowClient.mjs'

const compact = value => JSON.stringify(value, (key, item) => ['grid', 'parcels', 'snapshots'].includes(key) ? '(Geographic data available in JSON export)' : item, 2)
export default function WorkflowResults({ results, events, running, error, onShow }) {
  const [frames,setFrames]=useState({})
  const latest = {}
  events.filter(e => e.type === 'agent').forEach(e => { latest[e.agent] = e.status })
  return <div className="geo-result-content">
    <div className="geo-tabs">{['orchestrator', 'location', 'data', 'simulation', 'verifier'].map(role => <span key={role}>{role} · {latest[role] || (running ? 'waiting' : '—')}</span>)}</div>
    {error && <p className="geo-error" role="alert">{error}</p>}
    {running && <p role="status">Agents are investigating. Tool results appear below as they finish.</p>}
    {results.map((result, index) => <section key={result.id || index}>
      <div className="geo-section-heading"><h3>{result.request?.place || result.location?.matched || `Place ${index + 1}`} · {result.status}</h3><button onClick={() => downloadJSON(result, `askgaia-workflow-${result.id}.json`)}>Download JSON</button><button onClick={() => onShow(result)}>Show on map</button></div>
      {result.plan && <p className="geo-muted">Plan: {result.order.join(' → ')}. {result.plan.reason}</p>}
      {simulationFromWorkflow(result)?.snapshots && <label>Spray timeline · {simulationFromWorkflow(result).snapshots[frames[result.id] || 0]?.minute} minutes<input aria-label={`Spray timeline for ${result.request?.place || result.id}`} type="range" min="0" max={simulationFromWorkflow(result).snapshots.length-1} value={frames[result.id] || 0} onChange={e=>{const frame=+e.target.value;setFrames(f=>({...f,[result.id]:frame}));onShow(result,frame)}}/></label>}
      {['observed', 'modelled', 'uncertain'].map(label => <section key={label}><h3>{label === 'observed' ? 'Observed / recorded evidence' : label === 'modelled' ? 'Modeled scenarios' : 'Uncertain'}</h3>{(result[label] || []).length ? result[label].map((claim, i) => <article className="geo-finding" key={i}><div><p>{claim.text}</p><small>{claim.verification}</small><div>{claim.evidence_ids.map(id => <a key={id} href={`#evidence-${result.id}-${id}`}> [{id}] </a>)}</div></div></article>) : <p className="geo-muted">No supported statements returned in this category.</p>}</section>)}
      {(result.warnings || []).map((warning, i) => <p className="geo-muted" key={i}>{warning}</p>)}
      <p className="geo-muted">{result.epa_status}</p>
      <details><summary>Agent reports</summary>{Object.entries(result.agents || {}).map(([role, report]) => <article key={role}><h3>{role} · {report.status}</h3><p>{report.summary || report.error}</p>{report.limitations?.map((l,i) => <p key={i}>{l}</p>)}</article>)}</details>
      <details><summary>Sources and tool evidence ({result.evidence?.length || 0})</summary>{(result.evidence || []).map(e => <details className="geo-source" id={`evidence-${result.id}-${e.id}`} key={e.id}><summary>{e.agent} / {e.tool} · {e.status} · {e.id}</summary><pre className="gaia-json">{compact(e)}</pre></details>)}</details>
      <p className="geo-footnote">Recorded use, station measurements, weather models and hypothetical spray transport are distinct. These results do not establish personal exposure or safety.</p>
    </section>)}
    {results.length === 2 && <p className="geo-footnote">Comparison uses the same years, month and radius. Differences in recorded pesticide use do not rank the places by exposure or safety.</p>}
    <details open={running}><summary>Live research trail</summary><div className="geo-trace">{events.filter(e => e.type !== 'heartbeat').map((e, i) => <div key={i}><div><strong>{e.agent || e.evidence?.agent || e.type} · {e.tool || e.evidence?.tool || e.status || ''}</strong><p>{e.type === 'plan' ? e.plan.reason : e.evidence?.error || e.message || e.evidence?.status || ''}</p><small>{e.time}</small></div></div>)}</div></details>
  </div>
}
