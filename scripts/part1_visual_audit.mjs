// Part 1 synthetic-only Chrome CDP visual acceptance test.
// The backend must point to the isolated part1-demo-data directory.
import fs from 'node:fs'
import path from 'node:path'
const root=path.resolve(import.meta.dirname,'..')
const out=path.join(root,'docs','screenshots','part1-synthetic')
fs.mkdirSync(out,{recursive:true})
const series=await (await fetch('http://127.0.0.1:8000/api/series')).json()
if(series.length!==1||series[0].title!=='The Astral Lanterns')throw new Error('Refusing screenshots: synthetic-only series fixture not detected')
const targets=await (await fetch('http://127.0.0.1:9227/json')).json()
const target=targets.find(p=>p.type==='page'&&p.url.includes('127.0.0.1:5173'))
if(!target) throw new Error('Isolated synthetic Vite page not found')
const ws=new WebSocket(target.webSocketDebuggerUrl)
await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject})
let id=0;const pending=new Map()
ws.onmessage=(e)=>{const m=JSON.parse(e.data);if(m.id&&pending.has(m.id)){const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(Error(JSON.stringify(m.error))):p.resolve(m.result)}}
const send=(method,params={})=>new Promise((resolve,reject)=>{const k=++id;pending.set(k,{resolve,reject});ws.send(JSON.stringify({id:k,method,params}))})
async function evaluate(expression){const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw new Error(JSON.stringify(r.exceptionDetails));return r.result?.value}
const wait=async(ms=700)=>new Promise(resolve=>setTimeout(resolve,ms))
const must=async(condition,message)=>{for(let i=0;i<18;i++){if(await evaluate(condition))return;await wait(500)}throw new Error(message)}
const click=async(expression)=>{const r=await evaluate(expression);if(!r)throw Error('Could not click: '+expression);await wait(700)}
async function shot(name,width=1440,height=900){
 await send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:width<600})
 await wait(350)
 await evaluate('document.querySelector(".story-observatory")?.scrollIntoView({block:"start"});window.scrollBy(0,-6);true')
 await wait(350)
 const png=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false})
 const filename=`${name}-${width}.png`
 fs.writeFileSync(path.join(out,filename),Buffer.from(png.data,'base64'))
 const metrics=await evaluate(`({width:innerWidth,documentWidth:document.documentElement.scrollWidth,obs:!!document.querySelector('.story-observatory'),lens:[...document.querySelectorAll('.observatory-lenses button')].find(x=>x.getAttribute('aria-pressed')==='true')?.innerText,visibleFacts:document.querySelectorAll('.observatory-fact').length,errors:[...document.querySelectorAll('[role=alert]')].map(x=>x.innerText)})`)
 if(metrics.documentWidth>width+2)throw new Error('Horizontal overflow at '+width+': '+JSON.stringify(metrics))
 if(metrics.errors.some(x=>x.includes('intelligence unavailable')))throw new Error('Story-state fetch failed: '+metrics.errors)
 console.log('CAPTURE',filename,JSON.stringify(metrics))
}
try{
 await send('Page.enable')
 await send('Emulation.setDeviceMetricsOverride',{width:1440,height:900,deviceScaleFactor:1,mobile:false})
 await evaluate('localStorage.setItem("emberwriter.workspace","series");location.reload();true')
 await wait(2200)
 await must('!!document.querySelector(".story-observatory")','Story Observatory did not mount')
 await must('document.querySelectorAll(".observatory-graph-node").length>=8','Synthetic entities missing')
 await shot('01-universe')
 await click('([...document.querySelectorAll(".observatory-lenses button")].find(x=>x.innerText.includes("Character minds"))?.click(),true)')
 await shot('02-character-minds')
 await click('([...document.querySelectorAll(".observatory-lenses button")].find(x=>x.innerText.includes("Plot threads"))?.click(),true)')
 await must('document.querySelectorAll(".observatory-thread-card").length>0','Plot thread graph missing')
 await shot('03-plot-threads')
 await click('([...document.querySelectorAll(".observatory-lenses button")].find(x=>x.innerText.includes("Story history"))?.click(),true)')
 await shot('04-history')
 await click('([...document.querySelectorAll(".observatory-lenses button")].find(x=>x.innerText.includes("Model Lab"))?.click(),true)')
 await must('document.querySelectorAll(".model-lab-scenario").length===3','Model Lab tests not mounted')
 await shot('04b-model-lab')
 await click('([...document.querySelectorAll(".observatory-lenses button")].find(x=>x.innerText.includes("Universe"))?.click(),true)')
 await click('([...document.querySelectorAll(".observatory-book-track button")].find(x=>x.innerText.includes("BOOK 1"))?.click(),true)')
 await must('document.querySelectorAll(".observatory-fact").length>0','Book 1 evidence missing')
 await shot('05-book-one')
 await shot('06-tablet',900,800)
 await shot('07-mobile',390,844)
 await click('([...document.querySelectorAll(".observatory-lenses button")].find(x=>x.innerText.includes("Character minds"))?.click(),true)')
 await shot('08-mobile-psychology',390,844)
 await click('([...document.querySelectorAll(".observatory-lenses button")].find(x=>x.innerText.includes("Plot threads"))?.click(),true)')
 await shot('09-mobile-threads',390,844)
 console.log('PASS synthetic Part 1 visual interactive audit')
}catch(e){console.error('FAILED:',e.stack||e);process.exitCode=1}
finally{ws.close()}
