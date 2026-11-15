export function sampleGrid(result, east, north) {
  const g = result?.grid;
  if (!g || result.status !== 'complete') return 0;
  const x = (east/g.extent_m+.5)*(g.size-1), y = (north/g.extent_m+.5)*(g.size-1);
  if(x<0 || y<0 || x>g.size-1 || y>g.size-1) return 0;
  const i=Math.min(g.size-2,Math.floor(x)), j=Math.min(g.size-2,Math.floor(y)), a=x-i,b=y-j;
  return (g.values[j*g.size+i]*(1-a)+g.values[j*g.size+i+1]*a)*(1-b)+(g.values[(j+1)*g.size+i]*(1-a)+g.values[(j+1)*g.size+i+1]*a)*b;
}
export async function mapSimulation(scenario, signal) {
  const r=await fetch('/api/workflows/map-simulation',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(scenario),signal});
  if(!r.ok) throw new Error('Backend simulation unavailable');
  return r.json();
}
export function mountInvestigation(host, getContext) {
  const details=document.createElement('details'), title=document.createElement('summary'), button=document.createElement('button'), output=document.createElement('div');
  title.textContent='Agent investigation';button.textContent='Run four-agent review';button.type='button';output.setAttribute('role','status');
  details.append(title,button,output);host.append(details);
  let controller, downloadUrl;
  button.onclick=async()=>{
    controller?.abort();if(downloadUrl)URL.revokeObjectURL(downloadUrl);controller=new AbortController();const signal=controller.signal;
    const {place,lat,lon,simulation}=getContext();
    button.disabled=true;output.textContent='Starting location → data → simulation → verifier…';
    const snapshotId=simulation?.id || 'no plume';
    try {
      const s=simulation?.scenario;
      const response=await fetch('/api/workflows/investigate/stream',{method:'POST',signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({place:String(place).slice(0,200),selected_location:{lat,lon},question:'Review recorded pesticide use and the displayed hypothetical drift scenario. Separate recorded facts, model estimates, and missing evidence.',radius_km:4,...(simulation?.status==='complete' && s && Number.isFinite(s.source_lat) && Number.isFinite(s.source_lon) && s.speed>=.5 ? {scenario:{source_lat:s.source_lat,source_lon:s.source_lon,wind_speed_ms:s.speed,wind_from_deg:s.direction,stability:s.stability}} : {})})});
      if(!response.ok) throw new Error('Agent workflow unavailable. Check the configured AI provider.');
      const reader=response.body.getReader(), decoder=new TextDecoder();let buffer='';
      const consume=line=>{
        if(!line.trim())return;const event=JSON.parse(line);
        if(event.type==='error')throw new Error(event.message);
        if(event.type==='agent') output.textContent=`${event.agent}: ${event.status}`;
        if(event.type==='result'){
          output.textContent=`Review of simulation ${snapshotId}. `;
          for(const [role,report] of Object.entries(event.result.agents || {})){if(report.status==='error'){const p=document.createElement('p');p.textContent=`${role}: ${report.error}`;output.append(p);}}
          for(const label of ['observed','modelled','uncertain'])for(const claim of event.result[label]||[]){const p=document.createElement('p');p.textContent=`${label}: ${claim.claim || claim.text || JSON.stringify(claim)}`;output.append(p);}
          for(const warning of event.result.warnings||[]){const p=document.createElement('p');p.textContent=warning;output.append(p);}
          const p=document.createElement('p');p.textContent=`Workflow ${event.result.id} · ${event.result.status}`;output.append(p);
          const download=document.createElement('a');downloadUrl=URL.createObjectURL(new Blob([JSON.stringify(event.result,null,2)],{type:'application/json'}));download.href=downloadUrl;download.download=`investigation-${event.result.id}.json`;download.textContent='Download JSON';output.append(download);
        }
      };
      while(true){const {done,value}=await reader.read();buffer+=decoder.decode(value||new Uint8Array(),{stream:!done});const lines=buffer.split('\n');buffer=lines.pop();lines.forEach(consume);if(done){consume(buffer);break;}}
    }catch(e){if(!signal.aborted)output.textContent=e.message;}finally{if(!signal.aborted)button.disabled=false;}
  };
  return ()=>{controller?.abort();if(downloadUrl)URL.revokeObjectURL(downloadUrl);details.remove();};
}
