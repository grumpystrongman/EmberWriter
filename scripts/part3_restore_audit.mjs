import fs from 'node:fs'
import path from 'node:path'
const out=path.resolve(import.meta.dirname,'../docs/screenshots/part3-synthetic')
const ps=await(await fetch('http://127.0.0.1:8000/api/projects')).json()
if(ps.length!==1||!ps[0].name.includes('Synthetic Editorial Review'))throw Error('Only synthetic demo may be revised')
const prefix='http://127.0.0.1:8000/api/projects/'+ps[0].slug+'/developmental-editor'
const pages=await(await fetch('http://127.0.0.1:9227/json')).json(),page=pages.find(p=>p.type==='page'&&p.url.includes('127.0.0.1:5173'))
const ws=new WebSocket(page.webSocketDebuggerUrl);await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j})
let index=0;const pending=new Map();ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.id&&pending.has(m.id)){const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(Error(JSON.stringify(m.error))):p.resolve(m.result)}}
const send=(method,params={})=>new Promise((resolve,reject)=>{const id=++index;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}))})
const js=async e=>{const r=await send('Runtime.evaluate',{expression:e,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result?.value}
const sleep=ms=>new Promise(r=>setTimeout(r,ms));const wait=async(expr,label)=>{for(let i=0;i<35;i++){if(await js(expr))return;await sleep(300)}throw Error('Missing '+label)}
const shot=async(name,selector)=>{await js('document.querySelector('+JSON.stringify(selector)+').scrollIntoView({block:"center"});true');await sleep(440);const r=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});fs.writeFileSync(path.join(out,name+'.png'),Buffer.from(r.data,'base64'));console.log('SHOT',name)}
try{
 await send('Page.enable');await send('Emulation.setDeviceMetricsOverride',{width:1440,height:900,deviceScaleFactor:1,mobile:false})
 await js('localStorage.setItem("emberwriter.workspace","plan");location.reload();true')
 await wait('!!document.querySelector(".project-card")','project');await js('document.querySelector(".project-card").click();true')
 await wait('!!document.querySelector(".planning-groups")','planning')
 await js('([...document.querySelectorAll(".planning-groups button")].find(x=>x.innerText.includes("Edit & review"))).click();true')
 await js('([...document.querySelectorAll(".planning-tool-tabs button")].find(x=>x.innerText.includes("Developmental studio"))).click();true')
 await wait('!!document.querySelector(".devstudio-nav")','studio')
 await js('document.querySelectorAll(".devstudio-nav button")[3].click();true')
 await wait('!!document.querySelector(".devstudio-revision-toolbar button")','revision toolbar')
 await js('document.querySelector(".devstudio-revision-toolbar button").click();true')
 await wait('!!document.querySelector(".devstudio-history summary")','revisions')
 const pagePath=await js('document.querySelector(".devstudio-revision-toolbar select").value')
 const old=await(await fetch(prefix+'/document?'+new URLSearchParams({path:pagePath}))).json()
 if(!old.content.includes('rethink the warning'))throw Error('Edited synthetic fixture not found')
 await js('document.querySelector(".devstudio-history summary").click();true')
 await wait('document.querySelectorAll(".devstudio-history button").length>0','restore action')
 const restoreInfo=await js('([...document.querySelectorAll(".devstudio-history button")].map(x=>({disabled:x.disabled,label:x.innerText})))')
 console.log('REVISIONS',JSON.stringify(restoreInfo))
 await js('([...document.querySelectorAll(".devstudio-history button")].find(x=>!x.disabled)).click();true')
 await wait('!!document.querySelector(".devstudio-confirmation")','restore confirmation')
 await shot('18-restore-confirmation','.devstudio-confirmation')
 await js('document.querySelector(".devstudio-confirmation .devstudio-primary").click();true')
 await wait('!!document.querySelector(".devstudio-message:not(.devstudio-error)")','restore result')
 const restored=await(await fetch(prefix+'/document?'+new URLSearchParams({path:pagePath}))).json()
 if(restored.content.includes('rethink the warning'))throw Error('Original not restored')
 if(restored.revision_history.length<3)throw Error('Restore revision not recorded')
 console.log('PASS safe author-approved revision restoration',JSON.stringify({revisions:restored.revision_history.length,hash:restored.source_hash.slice(0,12)}))
 await shot('19-restored-revision','.devstudio-revision')
}catch(e){console.error('FAILED',e.stack||e);process.exitCode=1}finally{ws.close()}
