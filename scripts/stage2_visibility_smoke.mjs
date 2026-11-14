// Non-destructive local Chromium inspection: read-only UI interactions in a temporary tab.
import assert from 'node:assert/strict'
const origin='http://127.0.0.1:5173/'
const target=await fetch('http://127.0.0.1:9227/json/new?'+encodeURIComponent(origin),{method:'PUT'}).then(r=>r.json())
let ws
let xid=0
const pending=new Map()
function send(method,params={}){return new Promise((resolve,reject)=>{const id=++xid;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}))})}
async function js(expression){
 const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true})
 if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails))
 return r.result?.value
}
async function until(expr,label){
 for(let i=0;i<70;i++){if(await js(expr))return;await new Promise(r=>setTimeout(r,200))}
 throw Error('Missing '+label)
}
try{
 ws=new WebSocket(target.webSocketDebuggerUrl)
 await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject})
 ws.onmessage=e=>{const msg=JSON.parse(e.data);if(!msg.id||!pending.has(msg.id))return;const item=pending.get(msg.id);pending.delete(msg.id);msg.error?item.reject(Error(JSON.stringify(msg.error))):item.resolve(msg.result)}
 await send('Page.enable')
 await js('localStorage.setItem("emberwriter.workspace","series");location.reload();true')
 await until('[...document.querySelectorAll(".series-desk-select select option")].some(o=>o.textContent.includes("Destroyer"))','80-book series option')
 const selected=await js('(()=>{const s=document.querySelector(".series-desk-select select");const o=[...s.options].find(o=>o.textContent.includes("Destroyer"));if(!o)return null;s.value=o.value;s.dispatchEvent(new Event("change",{bubbles:true}));return o.textContent})()')
 assert.ok(selected,'80-book test series available')
 await until('!!document.querySelector(".observatory-lenses button")','Observatory')
 const stats=await js('({tabs:[...document.querySelectorAll(".observatory-lenses button")].map(x=>x.textContent.trim()),entities:document.querySelector(".observatory-hero-stats")?.textContent})')
 for(const label of ['Universe','Character minds','Plot threads','Story history','Model Lab'])assert.ok(stats.tabs.some(t=>t.includes(label)),'Missing '+label)
 for(const [index,heading] of [[0,'Universe'],[1,'Character minds'],[2,'Plot threads'],[3,'Story history']]){
   await js('document.querySelectorAll(".observatory-lenses button")['+index+'].click();true')
   await until('!!document.querySelector(".story-evidence-onboarding")','source evidence state for '+heading)
   await until('document.querySelector(".story-evidence-metrics")?.textContent.includes("80")','actual 80-source scan for '+heading)
   const state=await js('({heading:document.querySelector(".story-evidence-onboarding h3")?.textContent,metrics:document.querySelector(".story-evidence-metrics")?.textContent,actions:[...document.querySelectorAll(".story-evidence-actions button")].map(x=>x.textContent),pageWidth:document.documentElement.scrollWidth,viewport:innerWidth})')
   assert.ok(state.actions.includes('Explore source discoveries'))
   assert.ok(state.actions.includes('Review or add canon evidence'))
   assert.ok(state.pageWidth<=state.viewport+2,heading+' horizontal overflow')
   console.log('VISIBLE',heading,JSON.stringify(state))
 }
 await js('document.querySelectorAll(".observatory-lenses button")[4].click();true')
 await until('!!document.querySelector(".story-model-lab")','Model Lab')
 await until('document.querySelector(".model-lab-actions select")?.options.length>1 || !!document.querySelector(".model-lab-error")','local model picker or error')
 const model=await js('({heading:document.querySelector(".story-model-lab h3")?.textContent,controls:[...document.querySelectorAll(".model-lab-actions button")].map(x=>({label:x.textContent,disabled:x.disabled})),options:document.querySelector(".model-lab-actions select")?.options.length})')
 assert.ok(model.controls.length,'Model Lab missing run control')
 assert.ok(!model.controls[0].disabled,'Installed local models should enable benchmark control')
 console.log('VISIBLE Model Lab',JSON.stringify(model))
 const streamControl=await js('({present:!!document.querySelector(".story-stream-diagnostics"),action:document.querySelector(".story-stream-actions button")?.textContent,enabled:!document.querySelector(".story-stream-actions button")?.disabled})')
 assert.ok(streamControl.present&&streamControl.enabled,'Chunk 4 stream diagnostic must be available in Model Lab')
 console.log('VISIBLE Chunk4 Stream Diagnostic',JSON.stringify(streamControl))
 await js('document.querySelectorAll(".observatory-lenses button")[0].click();true')
 await until('!!document.querySelector(".story-evidence-actions button")','Empty-state actions')
 await js('document.querySelector(".story-evidence-actions button").click();true')
 await until('!!document.querySelector(".discovery-workspace")','Discover clicked through from source previews')
 await until('document.querySelector(".discovery-score strong")?.textContent==="9"','Actual discovery count')
 console.log('VISIBLE Discovery',await js('({heading:document.querySelector(".discovery-intro h3")?.textContent,leads:document.querySelectorAll(".discovery-lead").length})'))
 await js('(()=>{const s=document.querySelector(".series-desk-select select");const o=[...s.options].find(o=>o.textContent.includes("Astral Lanterns"));if(!o)return false;s.value=o.value;s.dispatchEvent(new Event("change",{bubbles:true}));return true})()')
 await until('document.querySelector(".series-desk-select select")?.selectedOptions[0]?.textContent.includes("Astral Lanterns")','Four-book series selected')
 await until('!![...document.querySelectorAll(".series-experience-modes button")].find(b=>b.textContent.includes("Knowledge Lab"))','Knowledge Lab navigation')
 await js('[...document.querySelectorAll(".series-experience-modes button")].find(b=>b.textContent.includes("Knowledge Lab")).click();true')
 await until('document.querySelector(".knowledge-state strong")?.textContent==="27"','Approved evidence in four-book Knowledge Lab')
 console.log('VISIBLE Approved knowledge',await js('({approved:document.querySelector(".knowledge-state strong")?.textContent,tabs:document.querySelectorAll(".knowledge-lenses button").length})'))
 await js('(()=>{const s=document.querySelector(".series-desk-select select");const o=[...s.options].find(o=>o.textContent.includes("Destroyer"));s.value=o.value;s.dispatchEvent(new Event("change",{bubbles:true}));return true})()')
 await until('document.querySelector(".series-desk-select select")?.selectedOptions[0]?.textContent.includes("Destroyer")','80-book source selected for verified section probe')
 await js('[...document.querySelectorAll(".series-experience-modes button")].find(b=>b.textContent.includes("Verify")).click();true')
 await until('!!document.querySelector(".source-sections summary")','Source section navigator')
 await js('document.querySelector(".source-sections summary").click();true')
 await until('!!document.querySelector(".source-original-preview input[type=file]")','Original EPUB reconciliation visible')
 const chapter=await js('({heading:document.querySelector(".source-original-preview strong")?.textContent,previewButton:document.querySelector(".source-original-preview button")?.textContent,disabled:document.querySelector(".source-original-preview button")?.disabled})')
 assert.ok(chapter.heading.includes('Chunk 4'))
 assert.ok(chapter.disabled,'EPUB preview must require explicit input')
 console.log('VISIBLE Chunk4 EPUB',JSON.stringify(chapter))
 await until('!!document.querySelector(".source-collection-recovery summary")','Whole-series ZIP recovery visible')
 await js('document.querySelector(".source-collection-recovery summary").click();true')
 await until('!!document.querySelector(".source-collection-recovery input[type=file]")','Original collection ZIP picker')
 const collection=await js('({control:document.querySelector(".source-collection-recovery summary")?.textContent,picker:!!document.querySelector(".source-collection-recovery input[type=file]"),previewDisabled:document.querySelector(".source-collection-recovery button")?.disabled})')
 assert.ok(collection.picker&&collection.previewDisabled,'ZIP preview must require explicit author file selection')
 console.log('VISIBLE Chunk4 EPUB Collection',JSON.stringify(collection))
 console.log('STAGE2_VISIBILITY_SMOKE_PASS',JSON.stringify({series:selected,tabs:stats.tabs,models:model.options,non_destructive:true}))
}finally{
 ws?.close()
 try{await fetch('http://127.0.0.1:9227/json/close/'+target.id)}catch{}
}
