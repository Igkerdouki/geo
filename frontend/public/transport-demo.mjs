// Shared demo controls and rendering: all parcel positions come from the backend.
export function demoScenario(location, speed, names=['Example ingredient A','Example ingredient B'], direction=270) {
  return {source_lat:location.lat,source_lon:location.lon,start_at:new Date().toISOString(),event_kind:'hypothetical',event_source:'AskGaia presentation demo — synthetic inputs, not a spray report',location_uncertainty_m:0,duration_minutes:3,horizon_minutes:8,snapshot_interval_minutes:1,deposition_map:true,
    ingredients:names.map((name,i)=>({name,applied_kg:1,airborne_fraction:.1,deposition_half_life_minutes:i?2:20,assumption_source:'Synthetic demo: 1 kg, 10% airborne; deposition half-life '+(i?2:20)+' min. Not measured chemical properties.'})),
    wind:[{minute:0,speed_ms:speed,from_deg:direction}],physics:{release_height_m:2,mixing_height_m:20,horizontal_diffusivity_m2_s:2,vertical_diffusivity_m2_s:.5,wind_height_exponent:0,assumption_source:'Synthetic demo physics; uniform wind, no resolved building airflow.'}};
}
export function transportLayer(THREE, scene, project) {
  const group=new THREE.Group();scene.add(group);
  function clear(){while(group.children.length){const o=group.children[0];group.remove(o);o.geometry?.dispose();o.material?.dispose()}}
  return {draw(frame,hidden=[]){clear();if(!frame)return; if(group.parent!==scene)scene.add(group);
    if(frame.release){
      const source=new THREE.Points(new THREE.BufferGeometry().setFromPoints([project(frame.release.lat,frame.release.lon)]),new THREE.PointsMaterial({color:frame.release.active?0xffffff:0xaaaaaa,size:frame.release.active?22:12,sizeAttenuation:false,depthTest:false,depthWrite:false,transparent:true,opacity:.95}));source.renderOrder=40;group.add(source);
    }
    for(const f of frame.footprints?.features||[]){if(hidden.includes(f.properties.ingredient))continue;
      const points=f.geometry.coordinates[0].map(([lon,lat])=>project(lat,lon));
      const line=new THREE.Line(new THREE.BufferGeometry().setFromPoints(points),new THREE.LineBasicMaterial({color:f.properties.color,transparent:true,opacity:.95,depthTest:false}));line.renderOrder=30;group.add(line);
    }
    // Ground cells remain after airborne puffs leave; colors encode cumulative loading.
    const cells=new Map();
    for(const f of frame.deposition?.features||[]){
      if(hidden.includes(f.properties.ingredient))continue;
      const key=JSON.stringify(f.geometry.coordinates),old=cells.get(key);
      if(old)old.loading+=f.properties.loading_mg_m2;
      else cells.set(key,{ring:f.geometry.coordinates[0],loading:f.properties.loading_mg_m2});
    }
    const peak=frame.deposition_peak_mg_m2||1;
    function polygon(ring,color,opacity,order){
      const ps=ring.map(([lon,lat])=>project(lat,lon)),vertices=[];
      for(let i=1;i<ps.length-1;i++)for(const p of [ps[0],ps[i],ps[i+1]])vertices.push(p.x,p.y,p.z);
      const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));
      const mesh=new THREE.Mesh(geo,new THREE.MeshBasicMaterial({color,transparent:true,opacity,side:THREE.DoubleSide,depthTest:false,depthWrite:false}));mesh.renderOrder=order;group.add(mesh);
    }
    for(const {ring,loading} of cells.values()){
      const v=Math.min(1,Math.log1p(9*loading/peak)/Math.log(10));
      if(v<.005)continue;
      const color=new THREE.Color().setHSL((1-v)*.16,1,.5);
      polygon(ring,color,.15+.65*v,28);
    }
    // Gaussian plan-view clouds: radius derives from backend diffusion, mass controls opacity.
    for(const f of frame.parcels?.features||[]){
      if(hidden.includes(f.properties.ingredient)||f.properties.airborne_kg<1e-10)continue;
      const [lon,lat]=f.geometry.coordinates,sigma=f.properties.sigma_m||10;
      const massRatio=Math.min(1,f.properties.airborne_kg/(frame.airborne_reference_kg||.05));
      for(let k=5;k>=1;k--){
        const radius=sigma*k*.5,ring=[];
        for(let j=0;j<=32;j++){const a=j*Math.PI/16;ring.push([lon+radius*Math.cos(a)/(111320*Math.cos(lat*Math.PI/180)),lat+radius*Math.sin(a)/111320]);}
        polygon(ring,f.properties.color,(.045+.045*(6-k))*massRatio,31);
      }
    }
  },dispose(){clear();scene.remove(group)}};
}
export function mountTransportDemo({getLocation,getWind=()=>null,onWind,onFrame,onActive=()=>{},host=document.body}) {
  const panel=document.createElement('details');panel.className='gaia-transport-demo';panel.open=false;
  panel.style.cssText='position:fixed;right:18px;top:115px;z-index:45;width:280px;max-height:55vh;overflow:auto;padding:14px;border:1px solid #6caa98;border-radius:16px;background:#09241fee;color:#f2f6ef;font:13px/1.45 system-ui;box-shadow:0 8px 30px #0006;pointer-events:auto';
  panel.innerHTML=`<style>.gaia-transport-demo button{background:#214c42;color:#f5f5e9;border:1px solid #5d8b7b;border-radius:9px;padding:7px 9px;cursor:pointer;font:inherit}.gaia-transport-demo button:disabled{opacity:.5}.gaia-transport-demo input[type=range]{width:100%;accent-color:#78d9ca}.gaia-transport-demo label{display:block;margin:5px 0}.gaia-transport-demo input:not([type=checkbox]):not([type=range]){max-width:95%}.gaia-transport-demo [data-notifications]{border-top:1px solid #56766a;margin-top:10px;font-size:12px}.gaia-transport-demo summary{cursor:pointer}</style><summary style="cursor:pointer;font-weight:700">Pesticide flow</summary><p>Same release: 2 kg over 3 minutes · illustrative ingredients</p><button data-current>Spray with selected wind</button><div style="display:flex;gap:8px"><button data-preset=".2">Low wind + spray</button><button data-preset="8">High wind + spray</button></div><p data-status role="status">Choose wind to see drift and ground accumulation.</p><div data-controls hidden><button data-play>Play timeline</button><input data-time aria-label="Demo time" type="range" min="0" value="0"/><div data-legend></div></div><details><summary>Model assumptions</summary><label>Ingredient A <input data-name="0" value="Example ingredient A" maxlength="120"/></label><label>Ingredient B <input data-name="1" value="Example ingredient B" maxlength="120"/></label><p>Each: 1 kg applied, 10% airborne. Assumed deposition half-lives: A 20 min; B 2 min. Names do not select validated chemical properties. Cloud colors identify ingredients; yellow–red ground cells show cumulative modeled deposition. Not measured residues or exposure boundaries. Wind is uniform; animation is illustrative.</p></details><button data-clear>Exit demo</button><div data-notifications role="log" aria-live="polite" aria-label="Demo notifications"></div>`;
  host.append(panel);let result=null,index=0,timer=null,controller=null,generation=0,hidden=new Set();
  const q=s=>panel.querySelector(s),buttons=[...panel.querySelectorAll('[data-preset]')];
  function notify(text){const p=document.createElement('p');p.textContent='DEMO · '+text;q('[data-notifications]').prepend(p);while(q('[data-notifications]').children.length>4)q('[data-notifications]').lastChild.remove()}
  function pause(){clearInterval(timer);timer=null;q('[data-play]').textContent='Play timeline'}
  const legend=document.createElement('div');legend.hidden=true;legend.style.cssText='position:fixed;left:24px;bottom:94px;z-index:46;max-width:300px;padding:10px 14px;border-radius:12px;background:#09241fee;color:#f2f6ef;font:12px/1.5 system-ui;pointer-events:none';host.append(legend);
  function draw(){if(!result)return;const f=result.snapshots[index];const release=f.release;q('[data-time]').value=index;q('[data-status]').textContent=`${release.active?'Spraying':'Release complete'} · ${release.applied_kg.toFixed(2)} / ${release.total_kg.toFixed(2)} kg applied · ${result.wind_steps[0].speed_ms} m/s · wind from ${result.wind_steps[0].from_deg}° · ${f.minute} min after hypothetical release`;onFrame(f,[...hidden]);legend.hidden=false;legend.textContent=`Modeled pesticide flow · ${f.minute} min. White marker: release source. Mint / gold: airborne ingredients. Ground: yellow → red = lower → higher accumulated deposition (0–${f.deposition_peak_mg_m2.toPrecision(2)} mg/m²). Illustrative scenario, not measured residue.`;
    q('[data-legend]').replaceChildren();f.mass_balance.forEach((b,i)=>{const label=document.createElement('label');label.style.cssText='display:block;color:'+(i?'#edc16b':'#a6ffe0');const c=document.createElement('input');c.type='checkbox';c.checked=!hidden.has(b.ingredient);c.onchange=()=>{c.checked?hidden.delete(b.ingredient):hidden.add(b.ingredient);draw()};label.append(c,document.createTextNode(`${b.ingredient}: ${b.airborne_kg.toFixed(3)} kg airborne · ${b.deposited_kg.toFixed(3)} kg deposited`));q('[data-legend]').append(label)});
  }
  async function run(speed,direction=270){const loc=getLocation();if(!loc){notify('Select a city or school first.');return}pause();controller?.abort();controller=new AbortController();const gen=++generation;result=null;onFrame(null,[]);onActive(false);q('[data-controls]').hidden=true;buttons.forEach(b=>b.disabled=true);q('[data-status]').textContent='Calculating drift…';
    try{const names=[0,1].map(i=>q(`[data-name="${i}"]`).value.trim());if(names.some(n=>!n)||names[0].toLowerCase()===names[1].toLowerCase())throw Error('Use two distinct ingredient names.');
      const r=await fetch('/api/workflows/simulate-spray',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(demoScenario(loc,speed,names,direction)),signal:controller.signal});if(!r.ok)throw Error('Simulation unavailable. Please retry.');const data=await r.json();if(gen!==generation)return;
      result=data;
      const event=result.event,total=event.ingredients.reduce((sum,i)=>sum+i.applied_kg,0);
      const first=result.snapshots[0];
      result.snapshots.unshift({...first,minute:0,parcels:{type:'FeatureCollection',features:[]},footprints:{type:'FeatureCollection',features:[]},deposition:{type:'FeatureCollection',features:[]},mass_balance:first.mass_balance.map(b=>({...b,released_airborne_kg:0,airborne_kg:0,vapor_kg:0,deposited_kg:0,degraded_kg:0}))});
      for(const f of result.snapshots)f.release={lat:event.source_lat,lon:event.source_lon,active:f.minute<event.duration_minutes,total_kg:total,applied_kg:total*Math.min(1,f.minute/event.duration_minutes)};
      let peak=0;for(const f of result.snapshots){const cells=new Map();for(const c of f.deposition?.features||[]){const key=JSON.stringify(c.geometry.coordinates);cells.set(key,(cells.get(key)||0)+c.properties.loading_mg_m2)}peak=Math.max(peak,...cells.values())}
      for(const f of result.snapshots){f.deposition_peak_mg_m2=peak||1;f.airborne_reference_kg=.05}
      index=0;hidden.clear();onActive(true);onWind({speed,dir:direction,cls:'D'});q('[data-controls]').hidden=false;q('[data-time]').max=result.snapshots.length-1;draw();q('[data-play]').click();notify(`${speed<.5?'Calm wind: slow transport near source.':'Strong wind: faster downwind transport.'} Scenario only — no spraying detected.`);
    }catch(e){if(e.name!=='AbortError'){q('[data-status]').textContent=e.message;notify('Simulation unavailable; no result inferred.')}}finally{if(gen===generation)buttons.forEach(b=>b.disabled=false)}
  }
  q('[data-current]').onclick=()=>{const w=getWind();if(w)run(w.speed,w.dir);else q('[data-status]').textContent='Select Calm or Strong wind to start.'};
  buttons.forEach(b=>b.onclick=()=>run(+b.dataset.preset));q('[data-time]').oninput=e=>{pause();index=+e.target.value;draw()};
  q('[data-play]').onclick=()=>{if(timer){pause();return}if(!result)return;if(index===result.snapshots.length-1)index=0;draw();q('[data-play]').textContent='Pause';timer=setInterval(()=>{index++;draw();if(index>=result.snapshots.length-1){pause();notify('Timeline complete. Compare the other preset using the same source and ingredient assumptions.')}},1600)};
  function reset(silent=false){legend.hidden=true;++generation;controller?.abort();pause();result=null;onFrame(null,[]);onActive(false);buttons.forEach(b=>b.disabled=false);q('[data-controls]').hidden=true;q('[data-status]').textContent='Demo cleared. Use Current wind to restore weather-driven conditions.';if(!silent)notify('Demo layers cleared. Wind remains a scenario until Current wind is selected.')}
  q('[data-clear]').onclick=()=>reset();
  const startPreset=e=>{if([.2,8].includes(e.detail?.speed)){panel.open=true;run(e.detail.speed)}};window.addEventListener('gaia-release-preset',startPreset);
  const dispose=()=>{++generation;controller?.abort();pause();onFrame(null,[]);panel.remove();legend.remove();window.removeEventListener('gaia-release-preset',startPreset)};dispose.reset=reset;return dispose;
}
