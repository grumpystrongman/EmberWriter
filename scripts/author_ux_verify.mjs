// UX Scorecard acceptance — real Chromium interactions on an isolated synthetic book.
// No model calls, user manuscript changes, destructive actions, or retailer upload.
import fs from 'node:fs'
import path from 'node:path'
import assert from 'node:assert/strict'

const root=path.resolve(import.meta.dirname,'..')
const folder=path.join(root,'docs','reviews','assets','2026-11-12-scorecard-interactions')
fs.mkdirSync(folder,{recursive:true})
const projects=await(await fetch('http://127.0.0.1:8000/api/projects')).json()
assert.equal(projects.length,1,'Only the isolated synthetic book can be audited')
assert.match(projects[0].name,/Synthetic Editorial Review/)
const browsers=await(await fetch('http://127.0.0.1:9227/json')).json()
const tab=browsers.find(entry=>entry.type==='page'&&entry.url.startsWith('http://127.0.0.1:5173'))
assert.ok(tab,'Expected local development Chrome')
const ws=new WebSocket(tab.webSocketDebuggerUrl)
await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject})
let serial=0
const pending=new Map()
ws.onmessage=e=>{
 const m=JSON.parse(e.data)
 if(m.id&&!pending.has(m.id))return
 const p=pending.get(m.id)
 if(!p)return
 pending.delete(m.id)
 m.error?p.reject(Error(JSON.stringify(m.error))):p.resolve(m.result)
}
function send(method,params={}){
 return new Promise((resolve,reject)=>{
  const id=++serial
  pending.set(id,{resolve,reject})
  ws.send(JSON.stringify({id,method,params}))
 })
}
async function js(expression){
 const out=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true})
 if(out.exceptionDetails)throw Error(JSON.stringify(out.exceptionDetails))
 return out.result?.value
}
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms))
async function until(expr,label){
 for(let i=0;i<45;i++){if(await js(expr))return;await delay(250)}
 throw Error('Could not locate '+label)
}
async function tap(selector){
 const result=await js('(()=>{const e=document.querySelector('+JSON.stringify(selector)+');if(!e)return false;e.click();return true})()')
 assert.equal(result,true,'Missing control '+selector)
}
async function size(width,height){
 await send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:width<600})
}
async function shot(name,width=390,height=844){
 await size(width,height);await delay(360)
 const data=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false})
 fs.writeFileSync(path.join(folder,name+'.png'),Buffer.from(data.data,'base64'))
 const geo=await js('({inner:innerWidth,body:document.documentElement.scrollWidth,nav:!!document.querySelector(".workspace-mobile-nav"),view:document.querySelector(".workspace-shell")?.dataset.workspace})')
 assert.ok(geo.body<=width+2,'Horizontal overflow '+name+JSON.stringify(geo))
 console.log('SCREENSHOT',name,JSON.stringify(geo))
}
async function openBook(workspace){
 await size(1440,900)
 await send('Page.navigate',{url:'http://127.0.0.1:5173/'})
 await until('location.origin==="http://127.0.0.1:5173"','local frontend')
 await js('localStorage.setItem("emberwriter.workspace",'+JSON.stringify(workspace)+');location.reload();true')
 await until('!!document.querySelector(".project-card")','project')
 await js('if(!document.querySelector(".project-card.active"))document.querySelector(".project-card").click();true')
 await until('!!document.querySelector(".project-card.active")','active synthetic project')
 await until('document.querySelector(".workspace-shell")?.dataset.workspace==='+JSON.stringify(workspace),'workspace '+workspace)
 await delay(400)
}
const results=[]
try{
 await send('Page.enable')
 await openBook('write')
 await size(390,844)
 await until('document.querySelectorAll(".workspace-mobile-nav button").length===5','mobile tabs')
 await shot('01-mobile-navigation-write')
 for(const [n,name] of [[2,'plan'],[3,'series'],[4,'publish']]){
   await tap('.workspace-mobile-nav button:nth-child('+n+')')
   await until('document.querySelector(".workspace-shell")?.dataset.workspace==='+JSON.stringify(name),'navigation to '+name)
   await shot('0'+n+'-mobile-navigation-'+name)
   results.push({test:'mobile '+name,pass:true})
 }
 await tap('.workspace-mobile-nav button:last-child')
 await until('!!document.querySelector(".workspace-mobile-more")','more workspace tray')
 await shot('05-mobile-more-navigation')
 await tap('.workspace-mobile-more button')
 await until('document.querySelector(".workspace-shell")?.dataset.workspace!=="publish"','More navigation')
 results.push({test:'mobile More menu navigation',pass:true})

 await openBook('write')
 await size(390,844)
 await until('!!document.querySelector(".ember-companion-launcher")','Ember launch control')
 await tap('.ember-companion-launcher')
 await until('!!document.querySelector(".ember-companion-help-trigger")','Ember built-in help')
 await tap('.ember-companion-help-trigger')
 await until('!!document.querySelector(".ember-guides")','offline guide library')
 await shot('06-ember-offline-help')
 await tap('.ember-guide-card')
 await until('!!document.querySelector(".ember-guide-step")','first guide step')
 await shot('07-ember-guided-step')
 assert.ok(await js('document.querySelector(".ember-guide-step")?.innerText.includes("STEP 1")'))
 await tap('.ember-guide-step .ember-guide-locate')
 await until('!!document.querySelector(".ember-guide-result")','feedback for missing/located control')
 await shot('08-ember-control-location')
 await tap('.ember-guide-controls button:last-child')
 assert.ok(await js('document.querySelector(".ember-guide-step")?.innerText.includes("STEP 2")'))
 results.push({test:'offline how-to library, explicit step progression, truthful locate feedback',pass:true})

 await openBook('series')
 await until('document.querySelectorAll(".series-experience-modes button").length===4','four series modes')
 await shot('09-series-modes',1440,900)
 await tap('.series-experience-modes button:nth-child(3)')
 await until('!!document.querySelector(".series-verify-tools")','verification subnavigation')
 await shot('10-series-verify-tools',1440,900)
 results.push({test:'series task grouping and verification submenu',pass:true})

 const series=await(await fetch('http://127.0.0.1:8000/api/series')).json()
 const boards=series.length?await(await fetch('http://127.0.0.1:8000/api/series/'+series[0].id+'/scene-boards')).json():[]
 console.log('Synthetic scene boards available:',boards.length)
 if(boards.length>0){
  await tap('.series-experience-modes button:nth-child(2)')
  await until('!!document.querySelector(".p2-studio")','scene director studio')
  const sceneTab=await js('([...document.querySelectorAll(".p2-studio button")].find(e=>e.textContent?.includes("Scene Director"))?.outerHTML||"")')
  assert.ok(sceneTab,'Missing Scene Director tab')
  await js('([...document.querySelectorAll(".p2-studio button")].find(e=>e.textContent?.includes("Scene Director")))?.click();true')
  await until('document.querySelectorAll(".p2-saved-boards button").length>0','loaded saved scene boards')
  await js('document.querySelector(".p2-saved-boards button").click();true')
  await until('!!document.querySelector(".p2-board-actions")','selected board')
  const enabled=await js('([...document.querySelectorAll(".p2-board-actions button")].find(e=>e.textContent?.includes("Send to Scene Writer"))?.disabled===false)')
  if(enabled){
   await js('([...document.querySelectorAll(".p2-board-actions button")].find(e=>e.textContent?.includes("Send to Scene Writer"))).click();true')
   await until('!!document.querySelector(".p2-handoff-confirm")','author handoff confirmation')
   await shot('11-scene-writer-handoff-confirmation',1440,900)
   await tap('.p2-handoff-confirm button:first-of-type')
   await until('document.querySelector(".workspace-shell")?.dataset.workspace==="studio"','Scene Writer handoff')
   await until('document.querySelector(".ai-studio-compose .ai-studio-card textarea")?.value.includes("SCENE:")','injected scene prompt')
   await shot('12-saved-scene-brief-in-writer',1440,900)
   results.push({test:'saved storyboard -> explicit author confirmation -> Scene Writer prompt (no manuscript overwrite)',pass:true})
  }else{
   results.push({test:'scene handoff',pass:false,reason:'Selected storyboard is not saved/clean; test requires saved fixture'})
  }
 }else{
  results.push({test:'scene handoff',pass:false,reason:'No pre-existing saved synthetic scene board fixture'})
 }
 fs.writeFileSync(path.join(root,'docs','reviews','2026-11-12-scorecard-interactions.json'),JSON.stringify({
  date:'2026-11-12',synthetic:projects[0].name,results
 },null,2))
 console.log('INTERACTION_ACCEPTANCE',JSON.stringify(results))
 if(results.some(entry=>!entry.pass))process.exitCode=2
}catch(e){
 console.error('INTERACTION FAILED',e.stack||e);process.exitCode=1
}finally{ws.close()}
