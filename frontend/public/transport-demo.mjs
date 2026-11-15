// Shared demo controls and rendering: all parcel positions come from the backend.
export function demoScenario(location, speed, names=['Example ingredient A','Example ingredient B']) {
  return {source_lat:location.lat,source_lon:location.lon,start_at:new Date().toISOString(),event_kind:'hypothetical',event_source:'AskGaia presentation demo — synthetic inputs, not a spray report',location_uncertainty_m:0,duration_minutes:2,horizon_minutes:5,snapshot_interval_minutes:1,
    ingredients:names.map((name,i)=>({name,applied_kg:1,airborne_fraction:.1,deposition_half_life_minutes:i?2:20,assumption_source:'Synthetic demo: 1 kg, 10% airborne; deposition half-life '+(i?2:20)+' min. Not measured chemical properties.'})),
    wind:[{minute:0,speed_ms:speed,from_deg:270}],physics:{release_height_m:2,mixing_height_m:20,horizontal_diffusivity_m2_s:2,vertical_diffusivity_m2_s:.5,wind_height_exponent:0,assumption_source:'Synthetic demo physics; uniform wind, no resolved building airflow.'}};
}
export function transportLayer(THREE, scene, project) {
  const group=new THREE.Group();scene.add(group);
  function clear(){while(group.children.length){const o=group.children[0];group.remove(o);o.geometry?.dispose();o.material?.dispose()}}
  return {draw(frame,hidden=[]){clear();if(!frame)return; if(group.parent!==scene)scene.add(group);
    for(const f of frame.footprints?.features||[]){if(hidden.includes(f.properties.ingredient))continue;
      const points=f.geometry.coordinates[0].map(([lon,lat])=>project(lat,lon));
      const line=new THREE.Line(new THREE.BufferGeometry().setFromPoints(points),new THREE.LineBasicMaterial({color:f.properties.color,transparent:true,opacity:.95,depthTest:false}));line.renderOrder=30;group.add(line);
    }
    // Fixed screen-sized markers represent parcel centers, not cloud boundaries.
    const names=[...new Set((frame.parcels?.features||[]).map(f=>f.properties.ingredient))];
    names.forEach((name,index)=>{if(hidden.includes(name))return;const fs=frame.parcels.features.filter(f=>f.properties.ingredient===name);
      const geo=new THREE.BufferGeometry().setFromPoints(fs.map(f=>project(f.geometry.coordinates[1],f.geometry.coordinates[0])));
      const mass=fs.reduce((s,f)=>s+f.properties.airborne_kg,0);
      const mat=new THREE.PointsMaterial({color:fs[0].properties.color,size:index?8:16,sizeAttenuation:false,transparent:true,opacity:Math.max(.2,Math.min(.9,mass/.1)),depthTest:false,depthWrite:false});
      const points=new THREE.Points(geo,mat);points.renderOrder=31+index;group.add(points);
    });
  },dispose(){clear();scene.remove(group)}};
}
export function mountTransportDemo({getLocation,onWind,onFrame,onActive=()=>{},host=document.body}) {
  const panel=document.createElement('details');panel.className='gaia-transport-demo';panel.open=false;
  panel.style.cssText='position:fixed;right:18px;top:115px;z-index:45;width:280px;max-height:55vh;overflow:auto;padding:14px;border:1px solid #6caa98;border-radius:16px;background:#09241fee;color:#f2f6ef;font:13px/1.45 system-ui;box-shadow:0 8px 30px #0006;pointer-events:auto';
  panel.innerHTML=`<style>.gaia-transport-demo button{background:#214c42;color:#f5f5e9;border:1px solid #5d8b7b;border-radius:9px;padding:7px 9px;cursor:pointer;font:inherit}.gaia-transport-demo button:disabled{opacity:.5}.gaia-transport-demo input[type=range]{width:100%;accent-color:#78d9ca}.gaia-transport-demo label{display:block;margin:5px 0}.gaia-transport-demo input:not([type=checkbox]):not([type=range]){max-width:95%}.gaia-transport-demo [data-notifications]{border-top:1px solid #56766a;margin-top:10px;font-size:12px}.gaia-transport-demo summary{cursor:pointer}</style><summary style="cursor:pointer;font-weight:700">Wind scenarios</summary><p>Demo · hypothetical release</p><div style="display:flex;gap:8px"><button data-preset=".2">Calm · 0.2 m/s</button><button data-preset="8">Strong · 8 m/s</button></div><p data-status role="status">Choose a preset. Cyan wind streaks show direction.</p><div data-controls hidden><button data-play>Play timeline</button><input data-time aria-label="Demo time" type="range" min="0" value="0"/><div data-legend></div></div><details><summary>Model assumptions</summary><label>Ingredient A <input data-name="0" value="Example ingredient A" maxlength="120"/></label><label>Ingredient B <input data-name="1" value="Example ingredient B" maxlength="120"/></label><p>Each: 1 kg applied, 10% airborne. Assumed deposition half-lives: A 20 min; B 2 min. Names do not select validated chemical properties. Colors identify ingredients; markers are parcel centers. Outlines are model moment ellipses, not exposure boundaries. Wind is uniform; animation is illustrative.</p></details><button data-clear>Exit demo</button><div data-notifications role="log" aria-live="polite" aria-label="Demo notifications"></div>`;
  host.append(panel);let result=null,index=0,timer=null,controller=null,generation=0,hidden=new Set();
  const q=s=>panel.querySelector(s),buttons=[...panel.querySelectorAll('[data-preset]')];
  function notify(text){const p=document.createElement('p');p.textContent='DEMO · '+text;q('[data-notifications]').prepend(p);while(q('[data-notifications]').children.length>4)q('[data-notifications]').lastChild.remove()}
  function pause(){clearInterval(timer);timer=null;q('[data-play]').textContent='Play timeline'}
  function draw(){if(!result)return;const f=result.snapshots[index];q('[data-time]').value=index;q('[data-status]').textContent=`${result.wind_steps[0].speed_ms} m/s from W → E · ${f.minute} min after hypothetical release`;onFrame(f,[...hidden]);
    q('[data-legend]').replaceChildren();f.mass_balance.forEach((b,i)=>{const label=document.createElement('label');label.style.cssText='display:block;color:'+(i?'#edc16b':'#a6ffe0');const c=document.createElement('input');c.type='checkbox';c.checked=!hidden.has(b.ingredient);c.onchange=()=>{c.checked?hidden.delete(b.ingredient):hidden.add(b.ingredient);draw()};label.append(c,document.createTextNode(`${b.ingredient}: ${b.airborne_kg.toFixed(3)} kg airborne`));q('[data-legend]').append(label)});
  }
  async function run(speed){const loc=getLocation();if(!loc){notify('Select a city or school first.');return}pause();controller?.abort();controller=new AbortController();const gen=++generation;result=null;onFrame(null,[]);onActive(false);q('[data-controls]').hidden=true;buttons.forEach(b=>b.disabled=true);q('[data-status]').textContent='Calculating drift…';
    try{const names=[0,1].map(i=>q(`[data-name="${i}"]`).value.trim());if(names.some(n=>!n)||names[0].toLowerCase()===names[1].toLowerCase())throw Error('Use two distinct ingredient names.');
      const r=await fetch('/api/workflows/simulate-spray',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(demoScenario(loc,speed,names)),signal:controller.signal});if(!r.ok)throw Error('Simulation unavailable. Please retry.');const data=await r.json();if(gen!==generation)return;
      result=data;index=0;hidden.clear();onActive(true);onWind({speed,dir:270,cls:'D'});q('[data-controls]').hidden=false;q('[data-time]').max=result.snapshots.length-1;draw();notify(`${speed<.5?'Calm wind: slow transport near source.':'Strong wind: faster downwind transport.'} Scenario only — no spraying detected.`);
    }catch(e){if(e.name!=='AbortError'){q('[data-status]').textContent=e.message;notify('Simulation unavailable; no result inferred.')}}finally{if(gen===generation)buttons.forEach(b=>b.disabled=false)}
  }
  buttons.forEach(b=>b.onclick=()=>run(+b.dataset.preset));q('[data-time]').oninput=e=>{pause();index=+e.target.value;draw()};
  q('[data-play]').onclick=()=>{if(timer){pause();return}if(!result)return;if(index===result.snapshots.length-1)index=0;draw();q('[data-play]').textContent='Pause';timer=setInterval(()=>{index++;draw();if(index>=result.snapshots.length-1){pause();notify('Timeline complete. Compare the other preset using the same source and ingredient assumptions.')}},1100)};
  function reset(silent=false){++generation;controller?.abort();pause();result=null;onFrame(null,[]);onActive(false);buttons.forEach(b=>b.disabled=false);q('[data-controls]').hidden=true;q('[data-status]').textContent='Demo cleared. Use Current wind to restore weather-driven conditions.';if(!silent)notify('Demo layers cleared. Wind remains a scenario until Current wind is selected.')}
  q('[data-clear]').onclick=()=>reset();
  const dispose=()=>{++generation;controller?.abort();pause();onFrame(null,[]);panel.remove()};dispose.reset=reset;return dispose;
}
