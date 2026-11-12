// Synthetic-only detailed viewport capture for Story Observatory panels.
import fs from 'node:fs'
import path from 'node:path'
const root=path.resolve(import.meta.dirname,'..')
const out=path.join(root,'docs','screenshots','part1-synthetic')
const series=await(await fetch('http://127.0.0.1:8000/api/series')).json()
if(series.length!==1||series[0].title!=='The Astral Lanterns')throw Error('Refusing non-synthetic capture')
const targets=await(await fetch('http://127.0.0.1:9227/json')).json()
const target=targets.find(t=>t.type==='page'&&t.url.includes('127.0.0.1:5173'))
if(!target)throw Error('No isolated browser')
const ws=new WebSocket(target.webSocketDebuggerUrl)
await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j})
let seq=0;const pending=new Map()
ws.onmessage=event=>{const msg=JSON.parse(event.data);if(!msg.id)return;const p=pending.get(msg.id);if(!p)return;pending.delete(msg.id);msg.error?p.reject(Error(JSON.stringify(msg.error))):p.resolve(msg.result)}
const send=(method,params={})=>new Promise((resolve,reject)=>{const id=++seq;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}))})
const evaluate=async expr=>(await send('Runtime.evaluate',{expression:expr,returnByValue:true,awaitPromise:true})).result.value
const wait=ms=>new Promise(r=>setTimeout(r,ms))
try{
 await send('Page.enable')
 await send('Emulation.setDeviceMetricsOverride',{width:1440,height:900,deviceScaleFactor:1,mobile:false})
 await evaluate('localStorage.setItem("emberwriter.workspace","series");location.reload();true')
 await wait(2500)
 for(const [tab,selector,label] of [
 ['Universe','.observatory-network','16-graph-detail'],
 ['Character minds','.observatory-psychology-body','17-psychology-detail'],
 ['Plot threads','.observatory-thread-list','18-threads-detail'],
 ['Story history','.observatory-chronicle-track','19-history-detail'],
 ['Model Lab','.model-lab-console','20-model-lab-controls']]){
  await evaluate('([...document.querySelectorAll(".observatory-lenses button")].find(x=>x.innerText.includes('+JSON.stringify(tab)+'))?.click(),true)')
  await wait(700)
  const found=await evaluate('Boolean(document.querySelector('+JSON.stringify(selector)+'))')
  if(!found)throw Error('No target '+selector)
  await evaluate('document.querySelector('+JSON.stringify(selector)+').scrollIntoView({block:"start"});window.scrollBy(0,-25);true')
  await wait(550)
  const {data}=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false})
  fs.writeFileSync(path.join(out,label+'.png'),Buffer.from(data,'base64'))
  console.log('CAPTURE',label+'.png')
 }
}finally{ws.close()}
