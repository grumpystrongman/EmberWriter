// Synthetic-only Part 2 visual workflow acceptance via Chrome DevTools protocol.
// Refuses to run unless the local API exposes the designated demonstration series.
import fs from 'node:fs'
import path from 'node:path'
const root=path.resolve(import.meta.dirname,'..')
const out=path.join(root,'docs','screenshots','part2-synthetic')
fs.mkdirSync(out,{recursive:true})
const all=await (await fetch('http://127.0.0.1:8000/api/series')).json()
if(all.length!==1||all[0].title!=='The Astral Lanterns')throw Error('Safety gate: not the isolated synthetic series')
const tabs=await (await fetch('http://127.0.0.1:9227/json')).json()
const page=tabs.find(t=>t.type==='page'&&t.url.startsWith('http://127.0.0.1:5173'))
if(!page)throw Error('Isolated Chrome development page unavailable')
const ws=new WebSocket(page.webSocketDebuggerUrl)
await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject})
let seq=0
const pending=new Map()
ws.onmessage=event=>{const value=JSON.parse(event.data);if(!value.id||!pending.has(value.id))return;const item=pending.get(value.id);pending.delete(value.id);value.error?item.reject(Error(JSON.stringify(value.error))):item.resolve(value.result)}
const send=(method,params={})=>new Promise((resolve,reject)=>{const id=++seq;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}))})
async function evaluate(expression){const res=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(res.exceptionDetails)throw Error(JSON.stringify(res.exceptionDetails));return res.result?.value}
const wait=ms=>new Promise(r=>setTimeout(r,ms))
const eventually=async(expression,reason)=>{for(let i=0;i<22;i++){if(await evaluate(expression))return;await wait(350)}throw Error(reason)}
const click=async(expression)=>{const result=await evaluate(expression);if(!result)throw Error('Click target not found: '+expression);await wait(320)}
async function shot(label,width=1440,height=900,selector='.p2-studio'){
 await send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:width<600})
 await wait(350)
 await evaluate('document.querySelector('+JSON.stringify(selector)+')?.scrollIntoView({block:"start"});true')
 await wait(450)
 const png=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false})
 fs.writeFileSync(path.join(out,label+'.png'),Buffer.from(png.data,'base64'))
 const dimensions=await evaluate('({viewport:innerWidth,document:document.documentElement.scrollWidth,studio:document.querySelector(".p2-studio")?.getBoundingClientRect().width, studioScroll:document.querySelector(".p2-studio")?.scrollWidth, warnings:[...document.querySelectorAll(".p2-message.error")].map(e=>e.innerText)})')
 if(dimensions.document>width+2)throw Error('Page overflow at '+width+': '+JSON.stringify(dimensions))
 if(dimensions.studioScroll>dimensions.studio+10)throw Error('Studio overflow '+JSON.stringify(dimensions))
 if(dimensions.warnings.length)throw Error('Visible errors '+JSON.stringify(dimensions.warnings))
 console.log('CAPTURE',label,JSON.stringify(dimensions))
}
try {
 await send('Page.enable')
 await send('Emulation.setDeviceMetricsOverride',{width:1440,height:900,deviceScaleFactor:1,mobile:false})
 await evaluate('localStorage.setItem("emberwriter.workspace","series");location.reload();true')
 await wait(1700)
 await eventually('!!document.querySelector(".series-desk-tabs")','Series Desk did not load')
 await click('([...document.querySelectorAll(".series-desk-tabs button")].find(x=>x.innerText.includes("Character & Scene Studio"))?.click(),true)')
 await eventually('!!document.querySelector(".p2-character-view")','Character studio did not mount')
 await shot('01-character-arcs-desktop')
 await click('([...document.querySelectorAll(".p2-navigation button")].find(x=>x.innerText.includes("Relationship orbit"))?.click(),true)')
 await eventually('!!document.querySelector(".p2-relationship-view")','Relationship orbit did not mount')
 await shot('02-relationship-orbit-desktop')
 await click('([...document.querySelectorAll(".p2-navigation button")].find(x=>x.innerText.includes("Scene Director"))?.click(),true)')
 await eventually('!!document.querySelector(".p2-director")','Scene Director did not mount')
 await shot('03-scene-director-empty')
 await click('document.querySelector(".p2-new-board")?.click(),true')
 await eventually('document.querySelectorAll(".p2-beat-card").length===6','Six-beat storyboard missing')
 await shot('04-scene-board-desktop')
 await click('([...document.querySelectorAll(".p2-kind-choices button")].find(x=>x.innerText.includes("Reversal"))?.click(),true)')
 await click('([...document.querySelectorAll(".p2-beat-card")][1]?.click(),true)')
 await evaluate('(()=>{const x=document.querySelector(".p2-board-heading input");const setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,"value").set;setter.call(x,"The Lantern Betrayal");x.dispatchEvent(new Event("input",{bubbles:true}));return true})()')
 await wait(250)
 await click('([...document.querySelectorAll(".p2-board-actions button")].find(x=>x.innerText.includes("Save scene plan"))?.click(),true)')
 await eventually('!!document.querySelector(".p2-message:not(.error)")','Board did not save')
 const boards=await (await fetch('http://127.0.0.1:8000/api/series/'+all[0].id+'/scene-boards')).json()
 if(!boards.length||!boards.some(board=>board.beats.length===6))throw Error('Persisted board unexpected: '+JSON.stringify(boards))
 await shot('05-scene-saved')
 await click('([...document.querySelectorAll(".p2-continuity-console button")].find(x=>x.innerText.includes("Check this scene"))?.click(),true)')
 await eventually('!!document.querySelector(".p2-continuity-results")','Continuity Guardian did not respond')
 await shot('06-scene-continuity')
 await shot('07-scene-mobile',390,844)
 await click('([...document.querySelectorAll(".p2-navigation button")].find(x=>x.innerText.includes("Character arcs"))?.click(),true)')
 await shot('08-character-mobile',390,844)
 await click('([...document.querySelectorAll(".p2-navigation button")].find(x=>x.innerText.includes("Relationship orbit"))?.click(),true)')
 await shot('09-relationships-mobile',390,844)
 await shot('10-relationships-tablet',900,800)
 console.log('PASS Part 2 synthetic browser acceptance')
} catch(e){console.error('FAIL',e.stack||e);process.exitCode=1}
finally{ws.close()}
