// Part 3: synthetic only, actual browser screenshots and interactions.
import fs from 'node:fs'
import path from 'node:path'
const root=path.resolve(import.meta.dirname,'..'),out=path.join(root,'docs','screenshots','part3-synthetic')
fs.mkdirSync(out,{recursive:true})
const projects=await(await fetch('http://127.0.0.1:8000/api/projects')).json()
if(projects.length!==1||!projects[0].name.includes('Synthetic Editorial Review'))throw Error('Refusing non-synthetic workspace')
const targets=await(await fetch('http://127.0.0.1:9227/json')).json()
const page=targets.find(t=>t.type==='page'&&t.url.includes('127.0.0.1:5173'))
if(!page)throw Error('Missing synthetic browser')
const ws=new WebSocket(page.webSocketDebuggerUrl)
await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j})
let seq=0;const pending=new Map()
ws.onmessage=e=>{const x=JSON.parse(e.data);if(x.id&&pending.has(x.id)){const p=pending.get(x.id);pending.delete(x.id);x.error?p.reject(Error(JSON.stringify(x.error))):p.resolve(x.result)}}
const send=(method,params={})=>new Promise((resolve,reject)=>{const i=++seq;pending.set(i,{resolve,reject});ws.send(JSON.stringify({id:i,method,params}))})
async function js(expression){const result=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(result.exceptionDetails)throw Error(JSON.stringify(result.exceptionDetails));return result.result?.value}
const pause=ms=>new Promise(r=>setTimeout(r,ms))
async function waitFor(expression,message){for(let i=0;i<30;i++){if(await js(expression))return;await pause(300)}throw Error(message)}
async function click(expression){const result=await js(expression);if(!result)throw Error('Missing control: '+expression);await pause(420)}
async function screenshot(label,width=1440,height=900){
 await send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:width<600})
 await js('document.querySelector(".devstudio")?.scrollIntoView({block:"start"});true')
 await pause(500)
 const {data}=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false})
 fs.writeFileSync(path.join(out,label+'.png'),Buffer.from(data,'base64'))
 const metric=await js('({viewport:innerWidth,document:document.documentElement.scrollWidth,studio:document.querySelector(".devstudio")?.clientWidth,studioScroll:document.querySelector(".devstudio")?.scrollWidth,alerts:[...document.querySelectorAll(".devstudio-error")].map(x=>x.innerText)})')
 console.log('CAPTURE',label,JSON.stringify(metric))
 if(metric.document>width+2||metric.studioScroll>metric.studio+5)throw Error('Overflow '+JSON.stringify(metric))
 if(metric.alerts.length)throw Error('UI error: '+metric.alerts.join(';'))
}
try{
 await send('Page.enable');await send('Emulation.setDeviceMetricsOverride',{width:1440,height:900,deviceScaleFactor:1,mobile:false})
 await js('localStorage.setItem("emberwriter.workspace","plan");location.reload();true');await pause(1800)
 await waitFor('!!document.querySelector(".project-card")','Synthetic project missing')
 await click('document.querySelector(".project-card")?.click(),true')
 await waitFor('!!document.querySelector(".planning-groups")','Planning Hub did not load')
 await click('([...document.querySelectorAll(".planning-groups button")].find(x=>x.innerText.includes("Edit & review"))?.click(),true)')
 await click('([...document.querySelectorAll(".planning-tool-tabs button")].find(x=>x.innerText.includes("Developmental studio"))?.click(),true)')
 await waitFor('!!document.querySelector(".devstudio-pulse-layout")','Developmental overview did not render')
 await screenshot('01-manuscript-pulse-desktop')
 await click('([...document.querySelectorAll(".devstudio-bars button")][1]?.click(),true)')
 await screenshot('02-chapter-inspector-desktop')
 await js('document.querySelectorAll(".devstudio-nav button")[1].click();true');await pause(350)
 await waitFor('!!document.querySelector(".devstudio-track-form")','Arc atlas not mounted')
 await screenshot('03-arc-atlas-empty')
 await js('(()=>{const input=document.querySelector(".devstudio-track-form input");const setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,"value").set;setter.call(input,"Mira, Tavi, glass compass");input.dispatchEvent(new Event("input",{bubbles:true}));return true})()')
 await click('document.querySelector(".devstudio-track-form button")?.click(),true')
 await waitFor('document.querySelectorAll(".devstudio-presence tbody tr").length===3','Subject presence missing')
 await screenshot('04-arc-atlas-tracked')
 await click('document.querySelector(".devstudio-presence td button.present")?.click(),true')
 await screenshot('05-arc-evidence')
 await js('document.querySelectorAll(".devstudio-nav button")[3].click();true');await pause(350)
 await js('document.querySelectorAll(".devstudio-revision-toolbar button")[0].click();true');await pause(350)
 await waitFor('document.querySelectorAll(".devstudio-paragraph").length>=3','Revision paragraphs not loaded')
 await screenshot('06-revision-workbench')
 await js('(()=>{const area=document.querySelector(".devstudio-paragraph textarea");const setter=Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,"value").set;setter.call(area,area.value+" Carefully revised.");area.dispatchEvent(new Event("input",{bubbles:true}));return true})()')
 await waitFor('!!document.querySelector(".devstudio-paragraph.modified")','Edited paragraph not marked')
 await screenshot('07-edited-paragraph')
 await screenshot('08-mobile-revision',390,844)
 await js('document.querySelectorAll(".devstudio-nav button")[0].click();true');await pause(350)
 await screenshot('09-mobile-pulse',390,844)
 await js('document.querySelectorAll(".devstudio-nav button")[1].click();true');await pause(350)
 await screenshot('10-mobile-arcs',390,844)
 await screenshot('11-tablet-arcs',900,800)
 console.log('PASS Part 3 synthetic browser acceptance')
}catch(e){console.error('FAILED',e.stack||e);process.exitCode=1}
finally{ws.close()}


