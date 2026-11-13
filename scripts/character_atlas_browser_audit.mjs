// UI continuity acceptance on authorized, isolated 80-volume local test site.
// Screenshots include copyrighted excerpts only when author explicitly opens them.
// Store captures in ignored .ux-audit, never in Git or public logs.
import fs from 'node:fs'
import path from 'node:path'
const root=path.resolve(import.meta.dirname,'..')
const folder=path.join(root,'.ux-audit','destroyer-library')
fs.mkdirSync(folder,{recursive:true})
const endpoint='http://127.0.0.1:8000'
const projects=await(await fetch(endpoint+'/api/projects')).json()
if(projects.length!==1||!projects[0].name.includes('Synthetic Editorial Review'))throw Error('Not isolated test site')
const library=(await(await fetch(endpoint+'/api/series')).json()).find(item=>item.title==='The Destroyer - 80-Book Continuity Lab')
if(!library||library.volume_count!==80)throw Error('80 books not loaded')
const tabs=await(await fetch('http://127.0.0.1:9227/json')).json()
const page=tabs.find(t=>t.type==='page'&&t.url.startsWith('http://127.0.0.1:5173'))
if(!page)throw Error('Local Chrome test tab missing')
const ws=new WebSocket(page.webSocketDebuggerUrl)
await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j})
let serial=0;const callbacks=new Map()
ws.onmessage=e=>{const d=JSON.parse(e.data);const p=callbacks.get(d.id);if(!p)return;callbacks.delete(d.id);d.error?p.j(Error(JSON.stringify(d.error))):p.r(d.result)}
function send(method,params={}){return new Promise((r,j)=>{const id=++serial;callbacks.set(id,{r,j});ws.send(JSON.stringify({id,method,params}))})}
async function js(expression){const d=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(d.exceptionDetails)throw Error(JSON.stringify(d.exceptionDetails));return d.result?.value}
async function until(expr,label){for(let i=0;i<50;i++){if(await js(expr))return;await new Promise(r=>setTimeout(r,250))}throw Error('UI missing: '+label)}
async function snap(name,width,height,selector){
 await send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:width<600})
 await js('document.querySelector('+JSON.stringify(selector)+')?.scrollIntoView({block:"start"});true')
 await new Promise(r=>setTimeout(r,350))
 const output=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false})
 fs.writeFileSync(path.join(folder,name+'.png'),Buffer.from(output.data,'base64'))
 const geo=await js('({width:innerWidth,doc:document.documentElement.scrollWidth,chart:document.querySelector(".cem-chart")?.scrollWidth,chartViewport:document.querySelector(".cem-chart-scroll")?.clientWidth})')
 if(geo.doc>width+2)throw Error('Overflow '+name+JSON.stringify(geo))
 console.log('CAPTURED',name,JSON.stringify(geo))
}
try{
 await send('Page.enable')
 await send('Emulation.setDeviceMetricsOverride',{width:1440,height:900,deviceScaleFactor:1,mobile:false})
 await send('Page.navigate',{url:'http://127.0.0.1:5173/'})
 await until('!!document.querySelector(".project-card")','project')
 await js('localStorage.setItem("emberwriter.workspace","series");location.reload();true')
 await until('!!document.querySelector(".project-card")','reload')
 await js('if(!document.querySelector(".project-card.active"))document.querySelector(".project-card").click();true')
 await until('!!document.querySelector(".character-evidence-map")','evidence atlas')
 await until('document.querySelectorAll(".cem-characters button").length===3','character selector')
 await js('([...document.querySelectorAll(".cem-characters button")].find(b=>b.innerText.includes("Remo Williams"))||null)?.click();true')
 await until('document.querySelectorAll(".cem-chart button").length===80','80 volume atlas')
 const initial=await js('({characters:document.querySelectorAll(".cem-characters button").length,books:document.querySelectorAll(".cem-chart button").length,windows:document.querySelector(".cem-summary strong")?.innerText,disclaimer:document.querySelector(".cem-caveat")?.innerText})')
 if(initial.windows!=='13,182'||!initial.disclaimer.includes('not establish'))throw Error('Atlas count/disclaimer incorrect '+JSON.stringify(initial))
 await snap('06-80-book-character-atlas',1440,900,'.character-evidence-map')
 await js('document.querySelector(\'.cem-chart button[aria-label^="Book 20:"]\')?.click();true')
 await until('!!document.querySelector(".cem-book-focus")','selected book panel')
 await snap('07-selected-character-book',1440,900,'.character-evidence-map')
 await js('document.querySelector(".cem-book-focus button")?.click();true')
 await until('document.querySelector(".series-evidence-resultbar")?.innerText.includes("books 20–20")','book 20 bounded source')
 const result=await js('({label:document.querySelector(".series-evidence-resultbar")?.innerText.slice(0,120),returned:[...document.querySelectorAll(".series-evidence-cardhead span")].map(e=>e.textContent?.trim())})')
 if(result.returned.length===0||result.returned.some(n=>n!=='BOOK 20'))throw Error('Book focus leaks future/earlier sources '+JSON.stringify(result))
 await snap('08-atlas-cited-book-20',1440,900,'.series-evidence-resultbar')
 await snap('09-80-book-atlas-mobile',390,844,'.character-evidence-map')
 const report={timestamp:new Date().toISOString(),private:true,series_id:library.id,volumes:80,characters:initial.characters,matchingWindows:13182,selectedBook:20,resultsBookOnly:true,mobileNoOverflow:true,sourceQuoteCommitted:false}
 fs.writeFileSync(path.join(root,'docs','reviews','2026-11-13-character-atlas-test.json'),JSON.stringify(report,null,2))
 console.log('CHARACTER_ATLAS_ACCEPTANCE',JSON.stringify(report))
}catch(err){console.error('ATLAS_FAILED',err.stack||err);process.exitCode=1}finally{ws.close()}
