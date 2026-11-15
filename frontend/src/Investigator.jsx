import { lazy, Suspense, useEffect, useRef, useState, useCallback } from 'react'
import { ArrowUpRight, ArrowRight, Search, Globe2, MapPin, Layers, BookOpen, Fingerprint, Download, RefreshCw, X, Plus, Check, AlertCircle, Loader2, Wind, ChevronRight, Terminal, History } from 'lucide-react'
import './Investigator.css'
const ThreeScene = lazy(() => import('./ThreeScene'))
import CityMap from './CityMap'
import WorkflowResults from './WorkflowResults'
import ScenarioPanel from './ScenarioPanel'
import { api, streamInvestigation, simulationFromWorkflow } from './workflowClient.mjs'
import './WorkflowControls.css'
import './SceneWorkspace.css'
import './MinimalUI.css'

const API = import.meta.env.VITE_API_URL || '/api'
async function request(path, options) {
  const response = await fetch(API + path, { ...options, headers: { 'Content-Type': 'application/json', ...options?.headers } })
  if (!response.ok) { const error = await response.json().catch(() => ({})); throw new Error(typeof error.detail === 'string' ? error.detail : `Request failed (${response.status})`) }
  return response.json()
}
const post = body => ({ method: 'POST', body: JSON.stringify(body) })
const date = value => value ? new Date(value).toLocaleString([], {month:'short', day:'numeric', hour:'2-digit', minute:'2-digit'}) : '—'
const safeLink = url => /^https:\/\//i.test(url || '') ? url : '#'

export default function Investigator() {
  const params = new URLSearchParams(window.location.search)
  const latitude = Number(params.get('lat')), longitude = Number(params.get('lon'))
  const initialLocation = params.has('lat') && params.has('lon') && Number.isFinite(latitude) && Number.isFinite(longitude) && latitude >= 32 && latitude <= 42.5 && longitude >= -125 && longitude <= -114 ? {lat:latitude,lon:longitude,matched:params.get('place') || 'Selected place'} : null
  const [caps,setCaps]=useState(null), [connectionError,setConnectionError]=useState('')
  const [place,setPlace]=useState(new URLSearchParams(window.location.search).get('place') || 'Chualar Elementary'), [question,setQuestion]=useState('What do public records establish about pesticide use around this school, and what evidence is missing?')
  const [suggestions,setSuggestions]=useState([]), [caseData,setCase]=useState(null), [history,setHistory]=useState([])
  const [error,setError]=useState(''), [pending,setPending]=useState(false), [tab,setTab]=useState('findings'), [selected,setSelected]=useState(null)
  const [showHistory,setShowHistory]=useState(false), [sourceUrl,setSourceUrl]=useState(''), [scenario,setScenario]=useState(params.get('scenario') === '1'), [direction,setDirection]=useState(225), [speed,setSpeed]=useState(4)
  const [view,setView]=useState('map'), [evidenceOpen,setEvidenceOpen]=useState(params.get('scenario') === '1'), [researchOpen,setResearchOpen]=useState(false)
  const [workflowResults,setWorkflowResults]=useState([]), [workflowEvents,setWorkflowEvents]=useState([]), [workflowMode,setWorkflowMode]=useState(false)
  const [comparePlace,setComparePlace]=useState(''), [compareEnabled,setCompareEnabled]=useState(false)
  const [mapLocation,setMapLocation]=useState(initialLocation || {lat:32.7157,lon:-117.1611}), [focus,setFocus]=useState(initialLocation), [overlay,setOverlay]=useState(null)
  const [sprayScenario,setSprayScenario]=useState(null), [attachScenario,setAttachScenario]=useState(false)
  const [workflowHistory,setWorkflowHistory]=useState([])
  useEffect(()=>{if(mapLocation?.lat!=null)window.postMessage({type:'gaia-context',context:{location:{name:mapLocation.matched || place,lat:mapLocation.lat,lon:mapLocation.lon},scenario:null}},location.origin)},[mapLocation])
  const streamController=useRef(null)
  useEffect(()=>()=>streamController.current?.abort(),[])
  const showSimulation=useCallback((data,frameIndex=0)=>{
    const source=data.event?{lat:data.event.source_lat,lon:data.event.source_lon}:data.source
    if(source)setFocus(previous=>previous?.lat===source.lat&&previous?.lon===source.lon?previous:{lat:source.lat,lon:source.lon,id:Date.now()})
    const frame=data.snapshots?.[frameIndex]
    setOverlay(data.grid || (frame?{type:'FeatureCollection',features:[...(data.uncertainty?.extent?.features||[]),...(frame.footprints?.features||[]),...frame.parcels.features]}:null))
  },[])
  const showFrame=useCallback((frame,data)=>{setOverlay({type:'FeatureCollection',features:[...(data.uncertainty?.extent?.features||[]),...(frame.footprints?.features||[]),...frame.parcels.features]})},[])
  function showWorkflow(result,frameIndex=0){
    const simulation=simulationFromWorkflow(result)
    if(simulation)showSimulation(simulation,frameIndex);else {setOverlay(null);if(result.location)setFocus({...result.location,id:Date.now()})}
    setView('map')
  }
  const running=pending || ['running','queued'].includes(caseData?.status)
  const mounted=useRef(true)
  useEffect(() => {if(!selected)return; const close=e=>{if(e.key==='Escape')setSelected(null)};document.addEventListener('keydown',close);return()=>document.removeEventListener('keydown',close)},[selected])
  useEffect(() => { mounted.current=true; request('/investigations/capabilities').then(setCaps).catch(() => setConnectionError('Backend not connected. Start the AskGaia API on port 8001.')); request('/investigations').then(setHistory).catch(()=>{}); return () => {mounted.current=false} }, [])
  useEffect(() => {
    if (!caseData?.id || !['running','queued'].includes(caseData.status)) return
    let stopped=false
    const poll=async () => {try {const next=await request(`/investigations/${caseData.id}`); if (!stopped) {setCase(next);setError('')}} catch(e) {if(!stopped)setError(e.message)} }
    const timer=setInterval(poll,1800); return () => {stopped=true;clearInterval(timer)}
  }, [caseData?.id,caseData?.status])
  async function begin(e) {
    e.preventDefault();setError('');setPending(true);setSelected(null);setCase(null);setEvidenceOpen(true);setResearchOpen(false);setScenario(false);setWorkflowMode(true);setWorkflowResults([]);setWorkflowEvents([]);setOverlay(null)
    streamController.current?.abort();const controller=new AbortController();streamController.current=controller
    try {
      const places=compareEnabled?[place,comparePlace]:[place]
      for(const name of places){
        const body={place:name,question,start_year:2020,end_year:2024,month:new Date().getMonth()+1,radius_km:1.25,dynamic_planning:true,...(attachScenario&&sprayScenario?{spray_scenario:sprayScenario}:{})}
        const result=await streamInvestigation(body,event=>{
          if(event.type==='result')return
          if(mounted.current)setWorkflowEvents(items=>[...items,event])
        },controller.signal)
        if(mounted.current){setWorkflowResults(items=>[...items,result]);showWorkflow(result)}
      }
    } catch(e){if(e.name!=='AbortError')setError(e.message);else setError('Investigation stopped. Completed results remain available.')} finally {if(mounted.current)setPending(false)}
  }
  async function followup(body) {setError('');setPending(true);try{const data=await request(`/investigations/${caseData.id}/followup`,post(body));setCase(data);setTab('trace');setSourceUrl('')}catch(e){setError(e.message)}finally{setPending(false)}}
  async function loadHistory(){setShowHistory(!showHistory);const results=await Promise.allSettled([request('/investigations'),api('/workflows/history')]);if(results[0].status==='fulfilled')setHistory(results[0].value);if(results[1].status==='fulfilled')setWorkflowHistory(results[1].value);if(results.every(r=>r.status==='rejected'))setError('History unavailable.')}
  async function openWorkflow(id){try{const result=await api('/workflows/history/'+id);setWorkflowResults([result]);setWorkflowEvents([]);setWorkflowMode(true);setCase(null);setScenario(false);setShowHistory(false);setEvidenceOpen(true);showWorkflow(result)}catch(e){setError(e.message)}}
  async function openCase(id){setWorkflowMode(false);setScenario(false);setEvidenceOpen(true);setResearchOpen(false);try{setCase(await request(`/investigations/${id}`));setShowHistory(false);setTab('findings');setSelected(null)}catch(e){setError(e.message)}}
  async function suggest(value){setPlace(value);if(value.length<2){setSuggestions([]);return}try{const list=await request('/investigations/places?q='+encodeURIComponent(value));setSuggestions(list)}catch{setSuggestions([])}}
  function exportPacket(){const blob=new Blob([JSON.stringify(caseData,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=`askgaia-evidence-${caseData.id.slice(0,8)}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
  const sources=caseData?.sources||[], findings=caseData?.findings||[], gaps=caseData?.gaps||[]
  const source=selected ? sources.find(s=>s.id===selected.source_id) : null
  return <div className={`geo-workspace geo-scene-workspace ${evidenceOpen?'evidence-open':''}`}>
    <header className="geo-header"><a href="/" className="geo-brand"><Globe2 size={28} strokeWidth={1.3}/><span>askgaia<span className="geo-brand-period">.</span></span></a><span className="geo-header-tag">ENVIRONMENTAL INTELLIGENCE</span><nav><button onClick={()=>{setScenario(!scenario);setEvidenceOpen(true);setView('map')}}><Wind size={16}/><span>Simulation</span></button><button onClick={loadHistory} title="Saved investigations" aria-label="Saved investigations"><History size={16}/><span>History</span></button><a href="/explorer" aria-label="Explore data" title="Explore data"><span>Explore data</span> <ArrowUpRight size={14}/></a><span className={`geo-status ${connectionError?'offline':''}`}><i/>{caps?'Research workspace':'Connecting'}</span></nav></header>
    {showHistory && <aside className="geo-history"><div className="geo-section-heading"><h3>Saved investigations</h3><button onClick={()=>setShowHistory(false)} aria-label="Close history"><X size={18}/></button></div>{workflowHistory.map(w=><button key={w.id} onClick={()=>openWorkflow(w.id)}><strong>{w.request?.place}</strong><span>Four-agent workflow · {w.status}</span><small>{date(w.updated_at)}</small></button>)}{history.length?history.map(c=><button key={c.id} onClick={()=>openCase(c.id)}><strong>{c.place?.name}</strong><span>{c.question}</span><small>{date(c.updated_at)} · {c.status}</small></button>):<p>Your investigations will appear here.</p>}</aside>}
    <main className="geo-layout"><section className={`geo-research ${researchOpen?'expanded':'collapsed'}`}><button className="geo-research-toggle" aria-label={researchOpen ? "Close research" : "Ask a question"} aria-expanded={researchOpen} title="Ask a question" onClick={()=>setResearchOpen(!researchOpen)}><Search size={16}/><span>Ask a question</span>{researchOpen?<X size={15}/>:<Plus size={15}/>}</button><div className="geo-research-body">
      <div className="geo-eyebrow"><span>01 / INVESTIGATE</span><span>CALIFORNIA</span></div>

      <form className="geo-question-form" onSubmit={begin}><label htmlFor="geo-place">PLACE OF INTEREST</label><div className="geo-place-input"><MapPin size={17}/><input id="geo-place" value={place} onChange={e=>suggest(e.target.value)} required minLength={2} maxLength={150} autoComplete="off"/></div>
        {suggestions.length>0&&<div className="geo-suggestions">{suggestions.slice(0,5).map(p=><button type="button" key={p.name} onClick={()=>{setPlace(p.name);setSuggestions([])}}>{p.name}<small>{p.county}</small></button>)}</div>}
        <label htmlFor="geo-question">YOUR QUESTION</label><textarea id="geo-question" value={question} onChange={e=>setQuestion(e.target.value)} minLength={8} maxLength={1500} required rows={3}/>
        <label><input type="checkbox" checked={compareEnabled} onChange={e=>setCompareEnabled(e.target.checked)}/> Compare two places</label>
        {compareEnabled&&<div className="geo-place-input"><input aria-label="Second California place" value={comparePlace} onChange={e=>setComparePlace(e.target.value)} required minLength={3} maxLength={150} placeholder="Second California address"/></div>}
        {sprayScenario&&<label><input type="checkbox" checked={attachScenario} onChange={e=>setAttachScenario(e.target.checked)}/> Include the last spray scenario (same source for both places)</label>}
        <button className="geo-primary" disabled={running || !caps?.llm_configured}>{running?<><Loader2 className="geo-spin" size={17}/> Investigating…</>:<>Start investigation <ArrowRight size={18}/></>}</button>
      </form>{pending&&<button onClick={()=>streamController.current?.abort()}>Stop investigation</button>}
      {(error||connectionError)&&<div className="geo-error" role="alert"><AlertCircle size={17}/><span>{error||connectionError}</span></div>}
      <div className="geo-integrations"><div><span className={`geo-dot ${caps?.brightdata_search?'':'muted'}`}/><strong>Bright Data</strong><span>{caps?.brightdata_search?'Web discovery ready':'Search not configured'}</span></div><div><span className={`geo-dot ${caps?.llm_configured?'':'muted'}`}/><strong>{caps?.llm_provider || 'AI'}</strong><span>{caps?.llm_configured?'Evidence analysis':'Not connected'}</span></div><div><DatabaseIcon/><strong>Evidence store</strong><span>{caps?.storage||'Checking…'}</span></div></div>
      <div className="geo-principle"><Fingerprint size={22}/><p><strong>Every finding has a source.</strong><br/>We separate recorded facts, modeled scenarios, and what’s still unknown.</p></div>
      <a className="geo-mcp-link" href="/api/investigations/capabilities" target="_blank" rel="noreferrer"><Terminal size={14}/> AskGaia evidence tools · MCP ready <ArrowUpRight size={13}/></a>
    </div></section>
    <section className="geo-canvas">{view==='3d'?<Suspense fallback={<div className="geo-three-error">Loading illustrative lab…</div>}><ThreeScene place={caseData?.place}/></Suspense>:<CityMap focus={focus} overlay={overlay} onLocation={setMapLocation}/>}
      <div className="geo-view-switch" aria-label="Scene view"><button className={view==='3d'?'active':''} onClick={()=>setView('3d')}><Layers size={14}/> Lab</button><button className={view==='map'?'active':''} onClick={()=>setView('map')}><Globe2 size={14}/> Map</button></div>
      <button className="geo-evidence-toggle" onClick={()=>setEvidenceOpen(!evidenceOpen)}><BookOpen size={16}/>{evidenceOpen?'Close':'Evidence'}{caseData&&<span>{findings.length} findings · {gaps.length} open questions</span>}{running&&<Loader2 size={14} className="geo-spin"/>}</button>
      <div className="geo-map-toolbar"><button className={scenario?'active':''} onClick={()=>setScenario(!scenario)}><Wind size={16}/> What-if lab</button><span><Layers size={14}/> Evidence, not assumptions</span></div>
      {scenario&&<div className="geo-scenario-controls"><div><strong>Explore the wind</strong><span>Illustration only · independent of retrieved records</span></div><label>Wind from {direction}°<input type="range" min="0" max="359" value={direction} onChange={e=>setDirection(+e.target.value)}/></label><label>Wind speed {speed} m/s<input type="range" min="1" max="12" value={speed} onChange={e=>setSpeed(+e.target.value)}/></label></div>}
      <section className={`geo-evidence ${evidenceOpen?'open':''}`}><div className="geo-evidence-top"><div><span className="geo-eyebrow">02 / EVIDENCE DESK</span><h2>{scenario?'Spray scenario':workflowMode?'Agent investigation':caseData?caseData.place.name:'An answer you can inspect.'}</h2></div>{caseData&&<div className="geo-export"><button onClick={()=>window.print()} title="Save PDF using your browser print dialog"><Download size={15}/> PDF</button><button onClick={exportPacket}>JSON</button></div>}</div>
        {scenario?<ScenarioPanel location={mapLocation} onResult={showSimulation} onFrame={showFrame} onScenario={setSprayScenario}/>:workflowMode?<WorkflowResults results={workflowResults} events={workflowEvents} running={pending} error={error} onShow={showWorkflow}/>:!caseData?<div className="geo-empty"><div className="geo-empty-steps"><div><Search/><strong>Discover</strong><span>Find public records<br/>and overlooked context.</span></div><ChevronRight/><div><Fingerprint/><strong>Verify</strong><span>Trace every finding<br/>back to its source.</span></div><ChevronRight/><div><BookOpen/><strong>Understand</strong><span>Leave with evidence<br/>and better questions.</span></div></div><p>Choose a place and ask your first question.</p></div>:<>
          <div className="geo-tabs">{[['findings','Findings',findings.length],['gaps','Open questions',gaps.length],['sources','Sources',sources.length],['trace','Research trail',caseData.trace.length],['changes','Changes',caseData.revisions.length]].map(([id,label,count])=><button key={id} className={tab===id?'active':''} onClick={()=>setTab(id)}>{label}<span>{count}</span></button>)}</div>
          <div className="geo-result-content" aria-live="polite">
            {caseData.status==='error'&&<div className="geo-error"><AlertCircle size={17}/><span>{caseData.errors.at(-1)}</span><button disabled={running} onClick={()=>followup({})}>Retry</button></div>}
            {tab==='findings'&&<><p className="geo-summary">{caseData.summary || 'Your research is underway. Sources and findings will appear here.'}</p>{findings.map((f,i)=><button key={f.id} className="geo-finding" onClick={()=>setSelected(f)}><span className="geo-finding-index">{String(i+1).padStart(2,'0')}</span><div><span className="geo-scope">{f.scope}</span><h3>{f.claim}</h3><span className="geo-proof"><Fingerprint size={13}/> Show me the evidence <ArrowUpRight size={13}/></span></div></button>)}<p className="geo-footnote">Exact excerpts are checked automatically. AI interpretations are not independently verified. Recorded use does not establish personal exposure.</p></>}
            {tab==='gaps'&&<>{gaps.length===0&&<p className="geo-muted">Open questions will appear after source analysis.</p>}{gaps.map(g=><article className="geo-gap" key={g.id}><span className="geo-scope">UNRESOLVED</span><h3>{g.question}</h3><button disabled={running || !caps?.brightdata_search} onClick={()=>followup({gap_id:g.id})}>Investigate this gap <ArrowRight size={15}/></button>{!caps?.brightdata_search&&<small>Connect Bright Data search to follow this lead, or add a source in the Sources tab.</small>}</article>)}</>}
            {tab==='sources'&&<><form className="geo-add-source" onSubmit={e=>{e.preventDefault();followup({source_url:sourceUrl})}}><input type="url" placeholder="Add a public HTTPS source URL" aria-label="Public source URL" value={sourceUrl} onChange={e=>setSourceUrl(e.target.value)} required pattern="https://.*"/><button disabled={running}><Plus size={16}/> Add</button></form>{sources.map(s=><article className="geo-source" key={s.id}><div><span className="geo-scope">{s.provider}</span><a href={safeLink(s.url)} target="_blank" rel="noreferrer">{s.title}<ArrowUpRight size={14}/></a><small>Retrieved {date(s.retrieved_at)} · SHA256 {s.sha256.slice(0,10)}</small></div><button aria-label={`Check for changes to ${s.title}`} title="Check for changes" disabled={running} onClick={()=>followup({refresh_id:s.id})}><RefreshCw size={16}/></button></article>)}</>}
            {tab==='trace'&&<div className="geo-trace">{caseData.trace.map(t=><div key={t.id}><span className={'geo-trace-icon '+t.status}>{t.status==='complete'?<Check size={13}/>:t.status==='running'?<Search size={13}/>:<AlertCircle size={13}/>}</span><div><strong>{t.tool.replaceAll('_',' ')}</strong><p>{t.detail}</p><small>{date(t.time)} · {t.status}</small></div></div>)}{running&&<div className="geo-working"><Loader2 size={16} className="geo-spin"/> Following the evidence…</div>}</div>}
            {tab==='changes'&&<>{caseData.revisions.length===0?<p className="geo-muted">Refresh a source to check for changes. Earlier evidence and analyses are preserved.</p>:caseData.revisions.map((r,i)=><article className="geo-revision" key={i}><span className="geo-scope">{date(r.time)}</span><h3>{r.kind==='source_change'?'Source text changed':'Previous analysis preserved'}</h3>{r.diff?<pre>{r.diff}</pre>:<p>{r.previous?.summary}</p>}</article>)}</>}
          </div>
        </>}
      </section>
    </section></main>
    {caseData&&<section className="geo-print-packet"><h1>AskGaia evidence packet</h1><h2>{caseData.place.name}</h2><p>{caseData.question}</p><p>{caseData.summary}</p><p>Updated {date(caseData.updated_at)} · Status: {caseData.status}</p><h2>Findings</h2>{findings.map(f=><article key={f.id}><h3>{f.claim}</h3><p>Scope: {f.scope}</p><blockquote>{f.quote}</blockquote><p>Source: {sources.find(s=>s.id===f.source_id)?.url}</p><small>{f.verification}</small></article>)}<h2>Unresolved questions</h2>{gaps.map(g=><p key={g.id}>{g.question}</p>)}<h2>Source provenance</h2>{sources.map(s=><article key={s.id}><h3>{s.title}</h3><p>{s.url}</p><p>{s.provider} · Retrieved {date(s.retrieved_at)}</p><small>SHA256 {s.sha256}</small></article>)}<h2>Research trail</h2>{caseData.trace.map(t=><p key={t.id}>{date(t.time)} · {t.tool} · {t.status}: {t.detail}</p>)}<p>Recorded use is not proof of personal exposure. Hypothetical wind illustrations are not exposure estimates.</p></section>}
    <footer className="geo-footer"><span>AskGaia / Environmental intelligence</span><span>Public evidence. Visible uncertainty.</span><span>Built for SanD Hacks 2026</span></footer>
    {selected&&<div className="geo-modal-backdrop" onClick={()=>setSelected(null)}><section className="geo-proof-modal" role="dialog" aria-modal="true" aria-label="Evidence behind this finding" onClick={e=>e.stopPropagation()}><button className="geo-modal-close" aria-label="Close evidence" autoFocus onClick={()=>setSelected(null)}><X/></button><span className="geo-eyebrow">SHOW ME WHY</span><h2>{selected.claim}</h2><span className="geo-scope">EXACT SOURCE EXCERPT</span><blockquote>{selected.quote}</blockquote><p>{selected.verification}</p>{source&&<><a href={safeLink(source.url)} target="_blank" rel="noreferrer">{source.title} <ArrowUpRight size={15}/></a><dl><dt>Retrieved through</dt><dd>{source.provider}</dd><dt>Retrieved at</dt><dd>{date(source.retrieved_at)}</dd><dt>Claim scope</dt><dd>{selected.scope}</dd><dt>Content fingerprint</dt><dd className="geo-hash">{source.sha256}</dd></dl></>}</section></div>}
  </div>
}
function DatabaseIcon(){return <span className="geo-dot muted"/>}
