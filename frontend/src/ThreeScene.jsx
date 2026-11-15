import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import { Pause, Play, RotateCcw } from 'lucide-react'

// Adapted from the supplied concept brief. Procedural scenery and illustrative
// relative plume only: buildings do not participate in a fluid dynamics model.
export default function ThreeScene({ place }) {
  const mount=useRef(null), tag=useRef(null), controller=useRef(null)
  const [direction,setDirection]=useState(253),[speed,setSpeed]=useState(2),[stability,setStability]=useState('D')
  const [playing,setPlaying]=useState(!window.matchMedia('(prefers-reduced-motion: reduce)').matches),[error,setError]=useState('')
  useEffect(()=>{
    const host=mount.current, reduce=window.matchMedia('(prefers-reduced-motion: reduce)').matches
    let teardown=()=>{}
    try {
const renderer=new THREE.WebGLRenderer({antialias:true,alpha:true});
renderer.setPixelRatio(Math.min(devicePixelRatio,2)); renderer.shadowMap.enabled=true; renderer.shadowMap.type=THREE.PCFSoftShadowMap;
host.appendChild(renderer.domElement);
const scene=new THREE.Scene(); scene.fog=new THREE.Fog(0x06090c,420,900);
const cam=new THREE.PerspectiveCamera(42,1,1,3000); cam.position.set(-240,190,290);
const ctl=new OrbitControls(cam,renderer.domElement); ctl.target.set(20,0,-10); ctl.enableDamping=true; ctl.maxPolarAngle=1.42; ctl.minDistance=120; ctl.maxDistance=900; ctl.autoRotate=false; ctl.autoRotateSpeed=0.35;

scene.add(new THREE.HemisphereLight(0xdfefff,0x2a3530,1.1));
const sun=new THREE.DirectionalLight(0xffffff,1.6); sun.position.set(-200,320,140); sun.castShadow=true; sun.shadow.mapSize.set(2048,2048);
Object.assign(sun.shadow.camera,{left:-420,right:420,top:420,bottom:-420,far:1200}); scene.add(sun);
// ground disc
const ground=new THREE.Mesh(new THREE.CircleGeometry(460,96),new THREE.MeshStandardMaterial({color:0x8d969c,roughness:1}));
ground.rotation.x=-Math.PI/2; ground.receiveShadow=true; scene.add(ground);
// park (field = source) and school
const PARK={x:-40,z:30,w:190,d:150};
const park=new THREE.Mesh(new THREE.PlaneGeometry(PARK.w,PARK.d),new THREE.MeshStandardMaterial({color:0x4d7a3a,roughness:1}));
park.rotation.x=-Math.PI/2; park.position.set(PARK.x,0.3,PARK.z); park.receiveShadow=true; scene.add(park);
const SCHOOL=new THREE.Vector3(150,0,-110);
// buildings (instanced)
const rnd=(a=>()=>(a=Math.imul(a^a>>>15,1|a)+0x6D2B79F5|0,((a^a>>>7)>>>0)/4294967296))(7);
const boxes=[]; const B=12;
for(let gx=-420;gx<=420;gx+=B*1.6){for(let gz=-420;gz<=420;gz+=B*1.6){
  if(Math.hypot(gx,gz)>440) continue;
  if(Math.abs(gx-PARK.x)<PARK.w/2+6&&Math.abs(gz-PARK.z)<PARK.d/2+6) continue;
  if(Math.abs(gx-SCHOOL.x)<22&&Math.abs(gz-SCHOOL.z)<22) continue;
  if(rnd()<0.18) continue;
  const core=Math.max(0,1-Math.hypot(gx-120,gz+60)/330);
  const h=4+Math.pow(rnd(),2.2)*30+core*core*rnd()*130;
  boxes.push([gx+(rnd()-.5)*4,gz+(rnd()-.5)*4,B*(0.7+rnd()*0.5),h,B*(0.7+rnd()*0.5)]);}}
const bmesh=new THREE.InstancedMesh(new THREE.BoxGeometry(1,1,1),new THREE.MeshStandardMaterial({color:0xe7ecf4,roughness:.75,metalness:.05}),boxes.length);
const m4=new THREE.Matrix4(); boxes.forEach((b,i)=>{m4.compose(new THREE.Vector3(b[0],b[3]/2,b[1]),new THREE.Quaternion(),new THREE.Vector3(b[2],b[3],b[4]));bmesh.setMatrixAt(i,m4)});
bmesh.castShadow=bmesh.receiveShadow=true; scene.add(bmesh);
const school=new THREE.Mesh(new THREE.BoxGeometry(34,10,24),new THREE.MeshStandardMaterial({color:0xffc857,emissive:0x5a3a00,roughness:.6}));
school.position.set(SCHOOL.x,5,SCHOOL.z); school.castShadow=true; scene.add(school);
// trees in park
const tg=new THREE.SphereGeometry(1,8,6),tm=new THREE.MeshStandardMaterial({color:0x1f3d22,roughness:1});
const trees=new THREE.InstancedMesh(tg,tm,140);
for(let i=0;i<140;i++){const edge=rnd()<.7;let x,z;if(edge){const s=rnd()*4|0;x=PARK.x+(s<2?(rnd()-.5)*PARK.w:(s==2?-1:1)*PARK.w/2*0.92);z=PARK.z+(s<2?(s?-1:1)*PARK.d/2*0.92:(rnd()-.5)*PARK.d)}else{x=PARK.x+(rnd()-.5)*PARK.w*.8;z=PARK.z+(rnd()-.5)*PARK.d*.8}
 const r=3+rnd()*3;m4.compose(new THREE.Vector3(x,r,z),new THREE.Quaternion(),new THREE.Vector3(r,r*1.1,r));trees.setMatrixAt(i,m4)}
trees.castShadow=true; scene.add(trees);
// --- Gaussian plume ground layer ---
const SZ=128, EXT=900, data=new Uint8Array(SZ*SZ*4), tex=new THREE.DataTexture(data,SZ,SZ); tex.magFilter=tex.minFilter=THREE.LinearFilter;
const plume=new THREE.Mesh(new THREE.PlaneGeometry(EXT,EXT),new THREE.MeshBasicMaterial({map:tex,transparent:true,depthWrite:false}));
plume.rotation.x=-Math.PI/2; plume.position.y=0.8; scene.add(plume);
const SIG={A:[.22,x=>.2*x],B:[.16,x=>.12*x],C:[.11,x=>.08*x/Math.sqrt(1+.0002*x)],D:[.08,x=>.06*x/Math.sqrt(1+.0015*x)],E:[.06,x=>.03*x/(1+.0003*x)],F:[.04,x=>.016*x/(1+.0003*x)]};
const M=2.0; // metres per scene unit
const stops=[[0,[31,75,209]],[.25,[22,184,232]],[.5,[63,224,122]],[.75,[233,228,58]],[1,[242,85,44]]];
const cmap=v=>{for(let i=1;i<stops.length;i++)if(v<=stops[i][0]){const[a,ca]=stops[i-1],[b,cb]=stops[i],f=(v-a)/(b-a);return ca.map((c,k)=>c+(cb[k]-c)*f)}return stops[4][1]};
let wind={dir:225,u:4,cls:'D'};
function conc(px,pz){ // ground-level, source = park area (sum of a few point sources)
  const th=(wind.dir+180)*Math.PI/180, wx=Math.sin(th), wz=-Math.cos(th); // direction wind blows TO
  const [ay,szf]=SIG[wind.cls]; let c=0;
  for(const s of SRC){const dx=(px-s[0])*M,dz=(pz-s[1])*M,x=dx*wx+dz*wz,y=-dx*wz+dz*wx; if(x<=1)continue;
    const sy=ay*x/Math.sqrt(1+.0001*x), sz=Math.max(szf(x),.5), H=2;
    c+=Math.exp(-y*y/(2*sy*sy))*2*Math.exp(-H*H/(2*sz*sz))/(Math.PI*wind.u*sy*sz);}
  return c/SRC.length;}
const SRC=[];for(let i=0;i<9;i++)SRC.push([PARK.x+((i%3)-1)*PARK.w*.3,PARK.z+(((i/3)|0)-1)*PARK.d*.3]);
let cRef=1;
function paintPlume(){
  cRef=conc(PARK.x+Math.sin((wind.dir+180)*Math.PI/180)*120,PARK.z-Math.cos((wind.dir+180)*Math.PI/180)*120)||1e-9;
  const ref=4*conc(PARK.x+Math.sin((wind.dir+180)*Math.PI/180)*(PARK.w*.55),PARK.z-Math.cos((wind.dir+180)*Math.PI/180)*(PARK.w*.55))||1e-9;
  for(let j=0;j<SZ;j++)for(let i=0;i<SZ;i++){const px=(i/(SZ-1)-.5)*EXT, pz=-(j/(SZ-1)-.5)*EXT; let v=conc(px,pz)/ref;
    v=v>0?Math.max(0,Math.min(1,1+Math.log10(v)/2.4)):0; const o=(j*SZ+i)*4,[r,g,b]=cmap(v);
    data[o]=r;data[o+1]=g;data[o+2]=b;data[o+3]=v<.02?0:Math.min(235,60+v*200)*(Math.hypot(px,pz)<455?1:0);}
  tex.needsUpdate=true;
}
// --- wind streamlines (particle trails) ---
const NP=reduce?250:(host.clientWidth<700?400:900), TR=6; const pos=new Float32Array(NP*TR*2*3), col=new Float32Array(NP*TR*2*3);
const lg=new THREE.BufferGeometry(); lg.setAttribute('position',new THREE.BufferAttribute(pos,3)); lg.setAttribute('color',new THREE.BufferAttribute(col,3));
const lines=new THREE.LineSegments(lg,new THREE.LineBasicMaterial({vertexColors:true,transparent:true,opacity:.85,blending:THREE.AdditiveBlending,depthWrite:false}));
scene.add(lines);
const P=[];function spawn(p,init){const s=SRC[Math.random()*SRC.length|0];p.x=s[0]+(Math.random()-.5)*60;p.z=s[1]+(Math.random()-.5)*50;p.y=1+Math.random()*6;p.age=init?Math.random()*260:0;p.hist=[[p.x,p.y,p.z]];p.seed=Math.random()*1000;}
for(let i=0;i<NP;i++){const p={};spawn(p,true);P.push(p)}
const spatial = new Map();
for (const b of boxes) { const key = `${Math.round(b[0]/(B*1.6))},${Math.round(b[1]/(B*1.6))}`; spatial.set(key,b) }
const hAt=(x,z)=>{const gx=Math.round(x/(B*1.6)),gz=Math.round(z/(B*1.6));for(let i=-1;i<=1;i++)for(let j=-1;j<=1;j++){const b=spatial.get(`${gx+i},${gz+j}`);if(b&&Math.abs(x-b[0])<b[2]/2+2&&Math.abs(z-b[1])<b[4]/2+2)return b[3]}return 0};
let tt=0;
function step(delta=1){tt+=.016*delta;const th=(wind.dir+180)*Math.PI/180, wx=Math.sin(th), wz=-Math.cos(th), sp=(.35+wind.u*.16)*delta;
  const spread={A:1.9,B:1.5,C:1.2,D:1,E:.75,F:.55}[wind.cls];
  let k=0;for(const p of P){
    const n=Math.sin(p.seed+tt*1.3+p.x*.02)*.5+Math.sin(p.seed*1.7+p.z*.025-tt)*.5;
    p.x+=(wx-wz*n*.35*spread)*sp; p.z+=(wz+wx*n*.35*spread)*sp;
    const h=hAt(p.x,p.z); p.y+= (h>p.y-2? (h+3-p.y)*.25 : (Math.sin(p.seed+tt)*.05*spread - (p.y>40?.08:0)));
    p.y=Math.max(1,p.y); p.age++; p.hist.unshift([p.x,p.y,p.z]); if(p.hist.length>TR+1)p.hist.pop();
    if(p.age>260||Math.hypot(p.x,p.z)>450)spawn(p,false);
    const life=Math.min(1,p.age/20)*Math.max(0,1-p.age/260);
    const L=p.hist.length;for(let s=0;s<TR;s++){const a=p.hist[Math.min(s,L-1)],b=p.hist[Math.min(s+1,L-1)]; const f=(1-s/TR)*life;
      const d=Math.min(1,p.age/170),[r,g,bb]=cmap(1-d*.85);
      pos.set(a,k*3);pos.set(b,k*3+3);
      col[k*3]=col[k*3+3]=r/255*f;col[k*3+1]=col[k*3+4]=g/255*f;col[k*3+2]=col[k*3+5]=bb/255*f; k+=2;}}
  lg.attributes.position.needsUpdate=lg.attributes.color.needsUpdate=true;}

    let paused=reduce, frame=0, last=0, visible=true, disposed=false;
    const point=new THREE.Vector3();
    const resize=()=>{const w=host.clientWidth,h=host.clientHeight;if(!w||!h)return;renderer.setSize(w,h);cam.aspect=w/h;cam.updateProjectionMatrix()};
    const observer=new ResizeObserver(resize);observer.observe(host);resize();
    const onVisibility=()=>{visible=!document.hidden;last=0};document.addEventListener('visibilitychange',onVisibility);
    const onLost=e=>{e.preventDefault();setError('3D rendering paused. Reload to restore the scene.')};renderer.domElement.addEventListener('webglcontextlost',onLost);
    controller.current={update:(dir,u,cls)=>{wind={dir,u,cls};paintPlume()},pause:value=>{paused=value},reset:()=>{cam.position.set(-240,190,290);ctl.target.set(20,0,-10);ctl.update()}};
    controller.current.update(253,2,'D');
    function loop(time){if(disposed)return;frame=requestAnimationFrame(loop);if(!visible)return;const delta=last?Math.min((time-last)/16.67,2):1;last=time;if(!paused)step(delta);ctl.update();renderer.render(scene,cam);point.set(SCHOOL.x,14,SCHOOL.z).project(cam);if(tag.current){tag.current.style.left=((point.x+1)/2*host.clientWidth)+'px';tag.current.style.top=((1-point.y)/2*host.clientHeight)+'px';tag.current.style.display=point.z>1||Math.abs(point.x)>1||Math.abs(point.y)>1?'none':'block'}}
    frame=requestAnimationFrame(loop);
    teardown=()=>{disposed=true;cancelAnimationFrame(frame);observer.disconnect();document.removeEventListener('visibilitychange',onVisibility);renderer.domElement.removeEventListener('webglcontextlost',onLost);ctl.dispose();scene.traverse(obj=>{obj.geometry?.dispose();const mats=Array.isArray(obj.material)?obj.material:[obj.material];for(const mat of mats){if(!mat)continue;mat.dispose()}});tex.dispose();renderer.dispose();renderer.domElement.remove();controller.current=null};
    } catch {setError('3D is unavailable on this device. Use Geographic map to continue.')}
    return ()=>teardown()
  },[])
  useEffect(()=>controller.current?.update(direction,speed,stability),[direction,speed,stability])
  useEffect(()=>controller.current?.pause(!playing),[playing])
  return <div className="geo-three-scene"><div className="geo-three-mount" ref={mount}/><span className="geo-school-tag" ref={tag}>▦ {place?.name || 'School'} <small>illustrative</small></span>
    {error&&<div className="geo-three-error" role="alert">{error}</div>}
    <aside className="geo-wind-panel"><div className="geo-wind-title">WHAT-IF · WIND SCENARIO</div>
      <label htmlFor="scene-direction">Wind from <strong>{direction}°</strong></label><input id="scene-direction" type="range" min="0" max="359" value={direction} onChange={e=>setDirection(+e.target.value)}/>
      <label htmlFor="scene-speed">Wind speed <strong>{speed} m/s</strong></label><input id="scene-speed" type="range" min="1" max="12" step=".5" value={speed} onChange={e=>setSpeed(+e.target.value)}/>
      <label htmlFor="scene-stability">Stability class <select id="scene-stability" value={stability} onChange={e=>setStability(e.target.value)}>{['A','B','C','D','E','F'].map(s=><option key={s}>{s}</option>)}</select></label>
      <div className="geo-plume-legend"><span>Relative plume visualization</span><div/><p><span>Lower</span><span>Higher</span></p></div>
      <div className="geo-scene-actions"><button onClick={()=>setPlaying(!playing)}>{playing?<Pause size={14}/>:<Play size={14}/>} {playing?'Pause':'Play'}</button><button onClick={()=>controller.current?.reset()} title="Reset camera" aria-label="Reset camera"><RotateCcw size={14}/></button></div>
      <p className="geo-scene-disclaimer">Illustrative neighborhood and simplified model. Not measured exposure. Buildings are visual context.</p>
    </aside>
    <span className="geo-orbit-hint">Drag to orbit · scroll to zoom</span>
  </div>
}
