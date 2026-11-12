// Browser screenshots of actual Part 1 rebuild, not mockups.
// Includes scrolled detail and mobile views that document-overflow checks missed.
import fs from 'node:fs'
import path from 'node:path'
const root=path.resolve(import.meta.dirname,'..')
const out=path.join(root,'docs','screenshots','part1-rebuild')
fs.mkdirSync(out,{recursive:true})
const series=await(await fetch('http://127.0.0.1:8000/api/series')).json()
if(series.length!==1||series[0].title!=='The Astral Lanterns'||series[0].volume_count!==4)throw Error('Synthetic fixture required')
const target=(await(await fetch('http://127.0.0.1:9227/json')).json()).find(t=>t.type==='page'&&t.url.startsWith('http://127.0.0.1:5173'))
if(!target)throw Error('Browser unavailable')
const ws=new WebSocket(target.webSocketDebuggerUrl)
await new Promise((res,rej)=>{ws.onopen=res;ws.onerror=rej})
let i=0;const pending=new Map()
ws.onmessage=e=>{const m=JSON.parse(e.data),p=pending.get(m.id);if(p){pending.delete(m.id);m.error?p.reject(Error(JSON.stringify(m.error))):p.resolve(m.result)}}
const send=(method,params={})=>new Promise((resolve,reject)=>{const id=++i;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}))})
const evalJs=async expr=>{const r=await send('Runtime.evaluate',{expression:expr,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result?.value}
const sleep=t=>new Promise(r=>setTimeout(r,t))
async function capture(name,selector,width=1440,height=900){
 await send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:width<600})
 await sleep(500)
 await evalJs('document.querySelector('+JSON.stringify(selector)+')?.scrollIntoView({block:"start"});true')
 await sleep(450)
 const png=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false})
 fs.writeFileSync(path.join(out,name+'.png'),Buffer.from(png.data,'base64'))
 const metrics=await evalJs('({vw:innerWidth,scroll:document.documentElement.scrollWidth,box:document.querySelector('+JSON.stringify(selector)+')?.getBoundingClientRect().width})')
 if(metrics.scroll>width+2||metrics.box>width+2)throw Error('Clipped capture '+name+JSON.stringify(metrics))
 console.log(name,JSON.stringify(metrics))
}
const tab=async term=>{await evalJs('([...document.querySelectorAll(".observatory-lenses button")].find(x=>x.innerText.includes('+JSON.stringify(term)+'))?.click(),true)');await sleep(600)}
try{
 await send('Page.enable')
 await send('Emulation.setDeviceMetricsOverride',{width:1440,height:900,deviceScaleFactor:1,mobile:false})
 await evalJs('localStorage.setItem("emberwriter.workspace","series");location.reload();true')
 await sleep(2300)
 await tab('Discover')
 await capture('12-discovery-ledger-detail','.discovery-layout')
 await capture('13-deep-read-controls','.discovery-deep-read')
 await capture('14-mobile-ledger','.discovery-layout',390,844)
 await capture('15-mobile-inspector','.discovery-inspector',390,844)
 await send('Emulation.setDeviceMetricsOverride',{width:1440,height:900,deviceScaleFactor:1,mobile:false})
 await tab('Universe')
 await evalJs('(()=>{const b=document.querySelector(".observatory-utility-bar button");if(b?.getAttribute("aria-pressed")!=="true")b?.click();return true})()')
 await sleep(650)
 await capture('16-immersive-graph','.observatory-main')
 await evalJs('document.querySelector(".observatory-utility-bar button")?.click();true')
 await sleep(300)
 await tab('Character minds')
 await capture('17-character-mind-evidence','.observatory-psychology-body')
 await tab('Plot threads')
 await capture('18-story-thread-rails','.observatory-thread-list')
 console.log('PASS detailed synthetic screenshots')
}catch(e){console.error('FAILED',e.stack||e);process.exitCode=1}
finally{ws.close()}
