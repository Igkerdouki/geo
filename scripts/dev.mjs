// One terminal owns both processes; do not rely on an assistant's temporary server.
import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..')
const backend=path.join(root,'backend'),frontend=path.join(root,'frontend')
const children=new Set();let stopping=false
function stop(code=0){if(stopping)return;stopping=true;for(const child of children)child.kill('SIGTERM');process.exitCode=code}
process.on('SIGINT',()=>stop());process.on('SIGTERM',()=>stop())
function launch(command,args,cwd){const child=spawn(command,args,{cwd,stdio:'inherit',env:process.env});children.add(child);child.on('error',e=>{console.error(e.message);stop(1)});child.on('exit',(code)=>{children.delete(child);if(!stopping)stop(code||0)});return child}
async function healthy(){try{const r=await fetch('http://127.0.0.1:8001/health',{signal:AbortSignal.timeout(1000)});return r.ok&&(await r.json()).status==='healthy'}catch{return false}}
if(!await healthy()){
 const python=path.join(backend,'.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python')
 if(!existsSync(python)){console.error('Backend environment missing. Run: cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt');process.exitCode=1}
 else {
  console.log('Starting AskGaia API on http://127.0.0.1:8001 …')
  launch(python,['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8001','--reload'],backend)
  let ready=false
  for(let i=0;i<60&&!stopping;i++){if(await healthy()){ready=true;break}await new Promise(r=>setTimeout(r,500))}
  if(!ready&&!stopping){console.error('API did not start. Check the backend error above.');stop(1)}
 }
}else console.log('Using the running AskGaia API on port 8001.')
if(!stopping&&!process.exitCode)launch(process.execPath,[path.join(frontend,'node_modules/vite/bin/vite.js'),...process.argv.slice(2)],frontend)
