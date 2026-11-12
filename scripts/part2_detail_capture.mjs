// Detailed evidence screenshots for Part Two: only synthetic demonstration series.
import fs from 'node:fs';import path from 'node:path'
const root=path.resolve(import.meta.dirname,'..'),out=path.join(root,'docs','screenshots','part2-synthetic')
const series=await(await fetch('http://127.0.0.1:8000/api/series')).json()
if(series.length!==1||series[0].title!=='The Astral Lanterns')throw Error('Safety: demo data expected')
const targets=await(await fetch('http://127.0.0.1:9227/json')).json(),page=targets.find(x=>x.type==='page'&&x.url.includes('127.0.0.1:5173'))
const ws=new WebSocket(page.webSocketDebuggerUrl);await new Promise(r=>ws.onopen=r)
let id=0;const p=new Map();ws.onmessage=e=>{const m=JSON.parse(e.data);if(!m.id||!p.has(m.id))return;const q=p.get(m.id);p.delete(m.id);m.error?q.reject(Error(JSON.stringify(m.error))):q.resolve(m.result)}
const send=(method,params={})=>new Promise((resolve,reject)=>{const i=++id;p.set(i,{resolve,reject});ws.send(JSON.stringify({id:i,method,params}))})
const js=async expression=>{const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result?.value}
const sleep=ms=>new Promise(r=>setTimeout(r,ms))
async function screenshot(name,selector){
 const found=await js('Boolean(document.querySelector('+JSON.stringify(selector)+'))')
 if(!found)throw Error('Missing '+selector)
 await js('document.querySelector('+JSON.stringify(selector)+').scrollIntoView({block:"start"});window.scrollBy(0,-55);true')
 await sleep(550)
 const data=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false})
 fs.writeFileSync(path.join(out,name+'.png'),Buffer.from(data.data,'base64'));console.log('SHOT',name)
}
try{
 await send('Page.enable');await send('Emulation.setDeviceMetricsOverride',{width:1440,height:900,deviceScaleFactor:1,mobile:false})
 await js('localStorage.setItem("emberwriter.workspace","series");location.reload();true');await sleep(1800)
 for(let i=0;i<20&&!await js('!!document.querySelector(".series-desk-tabs")');i++)await sleep(400)
 await js('([...document.querySelectorAll(".series-desk-tabs button")].find(b=>b.innerText.includes("Character & Scene Studio"))?.click(),true)');await sleep(1100)
 await js('([...document.querySelectorAll(".p2-cast-button")].find(b=>b.innerText.includes("Seren"))?.click(),true)');await sleep(320)
 await screenshot('11-character-evidence-details','.p2-character-detail')
 await js('([...document.querySelectorAll(".p2-navigation button")].find(b=>b.innerText.includes("Relationship orbit"))?.click(),true)');await sleep(400)
 await screenshot('12-bond-timeline-details','.p2-relationship-layout')
 await js('([...document.querySelectorAll(".p2-navigation button")].find(b=>b.innerText.includes("Scene Director"))?.click(),true)');await sleep(420)
 await js('document.querySelector(".p2-saved-boards button")?.click();true');await sleep(330)
 await screenshot('13-beat-tension-detail','.p2-tension-chart')
 await screenshot('14-scene-director-inspectors','.p2-director-bottom')
 await screenshot('15-before-after-ledger','.p2-before-after')
 await js('([...document.querySelectorAll(".p2-continuity-console button")].find(b=>b.innerText.includes("Check this scene"))?.click(),true)');await sleep(700)
 await screenshot('16-continuity-guardian-results','.p2-continuity-console')
}finally{ws.close()}
