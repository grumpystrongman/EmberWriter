import {useMemo,useState} from 'react'
import {RELEASE_GATES,SCORECARD_GROUPS,RELEASE_POLICY,type GateGroup,type ReleaseGate} from './release-gates'
import './release-lab.css'

type Filter='all'|'blocker'|'unrated'|'near'
const names:{[key in GateGroup]:string}={
 'Author experience':'Writing experience',
 'Story intelligence':'Story intelligence',
 'Safety & infrastructure':'Reliability & safety',
 'Publishing & delivery':'Publishing quality',
 'Professional author features':'Author craft'
}
function verdict(gate:ReleaseGate){
 if(gate.score===null)return 'Unverified'
 if(gate.score===5)return 'Proof needed'
 if(gate.score>=4)return 'Needs certification'
 return 'Needs buildout'
}
const formatted=RELEASE_GATES.map(gate=>gate.id+' — '+gate.title+'\nOutcome: '+gate.outcome+'\n5/5 proof: '+gate.proof).join('\n\n')

export default function ReleaseLab(){
 const [selected,setSelected]=useState<GateGroup|'all'>('all')
 const [filter,setFilter]=useState<Filter>('all')
 const [query,setQuery]=useState('')
 const [expanded,setExpanded]=useState<string|null>(null)
 const [copyMessage,setCopyMessage]=useState('')
 const [showPolicy,setShowPolicy]=useState(false)
 const counts=useMemo(()=>{
   const verified=0 // No entry has a human + automated SHA-bound 5/5 signoff.
   const blocked=RELEASE_GATES.filter(g=>g.priority==='P0').length
   const unrated=RELEASE_GATES.filter(g=>g.score===null).length
   return {verified,blocked,unrated,total:RELEASE_GATES.length}
 },[])
 const current=useMemo(()=>RELEASE_GATES.filter(g=>{
   if(selected!=='all'&&g.group!==selected)return false
   if(filter==='blocker'&&g.priority!=='P0')return false
   if(filter==='unrated'&&g.score!==null)return false
   if(filter==='near'&&!(g.score!==null&&g.score>=4))return false
   if(query&&!([g.id,g.title,g.outcome,g.proof,...g.evidence].join(' ').toLowerCase().includes(query.toLowerCase())))return false
   return true
 }),[selected,filter,query])
 const groupSummary=SCORECARD_GROUPS.map(group=>{
   const gates=RELEASE_GATES.filter(g=>g.group===group)
   const rated=gates.filter(g=>g.score!==null)
   const avg=rated.length?rated.reduce((sum,gate)=>sum+(gate.score||0),0)/rated.length:0
   return {group,gates,avg}
 })
 async function copy(){
   try{await navigator.clipboard.writeText('EMBERWRITER RELEASE GATES\n\n'+formatted+'\n\n'+RELEASE_POLICY);setCopyMessage('All acceptance criteria copied.')}
   catch{setCopyMessage('Clipboard unavailable in this browser.')}
 }
 return <section className="release-lab" aria-label="Complete author release readiness scorecard">
   <header className="rl-hero">
     <div className="rl-hero-copy">
       <span className="rl-eyebrow">EMBERWRITER / THE AUTHOR QUALITY LAB</span>
       <h2>Nothing ships at four.</h2>
       <p>The entire product. One release gate. Every tool must serve the story, preserve the manuscript, and earn five out of five with repeatable proof.</p>
       <div className="rl-hero-actions">
         <button type="button" onClick={()=>setShowPolicy(v=>!v)}
           aria-expanded={showPolicy}>Read the release contract {showPolicy?'−':'+'}</button>
         <button type="button" onClick={()=>void copy()}>Copy acceptance plan ↗</button>
       </div>
       {copyMessage&&<span className="rl-copy-status" role="status">{copyMessage}</span>}
     </div>
     <div className="rl-release-ring" role="img" aria-label="Zero of the required release categories independently certified">
       <div className="rl-release-ring-inner">
         <span>0</span><small>PROVEN 5/5</small>
         <strong>NO RELEASE</strong>
       </div>
     </div>
   </header>
   {showPolicy&&<div className="rl-contract" role="note">
     <strong>Our contract with the author</strong>
     <p>{RELEASE_POLICY}</p><p>Numbers below are provisional observations, not certification. A score of 5 requires accepted evidence from real task runs, actual devices, tests, and author review tied to the exact release build.</p>
   </div>}
   <div className="rl-kpis" aria-label="Current readiness indicators">
     <div><span>Entire product</span><strong>{counts.total}</strong><small>Individual release criteria</small></div>
     <div><span>Certified</span><strong>{counts.verified}</strong><small>With complete 5/5 proof</small></div>
     <div><span>Highest risk</span><strong>{counts.blocked}</strong><small>P0 blocks before release</small></div>
     <div><span>Unrated</span><strong>{counts.unrated}</strong><small>Need fresh measurements</small></div>
   </div>
   <div className="rl-section-heading"><span>THE FIVE QUALITY SYSTEMS</span><h3>Where the work stands</h3>
     <p>Choose a domain to inspect every requirement, its present evidence, and the exact proof required to finish.</p></div>
   <div className="rl-domains" role="group" aria-label="Filter quality systems">
     {groupSummary.map(({group,gates,avg},index)=><button key={group} type="button"
       className={selected===group?'rl-domain active':'rl-domain'} aria-pressed={selected===group}
       onClick={()=>{setSelected(selected===group?'all':group);setExpanded(null)}}>
       <span className="rl-domain-index">0{index+1} / {gates.length} GATES</span>
       <span className="rl-domain-meter" style={{'--fill':String(avg/5*100)+'%'} as React.CSSProperties} aria-hidden="true"/>
       <strong>{names[group]}</strong>
       <small>{avg.toFixed(1)} / 5 provisional</small>
       <span className="rl-domain-line"><i style={{width:avg/5*100+'%'}}/></span>
     </button>)}
   </div>
   <div className="rl-section-heading rl-work-head">
     <div><span>RELEASE CONDITIONS / NOT A CHECKBOX EXERCISE</span><h3>Earn the next five</h3>
       <p>{current.length} of {counts.total} quality gates shown. Select a gate to inspect its measurable definition of done.</p></div>
     <div className="rl-tools">
       <label htmlFor="rl-search">Find a requirement</label>
       <input id="rl-search" type="search" value={query} placeholder="Find continuity, keyboard, export..."
         onChange={e=>setQuery(e.target.value)}/>
     </div>
   </div>
   <div className="rl-filterbar" role="group" aria-label="Filter scorecard gates">
     {([['all','All gates'],['blocker','P0 blockers'],['unrated','Needs baseline'],['near','Near validation']] as const).map(([key,title])=>
       <button key={key} type="button" className={filter===key?'active':''}
         aria-pressed={filter===key} onClick={()=>{setFilter(key);setExpanded(null)}}>{title}</button>)}
     {(filter!=='all'||selected!=='all'||query)&&<button type="button" onClick={()=>{setFilter('all');setSelected('all');setQuery('');setExpanded(null)}}>Reset filters ↺</button>}
   </div>
   <div className="rl-gates">
     {current.map(gate=>{
       const active=expanded===gate.id
       return <article key={gate.id} className={'rl-gate'+(active?' expanded':'')}>
         <button type="button" className="rl-gate-trigger"
           aria-expanded={active} aria-controls={'rl-proof-'+gate.id}
           onClick={()=>setExpanded(active?null:gate.id)}>
           <span className="rl-gate-code">{gate.id}</span>
           <span className="rl-gate-info"><strong>{gate.title}</strong><small>{names[gate.group]} · {gate.priority} · {verdict(gate)}</small></span>
           <span className={'rl-gate-score'+(gate.score===null?' unrated':'')} aria-label={gate.score===null?'Not rated':gate.score+' out of five provisionally'}>{gate.score===null?'—':gate.score}<small>/5</small></span>
           <span className="rl-gate-chevron" aria-hidden="true">{active?'−':'+'}</span>
         </button>
         {active&&<div className="rl-gate-detail" id={'rl-proof-'+gate.id}>
           <div><span className="rl-detail-label">THE AUTHOR OUTCOME</span><p>{gate.outcome}</p></div>
           <div><span className="rl-detail-label">WHAT EARNS 5/5</span><p>{gate.proof}</p></div>
           <div className="rl-detail-evidence"><span className="rl-detail-label">CURRENT EVIDENCE · NOT A CERTIFICATION</span>
             {gate.evidence.length?gate.evidence.map((item,i)=><p key={i}>◆ {item}</p>):<p>No verified test receipt yet.</p>}</div>
           <div className="rl-detail-footer"><span>{gate.owner==='both'?'Engineering + working authors must sign off':gate.owner==='engineering'?'Engineering must verify':'Author review required'}</span><strong>5/5 still locked</strong></div>
         </div>}
       </article>
     })}
     {!current.length&&<div className="rl-no-matches">No gates match. Clear the filters or search for another feature.</div>}
   </div>
   <footer className="rl-footer">
     <strong>Quality is not a sticker.</strong>
     <p>Shipping is blocked until every proof package is complete. The scorecard must never interpret a screenshot, a passing unit test, or an attractive mockup as full author acceptance.</p>
   </footer>
 </section>
}
