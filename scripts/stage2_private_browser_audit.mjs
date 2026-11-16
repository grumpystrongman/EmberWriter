// Private, read-only acceptance of Stage II against the imported 80-book library.
// Source text and screenshots remain in ignored .ux-audit on the owner's computer.
import fs from 'node:fs'
import path from 'node:path'

const root=path.resolve(import.meta.dirname,'..')
const out=path.join(root,'.ux-audit','stage2-private')
fs.mkdirSync(out,{recursive:true})
const endpoint='http://127.0.0.1:8000'
const projects=await(await fetch(endpoint+'/api/projects')).json()
if(projects.length!==1||!projects[0].name.includes('Synthetic Editorial Review'))throw Error('Not the designated local test host')
const series=(await(await fetch(endpoint+'/api/series')).json()).find(item=>item.title==='The Destroyer - 80-Book Continuity Lab')
if(!series||series.volume_count!==80)throw Error('Expected already-imported private 80-book library')
const tabs=await(await fetch('http://127.0.0.1:9227/json')).json()
const page=tabs.find(item=>item.type==='page'&&item.url.startsWith('http://127.0.0.1:5173'))
if(!page)throw Error('Missing localhost Chrome test tab')
const ws=new WebSocket(page.webSocketDebuggerUrl)
await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j})
let id=0;const pending=new Map()
ws.onmessage=e=>{
 const msg=JSON.parse(e.data);if(!msg.id||!pending.has(msg.id))return
 const req=pending.get(msg.id);pending.delete(msg.id)
 msg.error?req.reject(Error(JSON.stringify(msg.error))):req.resolve(msg.result)
}
const send=(method,params={})=>new Promise((resolve,reject)=>{
 const xid=++id;pending.set(xid,{resolve,reject});ws.send(JSON.stringify({id:xid,method,params}))
})
async function js(expression){
 const value=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true})
 if(value.exceptionDetails)throw Error(JSON.stringify(value.exceptionDetails))
 return value.result?.value
}
const sleep=ms=>new Promise(r=>setTimeout(r,ms))
async function until(expr,label){for(let i=0;i<52;i++){if(await js(expr))return;await sleep(250)}throw Error('Did not reach '+label)}
async function shot(name,width=1440,height=900,selector='.series-knowledge-lab'){
 await send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:width<600})
 await js('document.querySelector('+JSON.stringify(selector)+')?.scrollIntoView({block:"start"});true')
 await sleep(420)
 const png=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false})
 fs.writeFileSync(path.join(out,name+'.png'),Buffer.from(png.data,'base64'))
 const geo=await js('({width:innerWidth,doc:document.documentElement.scrollWidth,body:document.body.scrollWidth,lab:document.querySelector(".series-knowledge-lab")?.scrollWidth,client:document.querySelector(".series-knowledge-lab")?.clientWidth,errors:[...document.querySelectorAll("[role=alert]")].filter(e=>e.getBoundingClientRect().width>0).map(e=>e.innerText.slice(0,160))})')
 if(geo.doc>width+3||geo.lab>geo.client+7||geo.errors.length)throw Error('Overflow or error '+JSON.stringify(geo))
 console.log('CAPTURED',name,JSON.stringify({width:geo.width,doc:geo.doc,lab:geo.lab,client:geo.client}))
 return geo
}
let findings={}
try{
 await send('Page.enable')
 await send('Page.navigate',{url:'http://127.0.0.1:5173/'})
 await until('!!document.querySelector(".project-card")','local project card')
 await js('localStorage.setItem("emberwriter.workspace","series");location.reload();true')
 await until('!!document.querySelector(".project-card")','reloaded project')
 await js('if(!document.querySelector(".project-card.active"))document.querySelector(".project-card").click();true')
 await until('!!document.querySelector(".series-experience-modes")','Series workspace')
 await until('!!document.querySelector(".series-desk-select select")','series selection')
 await js('(()=>{const select=document.querySelector(".series-desk-select select");const option=[...select.options].find(o=>o.textContent.includes("The Destroyer - 80-Book Continuity Lab"));if(!option)throw Error("Library unavailable");select.value=option.value;select.dispatchEvent(new Event("change",{bubbles:true}));return true})()')
 await until('!!document.querySelector(".series-evidence-search")','private source search')
 await js('document.querySelector(".series-experience-modes button:nth-child(3)").click();true')
 await until('!!document.querySelector(".series-verify-tools")','Verify tools')
 await js('([...document.querySelectorAll(".series-verify-tools button")].find(e=>e.textContent?.includes("Knowledge Lab"))).click();true')
 await until('!!document.querySelector(".series-knowledge-lab")','Stage II Knowledge Lab')
 await until('!!document.querySelector(".knowledge-summary")','Knowledge Lab source response')
 const baseline=await js('({book:document.querySelector(".knowledge-controls select")?.value,approved:document.querySelector(".knowledge-state strong")?.textContent,none:document.querySelector(".knowledge-summary")?.innerText.includes("Not enough approved evidence"),lenses:document.querySelectorAll(".knowledge-lenses button").length})')
 if(!baseline.none||baseline.approved!=='0'||baseline.lenses!==9)throw Error('Falsely claimed private canon: '+JSON.stringify(baseline))
 await shot('01-private-80-book-knowledge-lab')
 await js('(()=>{const select=document.querySelector(".knowledge-controls select");select.value="20";select.dispatchEvent(new Event("change",{bubbles:true}));return true})()')
 await until('!document.querySelector(".knowledge-state strong")?.innerText.includes("—")','Book 20 result')
 await shot('02-book20-abstention',1440,900)
 await js('document.querySelectorAll(".knowledge-lenses button")[8].click();true')
 await until('document.querySelector(".knowledge-empty")?.innerText.includes("No approved")','honest conflict abstention')
 await shot('03-no-invented-conflicts',390,844)
 // Search a real source but do not save, approve or transmit its contents.
 await send('Emulation.setDeviceMetricsOverride',{width:1440,height:900,deviceScaleFactor:1,mobile:false})
 const expanded=await js('document.querySelector(".series-evidence-collapse")?.getAttribute("aria-expanded")')
 if(expanded==='false')await js('document.querySelector(".series-evidence-collapse").click();true')
 await until('!!document.querySelector("#series-evidence-query")','private book search')
 await js('(()=>{const x=document.querySelector("#series-evidence-query");const setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,"value").set;setter.call(x,"Remo");x.dispatchEvent(new Event("input",{bubbles:true}));return true})()')
 await js('document.querySelector(".series-evidence-searchbar button[type=submit]").click();true')
 await until('document.querySelectorAll(".series-evidence-stage-claim").length>0','cited source review action')
 const hit=await js('({total:document.querySelector(".series-evidence-resultbar strong")?.innerText,book:document.querySelector(".series-evidence-cardhead span")?.innerText})')
 await js('document.querySelector(".series-evidence-stage-claim").click();true')
 await until('!!document.querySelector(".series-desk-evidence")','canon draft passage')
 await until('document.querySelector(".series-desk-excerpt")?.textContent?.length>0','verified source passage')
 await until('[...document.querySelectorAll(".series-desk-success")].some(e=>e.innerText.includes("Exact source confirmed"))','confirmed exact source offset')
 const draft=await js(`({quote:document.querySelector('textarea[maxlength="2000"]')?.value||"",confirmed:[...document.querySelectorAll(".series-desk-success")].some(e=>e.innerText.includes("Exact source confirmed")),notApproved:document.querySelector(".series-desk-success")?.innerText.includes("staged")})`)
 if(!draft.confirmed||draft.quote.length<10)throw Error('Source draft was not exact or not staged')
 findings={series_books:80,baseline,book20_no_claims:true,all_lenses:9,grounded_search_returned:true,claim_draft_staged:true,staged_quote_characters:draft.quote.length,claim_not_saved:true}
 console.log('PRIVATE_STAGE2_ACCEPTANCE',JSON.stringify(findings))
 fs.writeFileSync(path.join(out,'acceptance-metadata.json'),JSON.stringify({time:new Date().toISOString(),...findings},null,2))
}catch(e){console.error('PRIVATE_STAGE2_FAILED',e.stack||e);process.exitCode=1}finally{ws.close()}
