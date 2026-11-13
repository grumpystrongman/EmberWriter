// Deterministic fresh screenshot and DOM audit for the Author Experience Reviewer.
// Does not edit manuscripts, approve canon, publish, submit or upload any material.
// Requires an isolated synthetic project and the designated local Chrome debugger.
import fs from 'node:fs'
import path from 'node:path'

const root=path.resolve(import.meta.dirname,'..')
const date=new Date().toLocaleDateString('en-CA',{timeZone:'America/New_York'})
const runTag=process.argv[2]||date
const out=path.join(root,'docs','reviews','assets',runTag)
fs.mkdirSync(out,{recursive:true})
const backend='http://127.0.0.1:8000'
const projects=await(await fetch(backend+'/api/projects')).json()
if(projects.length!==1||!projects[0].name.includes('Synthetic Editorial Review')){
  throw Error('Safety stop: expected exactly one isolated synthetic editorial project, found '+projects.length)
}
const tabs=await(await fetch('http://127.0.0.1:9227/json')).json()
const target=tabs.find(x=>x.type==='page'&&x.url.startsWith('http://127.0.0.1:5173'))
if(!target)throw Error('No local synthetic-development Chrome tab')
const ws=new WebSocket(target.webSocketDebuggerUrl)
await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject})
let seq=0
const queue=new Map()
ws.onmessage=e=>{
  const msg=JSON.parse(e.data)
  if(!msg.id||!queue.has(msg.id))return
  const pending=queue.get(msg.id)
  queue.delete(msg.id)
  msg.error?pending.reject(Error(JSON.stringify(msg.error))):pending.resolve(msg.result)
}
function send(method,params={}){
  return new Promise((resolve,reject)=>{
    const id=++seq
    queue.set(id,{resolve,reject})
    ws.send(JSON.stringify({id,method,params}))
  })
}
async function js(expression){
  const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true})
  if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails))
  return r.result?.value
}
const sleep=ms=>new Promise(r=>setTimeout(r,ms))
async function wait(expr,label){
  for(let i=0;i<32;i++){
    if(await js(expr))return
    await sleep(250)
  }
  throw Error('Could not reach '+label)
}
async function navigateWorkspace(name){
  await js('localStorage.setItem("emberwriter.workspace",'+JSON.stringify(name)+');location.reload();true')
  await wait('!!document.querySelector(".project-card")','project card in '+name)
  await js('if(!document.querySelector(".project-card.active"))document.querySelector(".project-card")?.click();true')
  await wait('!!document.querySelector(".project-card.active")','selected synthetic project')
  const expected={
    write:'!!document.querySelector(".editor-header")',
    plan:'!!document.querySelector(".planning-groups")',
    analyze:'document.body.innerText.includes("Reader Perspectives & Critique")',
    publish:'!!document.querySelector(".pubdesk-journey")',
    series:'document.body.innerText.includes("Series Desk")',
  }
  await wait(expected[name],name+' authored workspace')
  await sleep(name==='publish'?1500:550)
}
async function capture(workspace,viewportWidth,viewportHeight,name){
  await send('Emulation.setDeviceMetricsOverride',{width:viewportWidth,height:viewportHeight,deviceScaleFactor:1,mobile:viewportWidth<600})
  await sleep(350)
  const checks=await js(`(()=>{
    const body=document.body;
    const visible=element=>{
      const bounds=element.getBoundingClientRect()
      const styles=getComputedStyle(element)
      return bounds.width>0&&bounds.height>0&&styles.visibility!=='hidden'&&styles.display!=='none'
    }
    const controls=[...document.querySelectorAll('button,a,[role=button],input,select,textarea')].filter(visible)
    const missing=controls.filter(el=>{
      const title=el.getAttribute('aria-label')||el.getAttribute('title')||el.innerText?.trim()||el.getAttribute('placeholder')||''
      return title.trim().length===0
    }).slice(0,18).map(el=>el.outerHTML.slice(0,180))
    const tiny=controls.filter(el=>{
      const r=el.getBoundingClientRect()
      return r.width<24||r.height<24
    }).slice(0,18).map(el=>({tag:el.tagName,text:(el.innerText||el.getAttribute('aria-label')||'').slice(0,46),width:Math.round(el.getBoundingClientRect().width),height:Math.round(el.getBoundingClientRect().height)}))
    return {
      title:document.title,
      viewport:innerWidth,
      documentWidth:document.documentElement.scrollWidth,
      bodyWidth:body.scrollWidth,
      heading:[...document.querySelectorAll('h1,h2,h3')].filter(visible).slice(0,12).map(e=>e.textContent?.trim()),
      visibleButtonCount:controls.length,
      unnamedControls:missing,
      smallControls:tiny,
      alertTexts:[...document.querySelectorAll('[role=alert]')].filter(visible).map(e=>e.textContent?.trim()).slice(0,10),
      firstViewportText:body.innerText.slice(0,850),
      currentWorkspace:localStorage.getItem('emberwriter.workspace'),
    }
  })()`)
  const r=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false})
  fs.writeFileSync(path.join(out,name+'.png'),Buffer.from(r.data,'base64'))
  const data={step:name,workspace,...checks,image:'assets/'+runTag+'/'+name+'.png'}
  console.log('AUDIT',JSON.stringify({step:name,width:checks.viewport,scroll:checks.documentWidth,headings:checks.heading.slice(0,3),unnamed:checks.unnamedControls.length,small:checks.smallControls.length,alerts:checks.alertTexts}))
  return data
}
const runs=[]
try{
  await send('Page.enable')
  await send('Page.navigate',{url:'http://127.0.0.1:5173/'})
  await wait('location.origin==="http://127.0.0.1:5173"','synthetic development site')
  for(const workspace of ['write','plan','analyze','publish','series']){
    await send('Emulation.setDeviceMetricsOverride',{width:1440,height:900,deviceScaleFactor:1,mobile:false})
    await navigateWorkspace(workspace)
    runs.push(await capture(workspace,1440,900,workspace+'-desktop'))
    runs.push(await capture(workspace,390,844,workspace+'-mobile'))
  }
  await send('Emulation.setDeviceMetricsOverride',{width:1440,height:900,deviceScaleFactor:1,mobile:false})
  await navigateWorkspace('publish')
  if(await js('!!document.querySelector(".pubdesk")')){
    runs.push(await capture('publish',900,800,'publish-tablet'))
    await js('document.querySelector(".pubdesk-journey button:nth-child(2)")?.click();true')
    await sleep(300)
    runs.push(await capture('publish',1440,900,'publish-interior-milestone'))
  }
  await navigateWorkspace('plan')
  if(await js('!!document.querySelector(".planning-groups")')){
    await js('([...document.querySelectorAll(".planning-groups button")].find(x=>x.innerText.includes("Edit & review"))||null)?.click();true')
    await sleep(250)
    await js('([...document.querySelectorAll(".planning-tool-tabs button")].find(x=>x.innerText.includes("Developmental studio"))||null)?.click();true')
    await sleep(500)
    if(await js('!!document.querySelector(".devstudio")')){
      runs.push(await capture('plan',1440,900,'editorial-desktop'))
      runs.push(await capture('plan',390,844,'editorial-mobile'))
    }
  }
  const baseline={
    date,
    runTag,
    source:'Fresh CDP capture of synthetic localhost application',
    synthetic_project:projects[0].name,
    timestamp:new Date().toISOString(),
    cases:runs,
  }
  fs.writeFileSync(path.join(root,'docs','reviews',runTag+'-evidence.json'),JSON.stringify(baseline,null,2))
  console.log('SUCCESS: captured',runs.length,'author UX screenshots. No writes to manuscript.')
}catch(e){
  console.error('AUDIT FAILED',e.stack||e)
  process.exitCode=1
}finally{ws.close()}
