// Local-only author acceptance of 80-book Series Vault UI.
// Screenshots stay in .ux-audit (ignored) because books are user-supplied.
import fs from 'node:fs'
import path from 'node:path'
const root=path.resolve(import.meta.dirname,'..')
const folder=path.join(root,'.ux-audit','destroyer-library')
fs.mkdirSync(folder,{recursive:true})
const endpoint='http://127.0.0.1:8000'
const projects=await(await fetch(endpoint+'/api/projects')).json()
if(projects.length!==1||!projects[0].name.includes('Synthetic Editorial Review'))throw Error('Not the private test site')
const collection=(await(await fetch(endpoint+'/api/series')).json())
  .find(item=>item.title==='The Destroyer - 80-Book Continuity Lab')
if(!collection||collection.volume_count!==80)throw Error('Expected imported 80-book test series')
const tabs=await(await fetch('http://127.0.0.1:9227/json')).json()
const page=tabs.find(item=>item.type==='page'&&item.url.startsWith('http://127.0.0.1:5173'))
if(!page)throw Error('Local Chrome tab unavailable')
const ws=new WebSocket(page.webSocketDebuggerUrl)
await new Promise((res,rej)=>{ws.onopen=res;ws.onerror=rej})
let id=0
const pending=new Map()
ws.onmessage=event=>{
 const item=JSON.parse(event.data)
 if(!item.id||!pending.has(item.id))return
 const p=pending.get(item.id);pending.delete(item.id)
 item.error?p.reject(Error(JSON.stringify(item.error))):p.resolve(item.result)
}
const send=(method,params={})=>new Promise((resolve,reject)=>{
 const xid=++id
 pending.set(xid,{resolve,reject})
 ws.send(JSON.stringify({id:xid,method,params}))
})
async function js(expression){
 const o=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true})
 if(o.exceptionDetails)throw Error(JSON.stringify(o.exceptionDetails))
 return o.result?.value
}
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms))
async function until(expr,label){
 for(let i=0;i<55;i++){if(await js(expr))return;await sleep(250)}
 throw Error('Missing '+label)
}
async function screenshot(name,width=1440,height=900,selector='.series-evidence-search'){
 await send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:width<600})
 await js('document.querySelector('+JSON.stringify(selector)+')?.scrollIntoView({block:"start"});true')
 await sleep(420)
 const img=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false})
 fs.writeFileSync(path.join(folder,name+'.png'),Buffer.from(img.data,'base64'))
 const geometry=await js('({document:document.documentElement.scrollWidth,viewport:innerWidth,search:document.querySelector(".series-evidence-search")?.scrollWidth,searchWidth:document.querySelector(".series-evidence-search")?.clientWidth})')
 if(geometry.document>width+2||geometry.search>geometry.searchWidth+6)throw Error('Overflow '+JSON.stringify(geometry))
 console.log('CAPTURED',name,JSON.stringify(geometry))
}
try{
 await send('Page.enable')
 await send('Page.navigate',{url:'http://127.0.0.1:5173/'})
 await until('!!document.querySelector(".project-card")','synthetic project')
 await js('localStorage.setItem("emberwriter.workspace","series");location.reload();true')
 await until('!!document.querySelector(".project-card")','reloaded project card')
 await js('if(!document.querySelector(".project-card.active"))document.querySelector(".project-card").click();true')
 await until('!!document.querySelector(".series-evidence-search")','source evidence explorer')
 await until('document.body.innerText.includes("The Destroyer - 80-Book Continuity Lab")','selected test library')
 await screenshot('01-80-book-series-search-desktop')
 const expanded=await js('document.querySelector(".series-evidence-collapse")?.getAttribute("aria-expanded")')
 if(expanded==='false')await js('document.querySelector(".series-evidence-collapse").click();true')
 await until('!!document.querySelector("#series-evidence-query")','full-book search')
 await js('(()=>{const i=document.querySelector("#series-evidence-query");const set=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,"value").set;set.call(i,"Remo");i.dispatchEvent(new Event("input",{bubbles:true}));return true})()')
 await js('document.querySelector(".series-evidence-searchbar button[type=submit]").click();true')
 await until('!!document.querySelector(".series-evidence-resultbar")','grounded results')
 const overall=await js('({hits:document.querySelector(".series-evidence-resultbar strong")?.innerText, cards:document.querySelectorAll(".series-evidence-grid article").length})')
 if(overall.cards<5)throw Error('Insufficient results')
 // Results contain copyrighted user books. Store only on their own PC.
 await screenshot('02-grounded-search-private')
 await js('(()=>{const i=document.querySelector("#series-evidence-timeline");const set=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,"value").set;set.call(i,"20");i.dispatchEvent(new Event("input",{bubbles:true}));return true})()')
 await until('document.querySelector(".series-evidence-booklimit label")?.innerText.includes("20")','book cutoff')
 await js('document.querySelector(".series-evidence-searchbar button[type=submit]").click();true')
 await until('!!document.querySelector(".series-evidence-resultbar")','spoiler filtered results')
 const cutoff=await js('({limit:document.querySelector("#series-evidence-timeline").value,counts:[...document.querySelectorAll(".series-evidence-cardhead span")].map(e=>Number(e.innerText.replace(/[^0-9]/g,""))),matched:document.querySelector(".series-evidence-resultbar strong")?.innerText})')
 if(cutoff.counts.some(n=>n>20))throw Error('Future book leaked into cutoff results')
 await screenshot('03-book-20-spoiler-boundary')
 await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true})
 await screenshot('04-mobile-80-book-search',390,844)
 // Return to desktop, inspect Library import workflow (no reimport).
 await send('Emulation.setDeviceMetricsOverride',{width:1440,height:900,deviceScaleFactor:1,mobile:false})
 await js('document.querySelectorAll(".series-experience-modes button")[3].click();true')
 await until('!!document.querySelector(".series-collection-import")','ZIP batch import workflow')
 await screenshot('05-local-series-collection-import',1440,900,'.series-collection-import')
 const state=await js('({books:document.querySelectorAll(".series-desk-volume").length,importLabel:document.querySelector(".series-collection-import h2")?.innerText,seriesName:document.querySelector(".series-desk-header select")?.selectedOptions?.[0]?.textContent})')
 const report={time:new Date().toISOString(),series_id:collection.id,volumes:collection.volume_count,searchCards:overall.cards,cutoffBook:20,allReturnedBooksRespectCutoff:true,searchUIResponsive:true,bulkImportUIVisible:true,metrics:state}
 fs.writeFileSync(path.join(folder,'browser-acceptance.json'),JSON.stringify(report,null,2))
 console.log('BROWSER_ACCEPTANCE',JSON.stringify(report))
}catch(err){console.error('FAILED',err.stack||err);process.exitCode=1}
finally{ws.close()}
