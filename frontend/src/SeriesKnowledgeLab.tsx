import {useEffect,useRef,useState} from 'react'
import './series-knowledge-lab.css'

type Entity={id:string;name:string;kind:string}
type Volume={id:string;ordinal:number;title:string}
type Citation={source_id:string;title:string;book:number;volume:string;start:number;end:number;quote:string;sha256:string}
type Claim={id:string;subject_id:string;subject:string;predicate:string;value:string;target:string|null;target_id:string|null;scope:string;knower:string|null;knower_id:string|null;from_book:number;from_sequence:number;citation:Citation}
type Change={subject:string;predicate:string;scope:string;older:Claim;newer:Claim;classification:'recorded_change'|'coexisting_claims'|'possible_conflict';requires_author_review:boolean}
type Thread={subject_id:string;name:string;status:string;setups:Claim[];payoffs:Claim[];evidence:Claim[];requires_author_review:boolean}
type Knowledge={answer_status:string;approved_evidence_count:number;pending_proposals_visible:number;
 world_truths:Claim[];reader_reveals:Claim[];character_beliefs:Claim[];relationships:Claim[];
 psychology:Record<string,Claim[]>;history:Claim[];recorded_changes:Change[];possible_conflicts:Change[];
 causal_links:Claim[];thread_lifecycle:Thread[];
 limitations:string[];evidence_only:boolean;model_called:boolean}
type Props={seriesId:string;volumes:Volume[];entities:Entity[];
 onInspect:(sourceId:string,query:string,position:number)=>void;onReview:()=>void}
const API='http://127.0.0.1:8000/api'
const lenses=[['world_truths','World truth'],['character_beliefs','Character belief'],['reader_reveals','Reader knowledge'],['relationships','Relationships'],['psychology','Character psychology'],['causal_links','Causal links'],['thread_lifecycle','Plot promises'],['recorded_changes','Recorded changes'],['possible_conflicts','Continuity alerts']] as const
export default function SeriesKnowledgeLab({seriesId,volumes,entities,onInspect,onReview}:Props){
 const [book,setBook]=useState(volumes.at(-1)?.ordinal||1)
 const [sequence,setSequence]=useState(999999)
 const [subject,setSubject]=useState('')
 const [other,setOther]=useState('')
 const [knower,setKnower]=useState('')
 const [active,setActive]=useState<(typeof lenses)[number][0]>('world_truths')
 const [knowledge,setKnowledge]=useState<Knowledge|null>(null)
 const [working,setWorking]=useState(false)
 const [error,setError]=useState('')
 const [modelStatus,setModelStatus]=useState<{status:string;models:string[];next_step:string;source_text_sent:boolean;generation_tested:boolean}|null>(null)
 const [modelRefresh,setModelRefresh]=useState(0)
 const [probeModel,setProbeModel]=useState('')
 const [probing,setProbing]=useState(false)
 const [probeError,setProbeError]=useState('')
 const [probeResult,setProbeResult]=useState<{status:string;elapsed_ms:number;detail:string;source_text_sent:boolean;exact_answer_verified:boolean;limitations:string}|null>(null)
 type StreamResult={status:string;detail:string;elapsed_ms:number;first_token_ms:number|null;load_ms:number|null;
  prompt_eval_ms:number|null;generation_ms:number|null;prompt_tokens:number|null;generated_tokens:number|null;tokens_per_second:number|null;
  stream_events:number;stream_completed:boolean;exact_answer_verified:boolean;source_text_sent:boolean;limitations:string}
 const [streamBusy,setStreamBusy]=useState(false)
 const [streamError,setStreamError]=useState('')
 const [streamResult,setStreamResult]=useState<StreamResult|null>(null)
 const streamController=useRef<AbortController|null>(null)
 useEffect(()=>()=>{streamController.current?.abort()},[seriesId])
 async function runStreamProbe(){
  if(!probeModel||streamBusy||probing)return
  const controller=new AbortController()
  streamController.current=controller
  setStreamBusy(true);setStreamError('');setStreamResult(null)
  try{
   const response=await fetch(API+'/series/'+encodeURIComponent(seriesId)+'/local-model-stream-probe',{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({model:probeModel}),signal:controller.signal,
   })
   const payload=await response.json()
   if(!response.ok)throw Error(payload.detail||'Streaming test failed')
   if(!controller.signal.aborted)setStreamResult(payload as StreamResult)
  }catch(error){if(!controller.signal.aborted)setStreamError(String(error))}
  finally{if(streamController.current===controller){streamController.current=null;setStreamBusy(false)}}
 }
 function cancelStreamProbe(){
  streamController.current?.abort()
  streamController.current=null
  setStreamBusy(false)
  setStreamError('Test cancelled by author; no source text or canon changed.')
 }
 async function runProbe(){
   if(!probeModel||probing)return
   setProbing(true);setProbeError('');setProbeResult(null)
   try{
     const response=await fetch(API+'/series/'+encodeURIComponent(seriesId)+'/local-model-probe',{
       method:'POST',headers:{'Content-Type':'application/json'},
       body:JSON.stringify({model:probeModel}),
     })
     const payload=await response.json()
     if(!response.ok)throw Error(payload.detail||'Local model probe failed')
     setProbeResult(payload)
   }catch(cause){setProbeError(String(cause))}
   finally{setProbing(false)}
 }
 useEffect(()=>{setBook(volumes.at(-1)?.ordinal||1);setKnowledge(null);setError('')},[seriesId,volumes.length])
 useEffect(()=>{
   const controller=new AbortController()
   setModelStatus(null)
   void fetch(API+'/series/'+encodeURIComponent(seriesId)+'/local-model-readiness',{
     signal:controller.signal,
   }).then(async response=>{
     const result=await response.json()
     if(!response.ok)throw Error('Local model health check unavailable')
     return result
   }).then(value=>{if(!controller.signal.aborted)setModelStatus(value)})
     .catch(()=>{if(!controller.signal.aborted)setModelStatus({
       status:'unavailable',models:[],next_step:'Source research remains available without a model.',
       source_text_sent:false,generation_tested:false,
     })})
   return()=>controller.abort()
 },[seriesId,modelRefresh])
 useEffect(()=>{
   let alive=true
   setWorking(true);setError('');setKnowledge(null)
   const params=new URLSearchParams({book:String(book),sequence:String(sequence)})
   if(subject)params.set('subject_id',subject)
   if(other)params.set('other_id',other)
   if(knower)params.set('knower_id',knower)
   fetch(API+'/series/'+encodeURIComponent(seriesId)+'/knowledge-lab?'+params)
     .then(async response=>{
       const body=await response.json()
       if(!response.ok)throw Error(body.detail||'Knowledge research failed')
       return body as Knowledge
     }).then(payload=>{if(alive)setKnowledge(payload)})
     .catch(cause=>{if(alive)setError(String(cause))})
     .finally(()=>{if(alive)setWorking(false)})
   return()=>{alive=false}
 },[seriesId,book,sequence,subject,other,knower])
 function citation(claim:Claim){
   return <button type="button" className="knowledge-citation"
     onClick={()=>onInspect(claim.citation.source_id,claim.citation.quote,claim.citation.start)}>
     <strong>Book {claim.citation.book} · {claim.citation.volume}</strong>
     <span>Inspect original evidence at character {claim.citation.start.toLocaleString()} ↗</span>
     <small>SHA-256 {claim.citation.sha256.slice(0,12)}…</small>
   </button>
 }
 function claimCard(claim:Claim){
   return <article className="knowledge-claim" key={claim.id}>
     <div className="knowledge-claim-top"><strong>{claim.subject} · {claim.predicate.replaceAll('_',' ')}</strong>
       <span>Book {claim.from_book}{claim.from_sequence?'/scene '+claim.from_sequence:''}</span></div>
     <p>{claim.target||claim.value||'Source-bound assertion'}</p>
     {claim.knower&&<small>Known or believed by {claim.knower}</small>}
     <blockquote>{claim.citation.quote}</blockquote>
     {citation(claim)}
   </article>
 }
 let rows:Claim[]=[]
 if(knowledge){
   if(active==='psychology')rows=Object.values(knowledge.psychology).flat()
   else if(active==='recorded_changes'||active==='possible_conflicts'||active==='thread_lifecycle')rows=[]
   else rows=knowledge[active] as Claim[]
 }
 const alerts=active==='possible_conflicts'?knowledge?.possible_conflicts:knowledge?.recorded_changes
 return <section className="series-knowledge-lab" aria-label="Story knowledge and continuity laboratory">
   <div className="knowledge-intro">
     <div><span>STAGE II · EVIDENCE, NOT ASSUMPTION</span>
       <h2>What does the story establish?</h2>
       <p>Trace approved character knowledge, relationships and plot promises without revealing future books. Every claim links to the original passage.</p></div>
     <div className="knowledge-state"><strong>{knowledge?.approved_evidence_count??'—'}</strong><small>Approved claims visible at this point</small></div>
   </div>
   <div className="knowledge-controls knowledge-primary-controls">
     <label>Reading position<select value={book} onChange={e=>setBook(Number(e.target.value))}>
       {volumes.map(v=><option key={v.id} value={v.ordinal}>Book {v.ordinal} · {v.title}</option>)}
     </select></label>
     <label>Subject<select value={subject} onChange={e=>setSubject(e.target.value)}>
       <option value="">All source-backed subjects</option>
       {entities.map(e=><option key={e.id} value={e.id}>{e.name} · {e.kind}</option>)}
     </select></label>
   </div>
   <details className="knowledge-advanced">
     <summary>Refine by scene, other participant or belief holder</summary>
     <div className="knowledge-controls knowledge-extra-controls">
       <label>Scene sequence<input type="number" min={0} max={999999} value={sequence}
         onChange={e=>setSequence(Math.min(999999,Math.max(0,Number(e.target.value)||0)))}/></label>
       <label>Related participant<select value={other} onChange={e=>setOther(e.target.value)}>
         <option value="">Any</option>
         {entities.filter(e=>e.id!==subject).map(e=><option key={e.id} value={e.id}>{e.name}</option>)}
       </select></label>
       <label>Whose belief?<select value={knower} onChange={e=>setKnower(e.target.value)}>
         <option value="">Every approved belief holder</option>
         {entities.filter(e=>e.kind==='character').map(e=><option key={e.id} value={e.id}>{e.name}</option>)}
       </select></label>
     </div>
   </details>
   <label className="knowledge-mobile-lens">What would you like to inspect?
     <select value={active} onChange={e=>setActive(e.target.value as typeof active)}>
       {lenses.map(([key,label])=><option key={key} value={key}>{label}</option>)}
     </select>
   </label>
   <nav className="knowledge-lenses" aria-label="Investigate a story knowledge lens">
     {lenses.map(([id,label])=><button key={id} type="button" aria-pressed={active===id}
       onClick={()=>setActive(id)}>{label}
       {active===id&&<span aria-hidden="true"> ·</span>}
     </button>)}
   </nav>
   {working&&<p role="status">Examining approved source evidence…</p>}
   {error&&<p role="alert" className="knowledge-error">{error}</p>}
   {knowledge&&!working&&<div className="knowledge-results">
     <div className="knowledge-summary">
       <div><strong>{knowledge.answer_status==='grounded'?'Source-backed research':'Not enough approved evidence'}</strong>
         <p>{knowledge.answer_status==='grounded'
           ?'These are reviewed assertions, not independently inferred truths.'
           :'This series has no approved claims for this position and selection. Searching text does not create knowledge.'}</p>
       </div>
       {knowledge.pending_proposals_visible>0&&<button type="button" onClick={onReview}>
         {knowledge.pending_proposals_visible} pending proposal{knowledge.pending_proposals_visible===1?'':'s'} · Review evidence
       </button>}
     </div>
     {active==='thread_lifecycle'?
       <div className="knowledge-threads">
         {knowledge.thread_lifecycle.length?knowledge.thread_lifecycle.map(thread=><article key={thread.subject_id} className="knowledge-change">
           <span>{thread.status.toUpperCase()} · AUTHOR-CURATED SOURCE CHAIN</span>
           <h3>{thread.name}</h3>
           <div className="knowledge-change-pair">
             <div><small>Setup evidence</small>
               {thread.setups.length?thread.setups.map(claimCard):<p className="knowledge-empty">No reviewed setup recorded</p>}</div>
             <div><small>Payoff evidence</small>
               {thread.payoffs.length?thread.payoffs.map(claimCard):<p className="knowledge-empty">No reviewed payoff recorded</p>}</div>
           </div>
           <p>This is only a chain of author-approved statements, not a conclusion about dramatic effectiveness.</p>
         </article>):<p className="knowledge-empty">No approved setup or payoff claims at this story position. This does not prove a plot thread is missing.</p>}
       </div>
       :active==='recorded_changes'||active==='possible_conflicts'?
       <div className="knowledge-changes">
         {alerts?.length?alerts.map(item=><article key={item.older.id+'-'+item.newer.id}
           className="knowledge-change">
           <span>{item.classification==='possible_conflict'?'POSSIBLE CONTRADICTION':'RECORDED CHANGE'}</span>
           <h3>{item.subject} · {item.predicate.replaceAll('_',' ')}</h3>
           <div className="knowledge-change-pair">
             <div><small>Earlier · Book {item.older.from_book}</small>{claimCard(item.older)}</div>
             <div><small>Later · Book {item.newer.from_book}</small>{claimCard(item.newer)}</div>
           </div>
           <p>Interpretation requires author review. A change may be intentional, and two claims may coexist.</p>
         </article>):<p className="knowledge-empty">No approved, source-grounded changes or conflicts found for this selected position.</p>}
       </div>
       :rows.length?<div className="knowledge-cards">{rows.map(claimCard)}</div>
       :<p className="knowledge-empty">No author-approved citations support this lens at the selected reading position. This is an abstention, not a claim that nothing happened.</p>}
     <details className="knowledge-limits"><summary>Evidence limits and interpretation rules</summary>
       {knowledge.limitations.map(rule=><p key={rule}>{rule}</p>)}
     </details>
   </div>}
   <details className="knowledge-model-health">
     <summary><span>Local AI readiness</span><strong>{modelStatus?modelStatus.status.replaceAll('_',' '):'Checking…'}</strong></summary>
     <p>{modelStatus?.next_step||'Checking the local Ollama service only.'}</p>
     <p>No book text is transmitted by this health check. An installed model does not prove successful generation or continuity reasoning.</p>
     {!!modelStatus?.models.length&&<label className="knowledge-probe-label">
       Model for synthetic test
       <select value={probeModel} onChange={e=>{setProbeModel(e.target.value);setProbeResult(null)}}>
         <option value="">Choose an installed model</option>
         {modelStatus.models.map(name=><option key={name} value={name}>{name}</option>)}
       </select></label>}
     <div><button type="button" onClick={()=>setModelRefresh(n=>n+1)}>Recheck local models</button>
       <button type="button" onClick={onReview}>Review selected source or request unsaved suggestions ↗</button>
       <button type="button" disabled={!probeModel||probing||streamBusy} onClick={()=>void runProbe()}>
         {probing?'Testing synthetic sentence…':'Verify local model actually answers'}
       </button></div>
     <div className="knowledge-stream-controls">
       <button type="button" disabled={!probeModel||probing||streamBusy} onClick={()=>void runStreamProbe()}>
         {streamBusy?'Measuring local streaming…':'Measure startup and streaming (45s max)'}
       </button>
       {streamBusy&&<button type="button" onClick={cancelStreamProbe}>Cancel streaming test</button>}
       <small>Uses invented fiction only. The server cancels an active model request when the browser disconnects. No source text is sent.</small>
     </div>
     {streamError&&<p role="status" className="knowledge-error">{streamError}</p>}
     {streamResult&&<div role="status" className="knowledge-stream-result">
       <strong>{streamResult.status==='passed'?'Synthetic streaming verified':'Streaming not verified: '+streamResult.status}</strong>
       <p>{streamResult.detail}. Completed: {streamResult.stream_completed?'yes':'no'}.</p>
       <dl>
         <div><dt>First generated text</dt><dd>{streamResult.first_token_ms?.toLocaleString()??'not received'} ms</dd></div>
         <div><dt>Complete request</dt><dd>{streamResult.elapsed_ms.toLocaleString()} ms</dd></div>
         <div><dt>Model load</dt><dd>{streamResult.load_ms?.toLocaleString()??'unreported'} ms</dd></div>
         <div><dt>Prompt evaluation</dt><dd>{streamResult.prompt_eval_ms?.toLocaleString()??'unreported'} ms</dd></div>
         <div><dt>Generation</dt><dd>{streamResult.generation_ms?.toLocaleString()??'unreported'} ms</dd></div>
         <div><dt>Generated tokens</dt><dd>{streamResult.generated_tokens??'unreported'}</dd></div>
         <div><dt>Generation rate</dt><dd>{streamResult.tokens_per_second===null?'unreported':streamResult.tokens_per_second.toLocaleString()+' tokens/sec'}</dd></div>
       </dl>
       <p>{streamResult.limitations}</p>
     </div>}
     {probeError&&<p role="alert" className="knowledge-error">{probeError}</p>}
     {probeResult&&<div className="knowledge-probe-result" role="status">
       <strong>{probeResult.status==='passed'?'Synthetic inference passed':'Not verified — '+probeResult.status}</strong>
       <p>{probeResult.detail} · {probeResult.elapsed_ms.toLocaleString()} ms</p>
       <p>{probeResult.limitations}</p>
     </div>}
   </details>
 </section>
}
