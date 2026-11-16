import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import os from 'node:os'
import {createHash} from 'node:crypto'
import {spawnSync} from 'node:child_process'

const root=path.resolve(import.meta.dirname,'..')
const runner=path.join(root,'scripts','verify_release_scorecard.mjs')
const evidenceDir=path.join(root,'release')
const evidencePath=path.join(evidenceDir,'quality-evidence.json')
function execute(...args){return spawnSync(process.execPath,[runner,...args],{cwd:root,encoding:'utf8',timeout:15000})}
function withManifest(content,check){
 if(fs.existsSync(evidencePath))throw Error('Refusing to overwrite an existing release certification manifest')
 fs.mkdirSync(evidenceDir,{recursive:true})
 fs.writeFileSync(evidencePath,content)
 try{return check()}finally{fs.rmSync(evidencePath,{force:true})}
}
function digest(bytes){return createHash('sha256').update(bytes).digest('hex')}
function checkoutCommit(){
 const dotgit=path.join(root,'.git')
 const gitDir=fs.statSync(dotgit).isDirectory()?dotgit:path.resolve(root,fs.readFileSync(dotgit,'utf8').trim().slice('gitdir:'.length).trim())
 const head=fs.readFileSync(path.join(gitDir,'HEAD'),'utf8').trim()
 if(/^[a-f0-9]{40}$/.test(head))return head
 const commonFile=path.join(gitDir,'commondir')
 const common=fs.existsSync(commonFile)?path.resolve(gitDir,fs.readFileSync(commonFile,'utf8').trim()):gitDir
 const refPath=path.join(common,...head.slice(5).split('/'))
 return fs.readFileSync(refPath,'utf8').trim()
}

test('the unified author scorecard contains all 38 requirements across five systems',()=>{
 const result=execute('--catalog')
 assert.equal(result.status,0,result.stderr)
 const parsed=JSON.parse(result.stdout)
 assert.equal(parsed.gates,38)
 assert.equal(parsed.groups.length,5)
 assert.equal(parsed.provisional5Count,0)
})
test('missing release evidence hard-blocks stable certification',()=>{
 assert.equal(fs.existsSync(evidencePath),false,'A live certification manifest is present; do not overwrite it')
 const result=execute('--certify')
 assert.equal(result.status,1)
 assert.match(result.stderr,/RELEASE HOLD/)
})
test('arbitrary external evidence paths are refused before reading',()=>{
 const file=path.join(os.tmpdir(),'private-manifest.json')
 const result=execute('--certify',file)
 assert.equal(result.status,1)
 assert.match(result.stderr,/evidence must be release\/quality-evidence.json/)
})
test('synthetic and AI-only self-review cannot certify any category',()=>withManifest(JSON.stringify({
 schema:1,kind:'production_scorecard',synthetic:true,ai_assessed:true,
 commit:'a'.repeat(40),gates:[{id:'UX-01',score:5,commit:'a'.repeat(40),evidence:[]}],
}),()=>{
 const result=execute('--certify')
 assert.equal(result.status,1)
 assert.match(result.stderr,/synthetic\/AI-only signoff rejected/)
 assert.match(result.stderr,/missing same-commit 5\/5 approval/)
}))
test('a list of provisional scores is never mistaken for release certification',()=>{
 const file=fs.readFileSync(path.join(root,'frontend','src','release-gates.ts'),'utf8')
 assert.match(file,/All gates must attain independently validated 5\/5/)
 assert.match(file,/SER-04/)
 assert.match(file,/ENG-01/)
 assert.match(file,/PUB-04/)
})
test('malformed release evidence fails closed without a stack trace',()=>withManifest('{broken',()=>{
 const result=execute('--certify')
 assert.equal(result.status,1)
 assert.match(result.stderr,/RELEASE HOLD: release evidence must be a valid JSON object/)
 assert.doesNotMatch(result.stderr,/SyntaxError|at JSON.parse/)
}))
test('receipt references cannot escape their fixed release evidence directory',()=>{
 const receipt=path.join(os.tmpdir(),'ember-scorecard-receipt-test.txt')
 const hash=digest('passed')
 const commit=checkoutCommit()
 for(const illegal of [receipt,'../receipt.txt']){
  withManifest(JSON.stringify({schema:1,kind:'production_scorecard',commit,
   gates:[{id:'UX-01',score:5,commit,
   evidence:[{kind:'test',path:illegal,sha256:hash,commit,result:'passed'}]}]}),()=>{
    const result=execute('--certify')
    assert.equal(result.status,1)
    assert.match(result.stderr,/UX-01: evidence path escapes the approved directory/)
  })
 }
})
test('non-array gate inventories are rejected without crashing',()=>withManifest(JSON.stringify({
 schema:1,kind:'production_scorecard',commit:'a'.repeat(40),gates:{'UX-01':{score:5}},
}),()=>{
 const result=execute('--certify')
 assert.equal(result.status,1)
 assert.match(result.stderr,/One review required for every single quality gate/)
 assert.doesNotMatch(result.stderr,/TypeError/)
}))
