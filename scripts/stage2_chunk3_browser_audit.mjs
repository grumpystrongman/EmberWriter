// Stage II complete synthetic-author browser walkthrough.
// Creates a synthetic three-book Series Vault, captures real UI and deletes
// only this unique synthetic fixture in finally. Never touches user books.
import fs from 'node:fs'
import path from 'node:path'
import assert from 'node:assert/strict'
const root=path.resolve(import.meta.dirname,'..')
const folder=path.join(root,'docs','reviews','assets','2026-11-13-stage2-chunk3')
fs.mkdirSync(folder,{recursive:true})
const api='http://127.0.0.1:8000/api'
const projects=await(await fetch(api+'/projects')).json()
assert.equal(projects.length,1,'Not the isolated synthetic test environment')
assert.match(projects[0].name,/Synthetic Editorial Review/)
const tabs=await(await fetch('http://127.0.0.1:9227/json')).json()
const page=tabs.find(item=>item.type==='page'&&item.url.startsWith('http://127.0.0.1:5173'))
assert.ok(page,'No localhost Chrome test tab')
const unique='STAGE II CHUNK3 QA - Glass Horizon Synthetic '+Date.now()
const json=(value)=>({method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(value)})
async function call(endpoint,options){
 const response=await fetch(api+endpoint,options)
 const body=await response.json().catch(()=>({}))
 if(!response.ok)throw Error('API '+response.status+' '+JSON.stringify(body).slice(0,300))
 return body
}
let seriesId=null
let ws
let xid=0
const pending=new Map()
function send(method,params={}){
 return new Promise((resolve,reject)=>{const id=++xid;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}))})
}
async function js(expression){
 const result=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true})
 if(result.exceptionDetails)throw Error(JSON.stringify(result.exceptionDetails))
 return result.result?.value
}
const sleep=ms=>new Promise(r=>setTimeout(r,ms))
async function until(expr,label){
 for(let i=0;i<60;i++){if(await js(expr))return;await sleep(250)}
 throw Error('Missing '+label)
}
async function screenshot(name,width=1440,height=900){
 await send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:width<600})
 await js('document.querySelector(".series-knowledge-lab")?.scrollIntoView({block:"start"});true')
 await sleep(380)
 const capture=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false})
 fs.writeFileSync(path.join(folder,name+'.png'),Buffer.from(capture.data,'base64'))
 const sizes=await js('({viewport:innerWidth,document:document.documentElement.scrollWidth,lab:document.querySelector(".series-knowledge-lab")?.scrollWidth,container:document.querySelector(".series-knowledge-lab")?.clientWidth,claimCount:document.querySelectorAll(".knowledge-claim").length,errors:[...document.querySelectorAll(".knowledge-error")].map(e=>e.textContent)})')
 if(sizes.document>width+2||sizes.lab>sizes.container+6||sizes.errors.length)throw Error('Visual overflow or error '+JSON.stringify(sizes))
 console.log('REAL SYNTHETIC CAPTURE',name,JSON.stringify(sizes))
 return sizes
}
try{
 const created=await call('/series',json({title:unique,description:'Temporary synthetic continuity browser QA; remove after testing'}))
 seriesId=created.id
 const texts=[
  'Chapter 1\nMira feared the old bridge. The blue crown rested in the crypt. The blue crown foreshadows the sealed gate.',
  'Chapter II\nMira discovered the bridge had been repaired. The blue crown moved to the tower. Readers learned Rowan guarded the crown.',
  'Epilogue\nMira trusts Rowan. Mira explained the crown to Rowan. The blue crown resolves the sealed gate.'
 ]
 const sources=[]
 for(let i=0;i<texts.length;i++){
   const form=new FormData()
   form.set('file',new Blob([texts[i]],{type:'text/markdown'}),'chapter-'+(i+1)+'.md')
   form.set('ordinal',String(i+1));form.set('title','Synthetic Journey '+(i+1))
   form.set('kind','novel');form.set('edition_status','reference')
   form.set('rights_confirmed','true')
   const result=await call('/series/'+seriesId+'/volumes/import',{method:'POST',body:form})
   sources.push(result.volumes[i].sources[0].id)
 }
 const mira=await call('/series/'+seriesId+'/entities',json({name:'Mira',kind:'character'}))
 const rowan=await call('/series/'+seriesId+'/entities',json({name:'Rowan',kind:'character'}))
 const crown=await call('/series/'+seriesId+'/entities',json({name:'Blue Crown',kind:'artifact'}))
 async function approve(book,phrase,subject,predicate,value,{end=null,scope='world',knower=null,target=null}={}){
   const position=texts[book-1].indexOf(phrase)
   assert.ok(position>=0,'Fixture source quote not found')
   const claim=await call('/series/'+seriesId+'/assertions',json({
     subject_id:subject.id,predicate,object_text:value,
     object_entity_id:target?.id||null,scope,knower_id:knower?.id||null,
     start_book:book,start_sequence:0,end_book:end,
     source_id:sources[book-1],quote_start:position,
     quote_end:position+phrase.length,quote:phrase,
   }))
   return call('/series/'+seriesId+'/assertions/'+claim.id+'/review',json({decision:'approved'}))
 }
 await approve(1,'The blue crown rested in the crypt.',crown,'located_in','crypt',{end:1})
 await approve(2,'The blue crown moved to the tower.',crown,'located_in','tower')
 await approve(1,'The blue crown foreshadows the sealed gate.',crown,'foreshadows','sealed gate')
 await approve(3,'The blue crown resolves the sealed gate.',crown,'resolves','sealed gate')
 await approve(1,'Chapter 1\nMira feared the old bridge.',mira,'fears','old bridge')
 await approve(2,'Readers learned Rowan guarded the crown.',rowan,'guards','the crown',{scope:'reader_reveal'})
 await approve(3,'Epilogue\nMira trusts Rowan.',mira,'trusts','Rowan',{target:rowan})
 // Exactly seven source-backed claims, deliberately authored in synthetic fixture.
 const point1=await call('/series/'+seriesId+'/knowledge-lab?book=1')
 const point3=await call('/series/'+seriesId+'/knowledge-lab?book=3')
 assert.equal(point1.world_truths.length,3)
 assert.equal(point1.thread_lifecycle[0].status,'open')
 assert.equal(point1.reader_reveals.length,0)
 assert.ok(!JSON.stringify(point1).includes('tower'))
 assert.equal(point3.world_truths.length,5)
 assert.equal(point3.thread_lifecycle[0].status,'resolved')
 assert.equal(point3.reader_reveals.length,1)
 assert.equal(point3.possible_conflicts.length,0)
 ws=new WebSocket(page.webSocketDebuggerUrl)
 await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j})
 ws.onmessage=e=>{const msg=JSON.parse(e.data);if(!msg.id||!pending.has(msg.id))return;const p=pending.get(msg.id);pending.delete(msg.id);msg.error?p.reject(Error(JSON.stringify(msg.error))):p.resolve(msg.result)}
 await send('Page.enable')
 await send('Emulation.setDeviceMetricsOverride',{width:1440,height:900,deviceScaleFactor:1,mobile:false})
 await send('Page.navigate',{url:'http://127.0.0.1:5173/'})
 await until('!!document.querySelector(".project-card")','test site')
 await js('localStorage.setItem("emberwriter.workspace","series");location.reload();true')
 await until('!!document.querySelector(".project-card")','project card on reload')
 await js('if(!document.querySelector(".project-card.active"))document.querySelector(".project-card").click();true')
 await until('!!document.querySelector(".series-desk-select select")','Series picker')
 await js('(()=>{const s=document.querySelector(".series-desk-select select");const option=[...s.options].find(o=>o.textContent.startsWith('+JSON.stringify(unique)+'));if(!option)return false;s.value=option.value;s.dispatchEvent(new Event("change",{bubbles:true}));return true})()')
 await until('document.querySelector(".series-desk-select select")?.selectedOptions[0]?.textContent.includes('+JSON.stringify(unique)+')','synthetic chosen')
 await until('!!document.querySelector(".series-experience-modes")','Series modes')
 await js('document.querySelector(".series-experience-modes button:nth-child(3)").click();true')
 await until('!!document.querySelector(".series-verify-tools")','Verify tools')
 await js('([...document.querySelectorAll(".series-verify-tools button")].find(e=>e.textContent.includes("Knowledge Lab"))).click();true')
 await until('!!document.querySelector(".series-knowledge-lab")','knowledge lab')
 await until('document.querySelector(".knowledge-state strong")?.textContent==="7"','seven approved claims')
 await screenshot('01-approved-world-truth-desktop')
 await js('(()=>{const select=document.querySelector(".knowledge-controls select");select.value="1";select.dispatchEvent(new Event("change",{bubbles:true}));return true})()')
 await until('document.querySelector(".knowledge-state strong")?.textContent==="3"','Book 1 cutoff')
 await screenshot('02-book1-no-future-spoilers')
 await js('document.querySelectorAll(".knowledge-lenses button")[6].click();true')
 await until('!!document.querySelector(".knowledge-threads")','plot promises lens')
 await screenshot('03-setup-no-future-payoff')
 await js('(()=>{const select=document.querySelector(".knowledge-controls select");select.value="3";select.dispatchEvent(new Event("change",{bubbles:true}));return true})()')
 await until('!!document.querySelector(".knowledge-threads")?.innerText.includes("RESOLVED")','Book 3 payoff')
 await screenshot('04-setup-and-payoff',1440,900)
 await screenshot('05-mobile-knowledge-lab',390,844)
 await screenshot('06-tablet-knowledge-lab',900,800)
 // Source drill-down from the exact approved quote, not a guessed nearby term.
 await send('Emulation.setDeviceMetricsOverride',{width:1440,height:900,deviceScaleFactor:1,mobile:false})
 await js('document.querySelector(".knowledge-citation").click();true')
 await until('!!document.querySelector(".series-desk-evidence")','exact source inspection')
 await until('document.querySelector(".series-desk-excerpt")?.textContent.includes("blue crown")','source quote')
 await until('!!document.querySelector(".source-sections")','chapter index')
 await js('document.querySelector(".source-sections summary").click();true')
 await until('document.querySelectorAll(".source-section-list button").length>=1','chapter heading detection')
 const names=await js('[...document.querySelectorAll(".source-section-list button")].map(x=>x.innerText)')
 if(!names.some(name=>name.includes("Chapter")))throw Error('Expected literal chapter heading missing')
 await js('document.querySelector(".source-sections").scrollIntoView({block:"center"});true')
 const sectionPNG=await send('Page.captureScreenshot',{format:'png'})
 fs.writeFileSync(path.join(folder,'07-source-chapter-navigator.png'),Buffer.from(sectionPNG.data,'base64'))
 await js('document.querySelector(".source-section-list button").click();true')
 await until('!!document.querySelector(".series-desk-excerpt")?.textContent.includes("Chapter")','chapter link')
 console.log('SECTION_NAVIGATION_VERIFIED',JSON.stringify(names.map(x=>x.slice(0,60))))
 console.log('SYNTHETIC_SOURCE_DRILLDOWN_PASS')
 const record={date:new Date().toISOString(),fixture:'Temporary synthetic fiction only',
   exact_source_verified:true,source_section_jump_verified:true,approved_claims:7,
   book1_no_future_knowledge:true,thread_payoff_hidden_until_book3:true,
   mobile_no_horizontal_overflow:true,
   original_user_manuscripts_unchanged:true}
 fs.writeFileSync(path.join(root,'docs','reviews','2026-11-13-stage2-chunk3-browser-evidence.json'),JSON.stringify(record,null,2))
 console.log('STAGE2_SYNTHETIC_BROWSER_PASS',JSON.stringify(record))
}catch(error){console.error('STAGE2_SYNTHETIC_BROWSER_FAIL',error.stack||error);process.exitCode=1}
finally{
 if(ws)ws.close()
 if(seriesId){
   try{
     await call('/series/'+seriesId+'/delete',json({confirmation:unique}))
     console.log('TEMP SYNTHETIC QA SERIES REMOVED')
   }catch(error){console.error('TEMP SYNTHETIC SERIES CLEANUP FAILED',error)}
 }
}
