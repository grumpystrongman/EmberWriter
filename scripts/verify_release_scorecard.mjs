// Fail-closed certification gate for EVERY EmberWriter author-quality requirement.
// "Catalog" validates structure. "Certify" requires per-build test artifacts and
// independent named reviewers. Neither screenshots nor LLM self-scoring suffice.
import fs from 'node:fs'
import path from 'node:path'
import crypto from 'node:crypto'
import {execFileSync} from 'node:child_process'
import {createRequire} from 'node:module'
const root=path.resolve(import.meta.dirname,'..')
const require=createRequire(path.join(root,'frontend','package.json'))
const ts=require('typescript')
const source=fs.readFileSync(path.join(root,'frontend','src','release-gates.ts'),'utf8')
const js=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText
const {RELEASE_GATES,SCORECARD_GROUPS}=await import('data:text/javascript;base64,'+Buffer.from(js).toString('base64'))
const ids=new Set()
const issues=[]
for(const g of RELEASE_GATES){
 if(!/^((UX|SER|ENG|PUB|CRAFT)-\d{2})$/.test(g.id)||ids.has(g.id))issues.push('Invalid or duplicate gate: '+g.id)
 ids.add(g.id)
 if(!SCORECARD_GROUPS.includes(g.group))issues.push('Unknown quality group: '+g.id)
 if(!g.proof||g.proof.length<35||!g.outcome||g.outcome.length<35)issues.push('Weak acceptance contract: '+g.id)
 if(!['P0','P1','P2'].includes(g.priority))issues.push('Invalid severity: '+g.id)
 if(g.score!==null&&!(Number.isInteger(g.score)&&g.score>=1&&g.score<=4))issues.push('No provisional 5/5 allowed: '+g.id)
}
if(ids.size!==38||SCORECARD_GROUPS.length!==5)issues.push('Scorecard inventory changed: requires a reviewed schema migration (expected 38 gates / five groups)')
if(!RELEASE_GATES.some(g=>g.id==='SER-06')||!RELEASE_GATES.some(g=>g.id==='UX-08'))issues.push('Continuity and accessibility must never be omitted')
if(process.argv[2]==='--catalog'){
 console.log(JSON.stringify({gates:ids.size,groups:SCORECARD_GROUPS,provisional5Count:0,valid:!issues.length,issues},null,2))
 process.exit(issues.length?1:0)
}
if(process.argv[2]!=='--certify'){
 console.error('Usage: node scripts/verify_release_scorecard.mjs --catalog | --certify PATH_TO_RELEASE_EVIDENCE.json')
 process.exit(2)
}
const manifestPath=process.argv[3]&&path.resolve(process.argv[3])
if(!manifestPath||!fs.existsSync(manifestPath)){
 console.error('RELEASE HOLD: missing release scorecard evidence manifest; 38 gates remain locked.')
 process.exit(1)
}
const manifest=JSON.parse(fs.readFileSync(manifestPath,'utf8'))
let gitSha
try{gitSha=execFileSync('git',['rev-parse','HEAD'],{cwd:root,encoding:'utf8'}).trim()}catch{issues.push('Unable to establish candidate Git commit')}
if(!/^[0-9a-f]{40}$/.test(manifest.commit||'')||manifest.commit!==gitSha)issues.push('All receipts must target the exact shipping commit')
if(manifest.schema!==1||manifest.kind!=='production_scorecard'||manifest.synthetic||manifest.ai_assessed)issues.push('Real production-candidate evidence required; synthetic/AI-only signoff rejected')
const reviews=manifest.gates||[]
if(!Array.isArray(reviews)||reviews.length!==RELEASE_GATES.length)issues.push('One review required for every single quality gate')
const records=new Map()
for(const g of reviews){
 if(!g||typeof g.id!=='string'||records.has(g.id)){issues.push('Duplicate or invalid gate review');continue}
 records.set(g.id,g)
}
for(const gate of RELEASE_GATES){
 const record=records.get(gate.id)
 if(!record||record.score!==5||record.commit!==gitSha){issues.push(gate.id+': missing same-commit 5/5 approval');continue}
 if(!Array.isArray(record.evidence)||!record.evidence.length){issues.push(gate.id+': test artifacts missing');continue}
 let automated=false,author=false,expert=false
 const reviewers={author:new Set(),expert:new Set()}
 for(const proof of record.evidence){
  if(!proof||proof.synthetic||proof.ai_only||proof.mock) {issues.push(gate.id+': synthetic or mock evidence rejected');continue}
  if(proof.kind==='test'){
   if(typeof proof.path!=='string'||typeof proof.sha256!=='string'||!(/^[a-f0-9]{64}$/.test(proof.sha256))){issues.push(gate.id+': invalid test receipt');continue}
   const base=path.dirname(manifestPath)
   const file=path.resolve(base,proof.path)
   if(!file.startsWith(base+path.sep)||proof.path.includes('..')){issues.push(gate.id+': evidence path escapes the approved directory');continue}
   if(!fs.existsSync(file)||!fs.statSync(file).isFile()){issues.push(gate.id+': evidence file missing');continue}
   const actual=crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
   if(actual!==proof.sha256||proof.commit!==gitSha||proof.result!=='passed'){issues.push(gate.id+': test evidence hash, commit or result invalid');continue}
   automated=true
  }else if(proof.kind==='human'){
   if(typeof proof.reviewer!=='string'||proof.reviewer.trim().length<4||typeof proof.assessment!=='string'||proof.assessment.trim().length<120||!/^\d{4}-\d{2}-\d{2}$/.test(proof.reviewed_at||'')||proof.commit!==gitSha||proof.approved!==true){
    issues.push(gate.id+': independent human acceptance incomplete');continue
   }
   if(proof.role==='author'){author=true;reviewers.author.add(proof.reviewer.trim().toLowerCase())}
   if(proof.role==='ux_expert'||proof.role==='engineer'){expert=true;reviewers.expert.add(proof.reviewer.trim().toLowerCase())}
  }
 }
 if(!automated||!author||!expert)issues.push(gate.id+': requires hashed passing test and independent author + expert reviews')
 if(author&&expert&&[...reviewers.author].every(name=>reviewers.expert.has(name)))issues.push(gate.id+': author and expert signoffs must be independent')
}
if(records.size!==ids.size)issues.push('Unrecognized/missing gate records; no partial release allowed')
if(issues.length){console.error('RELEASE HOLD — '+issues.length+' unmet requirements\n'+issues.join('\n'));process.exit(1)}
console.log('CERTIFIED: all '+ids.size+' quality gates verified with same-commit evidence and independent author/expert attestations')
