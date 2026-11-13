import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import os from 'node:os'
import {spawnSync} from 'node:child_process'
const root=path.resolve(import.meta.dirname,'..')
const runner=path.join(root,'scripts','verify_release_scorecard.mjs')
function execute(...args){return spawnSync(process.execPath,[runner,...args],{cwd:root,encoding:'utf8',timeout:15000})}
test('the unified author scorecard contains all 38 requirements across five systems',()=>{
 const result=execute('--catalog')
 assert.equal(result.status,0,result.stderr)
 const parsed=JSON.parse(result.stdout)
 assert.equal(parsed.gates,38)
 assert.equal(parsed.groups.length,5)
 assert.equal(parsed.provisional5Count,0)
})
test('missing release evidence hard-blocks stable certification',()=>{
 const result=execute('--certify',path.join(root,'does-not-exist-scorecard.json'))
 assert.equal(result.status,1)
 assert.match(result.stderr,/RELEASE HOLD/)
})
test('synthetic and AI-only self-review cannot certify any category',()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'ember-release-scorecard-'))
 try{
  const file=path.join(dir,'manifest.json')
  fs.writeFileSync(file,JSON.stringify({
   schema:1,kind:'production_scorecard',synthetic:true,ai_assessed:true,
   commit:'a'.repeat(40),gates:[{id:'UX-01',score:5,commit:'a'.repeat(40),evidence:[]}],
  }))
  const result=execute('--certify',file)
  assert.equal(result.status,1)
  assert.match(result.stderr,/synthetic\/AI-only signoff rejected/)
  assert.match(result.stderr,/missing same-commit 5\/5 approval/)
 }finally{fs.rmSync(dir,{recursive:true,force:true})}
})
test('a list of provisional scores is never mistaken for release certification',()=>{
 const file=fs.readFileSync(path.join(root,'frontend','src','release-gates.ts'),'utf8')
 assert.match(file,/All gates must attain independently validated 5\/5/)
 assert.match(file,/SER-04/)
 assert.match(file,/ENG-01/)
 assert.match(file,/PUB-04/)
})
