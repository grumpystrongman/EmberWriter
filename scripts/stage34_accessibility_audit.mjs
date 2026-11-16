// Local-only axe-core browser QA on a freshly isolated synthetic project.
// No author manuscripts, remote browser services or external submissions.
import fs from 'node:fs'
import path from 'node:path'
import assert from 'node:assert/strict'

const backend=process.env.EMBER_QA_BACKEND || 'http://127.0.0.1:8107'
const frontend=process.env.EMBER_QA_FRONTEND || 'http://127.0.0.1:5187'
const debuggerUrl=process.env.EMBER_QA_DEBUGGER || 'http://127.0.0.1:9287'
const axePath=process.env.EMBER_QA_AXE_PATH
const output=process.env.EMBER_QA_A11Y_RESULT
if(!axePath || !output)throw Error('Provide the local axe-core path and private audit output path')
const projects=await(await fetch(backend+'/api/projects')).json()
assert.equal(projects.length,1,'Only a fresh isolated synthetic project may be audited')
assert.match(projects[0].name,/Synthetic Editorial Review/)
const pages=await(await fetch(debuggerUrl+'/json')).json()
const page=pages.find(p=>p.type==='page'&&p.url.startsWith(frontend))
assert.ok(page,'Dedicated isolated QA Chromium tab is required')
const ws=new WebSocket(page.webSocketDebuggerUrl)
await new Promise((ok,fail)=>{ws.onopen=ok;ws.onerror=fail})
let counter=0
const waiting=new Map()
ws.onmessage=e=>{const item=JSON.parse(e.data);if(!waiting.has(item.id))return;const p=waiting.get(item.id);waiting.delete(item.id);item.error?p.fail(Error(JSON.stringify(item.error))):p.ok(item.result)}
const send=(method,params={})=>new Promise((ok,fail)=>{const id=++counter;waiting.set(id,{ok,fail});ws.send(JSON.stringify({id,method,params}))})
async function evaluate(expression){
 const answer=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true})
 if(answer.exceptionDetails)throw Error(JSON.stringify(answer.exceptionDetails))
 return answer.result?.value
}
const delay=ms=>new Promise(ok=>setTimeout(ok,ms))
async function wait(expr){
 for(let x=0;x<45;x++){if(await evaluate(expr))return;await delay(250)}
 throw Error('Synthetic browser failed to load '+expr)
}
const axe=fs.readFileSync(axePath,'utf8')
const checks=[]
try{
 await send('Page.enable')
 for(const workspace of ['write','plan','analyze','publish','series','studio']){
  await send('Page.navigate',{url:frontend+'/'})
  await wait('!!document.querySelector(".project-card")')
  await evaluate('localStorage.setItem("emberwriter.workspace",'+JSON.stringify(workspace)+');location.reload();true')
  await wait('document.querySelector(".workspace-shell")?.dataset.workspace==='+JSON.stringify(workspace))
  await wait('!!document.querySelector(".project-card")')
  for(let attempt=0;attempt<10;attempt++){
   if(await evaluate('!!document.querySelector(".project-card.active")'))break
   await evaluate('document.querySelector(".project-card")?.click();true')
   await delay(500)
  }
  await wait('!!document.querySelector(".project-card.active")')
  for(const width of [390,900,1440]){
   await send('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<600})
   await delay(300)
   await evaluate(axe)
   const result=await evaluate('(async()=>{const r=await axe.run(document,{runOnly:{type:"tag",values:["wcag2a","wcag2aa","wcag21a","wcag21aa","wcag22aa"]}});return {violations:r.violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.length,selectors:v.nodes.slice(0,6).map(n=>n.target),failures:v.nodes.slice(0,6).map(n=>n.failureSummary)})),incomplete:r.incomplete.length,passes:r.passes.length}})()')
   const overflow=await evaluate('document.documentElement.scrollWidth-innerWidth')
   const row={workspace,width,overflow,...result}
   checks.push(row)
   console.log('A11Y',workspace,width,'violations',result.violations.length,'overflow',overflow)
  }
 }
 fs.mkdirSync(path.dirname(output),{recursive:true})
 fs.writeFileSync(output,JSON.stringify({synthetic:true,created_at:new Date().toISOString(),checks},null,2))
 console.log('A11Y_RESULTS',output,'violations',checks.reduce((n,r)=>n+r.violations.length,0))
 if(checks.some(r=>r.violations.length||r.overflow>2))process.exitCode=2
}catch(e){console.error('A11Y_ERROR',e.stack||e);process.exitCode=1
}finally{ws.close()}
