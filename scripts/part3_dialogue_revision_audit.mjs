// Synthetic-only Part 3 Dialogue Studio and author-approved paragraph revision acceptance.
import fs from 'node:fs'
import path from 'node:path'
const root=path.resolve(import.meta.dirname,'..')
const out=path.join(root,'docs','screenshots','part3-synthetic')
fs.mkdirSync(out,{recursive:true})
const projects=await(await fetch('http://127.0.0.1:8000/api/projects')).json()
if(projects.length!==1||!projects[0].name.includes('Synthetic Editorial Review'))throw Error('Not synthetic: no UI mutations permitted')
const slug=projects[0].slug
const endpoint='http://127.0.0.1:8000/api/projects/'+slug+'/developmental-editor'
const targets=await(await fetch('http://127.0.0.1:9227/json')).json()
const page=targets.find(x=>x.type==='page'&&x.url.includes('127.0.0.1:5173'))
if(!page)throw Error('No synthetic Chrome')
const ws=new WebSocket(page.webSocketDebuggerUrl);await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j})
let seq=0;const pending=new Map()
ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.id&&pending.has(m.id)){const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(Error(JSON.stringify(m.error))):p.resolve(m.result)}}
const send=(method,params={})=>new Promise((resolve,reject)=>{const id=++seq;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}))})
const js=async expression=>{const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result?.value}
const sleep=ms=>new Promise(r=>setTimeout(r,ms))
const wait=async(expression,message)=>{for(let i=0;i<35;i++){if(await js(expression))return;await sleep(300)}throw Error(message)}
async function screenshot(name,width=1440,height=900,selector='.devstudio'){
 await send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:width<600})
 await js('document.querySelector('+JSON.stringify(selector)+')?.scrollIntoView({block:"start"});true')
 await sleep(500)
 const capture=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false})
 fs.writeFileSync(path.join(out,name+'.png'),Buffer.from(capture.data,'base64'))
 const metrics=await js('({viewport:innerWidth,document:document.documentElement.scrollWidth,studio:document.querySelector(".devstudio")?.clientWidth,scroll:document.querySelector(".devstudio")?.scrollWidth,errors:[...document.querySelectorAll(".devstudio-error")].map(x=>x.innerText)})')
 if(metrics.document>width+2||metrics.scroll>metrics.studio+5||metrics.errors.length)throw Error('Layout or UI error: '+JSON.stringify(metrics))
 console.log('CAPTURE',name,JSON.stringify(metrics))
}
try{
 await send('Page.enable');await send('Emulation.setDeviceMetricsOverride',{width:1440,height:900,deviceScaleFactor:1,mobile:false})
 await js('localStorage.setItem("emberwriter.workspace","plan");location.reload();true')
 await wait('!!document.querySelector(".project-card")','Project not found')
 await js('document.querySelector(".project-card").click();true')
 await wait('!!document.querySelector(".planning-groups")','Planning Hub missing')
 await js('([...document.querySelectorAll(".planning-groups button")].find(b=>b.innerText.includes("Edit & review"))).click();true')
 await js('([...document.querySelectorAll(".planning-tool-tabs button")].find(b=>b.innerText.includes("Developmental studio"))).click();true')
 await wait('!!document.querySelector(".devstudio-nav")','Editorial studio missing')
 await js('document.querySelectorAll(".devstudio-nav button")[2].click();true')
 await wait('document.querySelectorAll(".devstudio-voice-cast button").length>0','Dialogue analysis missing')
 const quotes=await js('({names:[...document.querySelectorAll(".devstudio-voice-cast button")].map(x=>x.innerText),quote:document.querySelector(".devstudio-voice-detail blockquote")?.innerText})')
 console.log('VOICES',JSON.stringify(quotes))
 await screenshot('12-dialogue-studio-desktop')
 await js('document.querySelectorAll(".devstudio-voice-cast button")[1]?.click();true')
 await screenshot('13-dialogue-speaker-comparison',1440,900,'.devstudio-voice-detail')
 await screenshot('14-dialogue-mobile',390,844,'.devstudio-dialogue')
 await send('Emulation.setDeviceMetricsOverride',{width:1440,height:900,deviceScaleFactor:1,mobile:false})
 await js('document.querySelectorAll(".devstudio-nav button")[3].click();true')
 await sleep(400)
 await js('document.querySelector(".devstudio-revision-toolbar button").click();true')
 await wait('document.querySelectorAll(".devstudio-paragraph").length>=3','Revision document not loaded')
 const pathname=await js('document.querySelector(".devstudio-revision-toolbar select").value')
 const before=await(await fetch(endpoint+'/document?'+new URLSearchParams({path:pathname}))).json()
 const selected=before.paragraphs.find(p=>p.text.includes('Mira approached'))||before.paragraphs[1]
 const index=before.paragraphs.indexOf(selected)
 const replacement=selected.text+' The silence made her rethink the warning.'
 const execute="(()=>{const area=document.querySelectorAll('.devstudio-paragraph textarea')["+index+"];const setter=Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set;setter.call(area,"+JSON.stringify(replacement)+");area.dispatchEvent(new Event('input',{bubbles:true}));return true})()"
 await js(execute)
 await wait('document.querySelectorAll(".devstudio-paragraph.modified").length===1','Modified preview not shown')
 await js('document.querySelector(".devstudio-paragraph.modified input[type=checkbox]").click();true')
 await wait('document.querySelector(".devstudio-revision-footer strong")?.innerText.includes("1 selected")','Selected edit count missing')
 await screenshot('15-revision-selected-diff',1440,900,'.devstudio-paragraph.modified')
 await js('document.querySelector(".devstudio-revision-footer .devstudio-primary").click();true')
 await wait('!!document.querySelector(".devstudio-confirmation")','Review confirmation missing')
 await screenshot('16-revision-confirmation',1440,900,'.devstudio-confirmation')
 await js('document.querySelector(".devstudio-confirmation .devstudio-primary").click();true')
 await wait('!!document.querySelector(".devstudio-message:not(.devstudio-error)")','Success message missing')
 const after=await(await fetch(endpoint+'/document?'+new URLSearchParams({path:pathname}))).json()
 if(after.source_hash===before.source_hash)throw Error('Source not updated')
 if(!after.content.includes(replacement))throw Error('Approved paragraph absent')
 for(const para of before.paragraphs.filter(p=>p.id!==selected.id)){
   if(!after.content.includes(para.text))throw Error('Unselected paragraph changed: '+para.id)
 }
 if(after.revision_history.length<2)throw Error('Previous revision not archived')
 console.log('PASS actual user-approved revision:',JSON.stringify({path:pathname,originalHash:before.source_hash.slice(0,9),newHash:after.source_hash.slice(0,9),revisionCount:after.revision_history.length}))
 await screenshot('17-revision-accepted',1440,900,'.devstudio-revision')
 console.log('PASS Part 3 dialogue/revision acceptance')
}catch(e){console.error('FAILED',e.stack||e);process.exitCode=1}
finally{ws.close()}
