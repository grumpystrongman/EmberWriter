import { useEffect, useMemo, useRef, useState } from 'react'
import './series-evidence-search.css'
import SeriesCharacterEvidenceMap from './SeriesCharacterEvidenceMap'

type Match = {
 book:number;volume:string;source_id:string;
 excerpt_start:number;excerpt_end:number;excerpt:string
}
type SearchResponse = {
 series_id:string;query:string;min_book:number;max_book:number;books:number;
 sources:number;total_hits:number;results:Match[];disclaimer:string
}
type Props = {
 seriesId:string;bookCount:number;characters:{id:string;name:string;kind:string}[];onOpenSource:(id:string,query:string,position:number)=>void;
 onDraftClaim:(entry:Match)=>void
}
const EXAMPLES=['Remo','Chiun','Smith','CURE']
type Citation={reading_period?:string;book?:number;volume?:string;source_id?:string;source_title?:string;excerpt?:string;excerpt_start?:number;quote?:string;quote_start?:number;start?:number;end?:number}
type GroundedAnswer={answer?:string;status?:string;abstained?:boolean;review_only?:boolean;reasons?:string[];reason_detail?:string;safety_reasons?:string[];safety_flags?:string[]|Record<string,boolean|string>;citations?:Citation[];evidence?:Citation[];passages?:Citation[];disclaimer?:string;semantic_entailment?:string;auto_approval_allowed?:boolean;uncertainty?:string;local_verifier?:string;method?:string;retrieval_guidance?:string;author_review_required?:boolean;context_cards?:Array<{id:string;facet:string;status:string}>}
type ContextCard={id:string;question:string;interpretation:string;facet:string;as_of_book:number;review_state:string;citations:Citation[]}
const API=((import.meta as ImportMeta & {env?:{VITE_API_BASE_URL?:string}}).env?.VITE_API_BASE_URL)||'http://127.0.0.1:8000/api'

type MapSource={id:string;title:string;book:number;volume:string}
type MapJob={id:string;source_id:string;book:number;model:string;next_offset:number;length:number;accepted?:number;discarded?:number}
type MapClaim={id:string;source_id:string;source_hash:string;book:number;start:number;end:number;quote:string;kind:string;subject:string;predicate:string;object:string;scope:string;knower:string;story_time:string;status:string;snapshot_verified:boolean}
function NarrativeMap({seriesId,cutoff,models,model,setModel,modelStatus,recheck,onOpenSource}:{seriesId:string;cutoff:number;models:string[];model:string;setModel:(v:string)=>void;modelStatus:string;recheck:()=>void;onOpenSource:Props['onOpenSource']}){
 const [sources,setSources]=useState<MapSource[]>([]),[sourceId,setSourceId]=useState('')
 const [job,setJob]=useState<MapJob|null>(null),[claims,setClaims]=useState<MapClaim[]>([])
 const [busy,setBusy]=useState(false),[loaded,setLoaded]=useState(false),[message,setMessage]=useState('')
 const controller=useRef(new AbortController())
 useEffect(()=>()=>controller.current.abort(),[])
 const base=API+'/series/'+encodeURIComponent(seriesId)
 async function request(path:string,options:RequestInit={}){
   const response=await fetch(base+path,{...options,signal:controller.current.signal})
   const data=await response.json()
   if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:'Request failed')
   return data
 }
 async function timeline(){
   const data=await request('/narrative-map?'+new URLSearchParams({as_of_book:String(cutoff)}))
   if(!controller.current.signal.aborted)setClaims((data.items||[]).filter((c:MapClaim)=>c.book<=cutoff))
 }
 async function load(){
   setBusy(true);setMessage('')
   try{
     const [detail]=await Promise.all([request(''),timeline()])
     if(controller.current.signal.aborted)return
     const found:MapSource[]=(detail.volumes||[]).flatMap((v:{ordinal:number;title:string;sources:{id:string;title:string}[]})=>v.ordinal<=cutoff?(v.sources||[]).map(source=>({id:source.id,title:source.title,book:v.ordinal,volume:v.title})):[])
     setSources(found);setSourceId(previous=>found.some(source=>source.id===previous)?previous:found[0]?.id||'');setLoaded(true)
   }catch(e){if(!controller.current.signal.aborted)setMessage(e instanceof Error?e.message:'Could not load sources')}
   finally{if(!controller.current.signal.aborted)setBusy(false)}
 }
 async function start(){
   if(!sourceId||!models.includes(model)||busy)return
   setBusy(true);setMessage('')
   try{const data=await request('/narrative-map/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({source_id:sourceId,model})});if(!controller.current.signal.aborted){setJob(data);setMessage('Scan ready; existing progress for this source and model is resumed.')}}
   catch(e){if(!controller.current.signal.aborted)setMessage(e instanceof Error?e.message:'Could not start scan')}
   finally{if(!controller.current.signal.aborted)setBusy(false)}
 }
 async function advance(){
   if(!job||busy)return
   setBusy(true);setMessage('')
   try{const data:MapJob=await request('/narrative-map/jobs/'+encodeURIComponent(job.id)+'/next',{method:'POST'});if(controller.current.signal.aborted)return;setJob(data);setMessage(`Passage processed: ${data.accepted??0} candidates retained, ${data.discarded??0} discarded.`);await timeline()}
   catch(e){if(!controller.current.signal.aborted)setMessage((e instanceof Error?e.message:'Passage could not be analyzed')+'. Check the local model and resume the scan to check progress.')}
   finally{if(!controller.current.signal.aborted)setBusy(false)}
 }
 async function review(claim:MapClaim,decision:'confirmed_for_research'|'rejected'){
   if(busy)return
   setBusy(true);setMessage('')
   try{await request('/narrative-map/'+encodeURIComponent(claim.id)+'/review',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({decision})});if(controller.current.signal.aborted)return;setClaims(previous=>decision==='rejected'?previous.filter(c=>c.id!==claim.id):previous.map(c=>c.id===claim.id?{...c,status:decision}:c));setMessage('Research review saved. No canon was approved.')}
   catch(e){if(!controller.current.signal.aborted)setMessage(e instanceof Error?e.message:'Review could not be saved')}
   finally{if(!controller.current.signal.aborted)setBusy(false)}
 }
 const current=sources.find(source=>source.id===job?.source_id)
 return <div className="narrative-map">
   <p>Opt in to scan one source at a time with an installed local Ollama model. Each step sends one 1,400-character passage to the local model. Verify your Ollama installation is offline; a local proxy or model could forward text. Nothing becomes canon automatically.</p>
   <button type="button" disabled={busy} onClick={()=>void load()}>{loaded?'Refresh sources and candidates':'Load vault sources and candidates'}</button>
   {loaded&&<>
     <div className="narrative-map-controls"><label>Source through book {cutoff}<select value={sourceId} disabled={busy||!sources.length} onChange={e=>{setSourceId(e.target.value);setJob(null)}}>{!sources.length&&<option value="">No sources at this cutoff</option>}{sources.map(source=><option key={source.id} value={source.id}>Book {source.book} - {source.volume} - {source.title}</option>)}</select></label>
       <label>Installed local model<select value={model} disabled={busy||!models.length} onChange={e=>{setModel(e.target.value);setJob(null)}}>{!models.length&&<option value="">No local model available</option>}{models.map(name=><option key={name} value={name}>{name}</option>)}</select></label></div>
     {modelStatus&&<p role="status">{modelStatus}</p>}
     <div className="grounded-actions"><button type="button" disabled={busy} onClick={recheck}>Recheck local models</button><button type="button" disabled={busy||!sourceId||!models.includes(model)} onClick={()=>void start()}>Start or resume source scan</button></div>
     {job&&<div className="narrative-map-progress"><strong>Current source: Book {job.book} - {current?.volume} - {current?.title||job.source_id}</strong><p>{job.next_offset.toLocaleString()} of {job.length.toLocaleString()} characters scanned - Model: {job.model}</p><progress value={job.next_offset} max={job.length} aria-label="Current source scan progress"/><p>{job.next_offset>=job.length?'This source scan is complete.':'Only the scanned portion of this source has been analyzed.'}</p><button type="button" disabled={busy||job.next_offset>=job.length||!models.includes(job.model)} onClick={()=>void advance()}>{busy?'Analyzing...':'Analyze next passage'}</button></div>}
     <h3>Candidate facts through book {cutoff}</h3><p>Reading order; proposed story time is separate. Candidates require author review and may be inaccurate. This list only reflects passages scanned so far.</p>
     {!claims.length&&<p>No visible candidates yet.</p>}
     {[...claims].filter(c=>c.book<=cutoff).sort((a,b)=>a.book-b.book||a.source_id.localeCompare(b.source_id)||a.start-b.start).map(c=><article className="narrative-map-claim" key={c.id}><strong>Book {c.book} - {c.kind.replace(/_/g,' ')} - {c.status==='proposed'?'Pending review':c.status.replace(/_/g,' ')}</strong><p>{c.subject} {c.predicate} {c.object}</p><p>{c.scope==='character_knowledge'?`Character knowledge: ${c.knower}`:'Narrator perspective'} - Story time: {c.story_time||'unknown'}</p><blockquote>{c.quote}</blockquote><p>Source: {sources.find(source=>source.id===c.source_id)?.title||c.source_id} - Characters {c.start.toLocaleString()}-{c.end.toLocaleString()} - Snapshot {c.snapshot_verified?'verified':'changed or unverified'} - SHA-256 {c.source_hash}</p><div className="grounded-actions"><button type="button" onClick={()=>onOpenSource(c.source_id,c.quote,c.start)}>Open exact source</button>{c.status==='proposed'&&<><button type="button" disabled={busy||!c.snapshot_verified} onClick={()=>void review(c,'confirmed_for_research')}>Confirm for research</button><button type="button" disabled={busy} onClick={()=>void review(c,'rejected')}>Reject</button></>}</div></article>)}
   </>}{message&&<p role="status">{message}</p>}
 </div>
}

export default function SeriesEvidenceSearch({seriesId,bookCount,characters,onOpenSource,onDraftClaim}:Props){
 const [query,setQuery]=useState('')
 const [question,setQuestion]=useState('')
 const [answerQuery,setAnswerQuery]=useState('')
 const [models,setModels]=useState<string[]>([])
 const [model,setModel]=useState('')
 const [modelStatus,setModelStatus]=useState('')
 const [modelRefresh,setModelRefresh]=useState(0)
 const [answerBusy,setAnswerBusy]=useState(false)
 const [recentCards,setRecentCards]=useState<ContextCard[]>([])
 const [reviewBusy,setReviewBusy]=useState(false)
 const [reviewMessage,setReviewMessage]=useState('')
 const cardSequence=useRef(0)

 const askSequence=useRef(0)
 const searchSequence=useRef(0)
 const askAbort=useRef<AbortController|null>(null)
 const searchAbort=useRef<AbortController|null>(null)
 const [answer,setAnswer]=useState<GroundedAnswer|null>(null)
 const [answerError,setAnswerError]=useState('')
 const [answerCutoff,setAnswerCutoff]=useState(1)
 const [answerSearch,setAnswerSearch]=useState('')
 useEffect(()=>{
   let active=true
   setModelStatus('Checking installed local models…')
   void fetch(API+'/series/'+encodeURIComponent(seriesId)+'/local-model-readiness')
     .then(async response=>{if(!response.ok)throw Error();return response.json()})
     .then(data=>{
       if(!active)return
       const local=(Array.isArray(data.models)?data.models:[]).filter((name:unknown):name is string=>
         typeof name==='string'&&!/(?:^|[-:])(cloud|remote)(?:$|[-:])/i.test(name))
       setModels(local);setModel(previous=>local.includes(previous)?previous:local[0]||'')
       setModelStatus(local.length?'':'No installed local Ollama models detected. Start Ollama or install a local model, then recheck.')
     }).catch(()=>{if(active){setModels([]);setModel('');setModelStatus('Could not check local models. Start Ollama and recheck.')}})
   return()=>{active=false}
 },[modelRefresh,seriesId])
 const [maxBook,setMaxBook]=useState(bookCount||1)
 const [searching,setSearching]=useState(false)
 const [result,setResult]=useState<SearchResponse|null>(null)
 const [error,setError]=useState('')
 const [sort,setSort]=useState<'relevance'|'chronological'>('relevance')
 const [focusedBook,setFocusedBook]=useState<number|null>(null)
 const [expanded,setExpanded]=useState(bookCount>12)
 useEffect(()=>{
   cardSequence.current++;setRecentCards([]);setReviewMessage('');
   askSequence.current++;searchSequence.current++
   askAbort.current?.abort();searchAbort.current?.abort()
   setAnswerBusy(false);setSearching(false)
   setMaxBook(Math.max(1,bookCount));setResult(null);setError('')
   setExpanded(bookCount>12);setFocusedBook(null);setAnswer(null);setAnswerError('');setQuestion('');setAnswerQuery('')
 },[seriesId,bookCount])
 useEffect(()=>()=>{askAbort.current?.abort();searchAbort.current?.abort()},[])
 const entries=useMemo(()=>{
   if(!result)return []
   return sort==='chronological'
     ?[...result.results].sort((a,b)=>a.book-b.book||a.excerpt_start-b.excerpt_start)
     :result.results
 },[result,sort])
 async function ask(){
   if(answerBusy||question.trim().length<3||answerQuery.trim().length<2||!models.includes(model))return
   const cutoff=maxBook,terms=answerQuery.trim()
   const token=++askSequence.current
   askAbort.current?.abort()
   const controller=new AbortController()
   askAbort.current=controller
   setAnswerBusy(true);setAnswerError('');setAnswer(null)
   try{
     const response=await fetch(API+'/series/'+encodeURIComponent(seriesId)+'/grounded-answer',{
       method:'POST',headers:{'Content-Type':'application/json'},
       body:JSON.stringify({question:question.trim(),query:terms,as_of_book:cutoff,model}),
       signal:controller.signal
     })
     if(token!==askSequence.current)return
     const data=await response.json()
     if(token!==askSequence.current)return
     if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:'Grounded answer could not complete')
     setAnswer(data as GroundedAnswer);setAnswerCutoff(cutoff);setAnswerSearch(terms)
   }catch(cause){
     if(token===askSequence.current&&!(cause instanceof DOMException&&cause.name==='AbortError'))
       setAnswerError(cause instanceof Error?cause.message:'Grounded answer could not complete')
   }finally{
     if(token===askSequence.current){setAnswerBusy(false);askAbort.current=null}
   }
 }
 async function loadResearchCandidates(){
   const token=++cardSequence.current
   setReviewMessage('');setReviewBusy(true)
   try{
     const params=new URLSearchParams({max_book:String(maxBook),limit:'20'})
     const response=await fetch(API+'/series/'+encodeURIComponent(seriesId)+'/context-proposals?'+params)
     if(token!==cardSequence.current)return
     const payload=await response.json()
     if(!response.ok)throw Error(payload.detail||'Could not load research proposals')
     setRecentCards(Array.isArray(payload.items)?payload.items:[])
   }catch(cause){
     if(token===cardSequence.current)setReviewMessage(String(cause))
   }finally{if(token===cardSequence.current)setReviewBusy(false)}
 }
 async function reviewResearchCandidate(cardId:string,decision:'confirmed_for_research'|'rejected'){
   if(reviewBusy)return
   const token=cardSequence.current
   setReviewBusy(true);setReviewMessage('')
   try{
     const response=await fetch(API+'/series/'+encodeURIComponent(seriesId)+
       '/context-proposals/'+encodeURIComponent(cardId)+'/review',{
       method:'POST',headers:{'Content-Type':'application/json'},
       body:JSON.stringify({decision})
     })
     if(token!==cardSequence.current)return
     const payload=await response.json()
     if(!response.ok)throw Error(payload.detail||'Research review could not be saved')
     setRecentCards(previous=>previous.map(item=>item.id===cardId?
       {...item,review_state:decision}:item))
     setReviewMessage('Research-note decision saved locally. This does not approve story canon.')
   }catch(cause){
     if(token===cardSequence.current)setReviewMessage(String(cause))
   }finally{if(token===cardSequence.current)setReviewBusy(false)}
 }
 async function run(term=query,book:number|null=null){
   const q=term.trim()
   if(q.length<2||searching)return
   const token=++searchSequence.current
   searchAbort.current?.abort()
   const controller=new AbortController()
   searchAbort.current=controller
   setQuery(q);setError('');setSearching(true);setFocusedBook(book)
   try{
     const params=new URLSearchParams({query:q,max_book:String(book||maxBook),limit:'35'})
     if(book!==null)params.set('min_book',String(book))
     const response=await fetch(API+'/series/'+encodeURIComponent(seriesId)+'/evidence-search?'+params,
       {signal:controller.signal})
     if(token!==searchSequence.current)return
     const data=await response.json()
     if(token!==searchSequence.current)return
     if(!response.ok)throw Error(data.detail||'Series search could not complete')
     setResult(data as SearchResponse)
   }catch(cause){
     if(token===searchSequence.current&&!(cause instanceof DOMException&&cause.name==='AbortError')){
       setResult(null);setError(String(cause))
     }
   }finally{
     if(token===searchSequence.current){setSearching(false);searchAbort.current=null}
   }
 }
 return <section className="series-evidence-search" aria-label="Search manuscript evidence across the series">
   <div className="series-evidence-heading">
     <div>
       <span>LOCAL SOURCE INTELLIGENCE · COMPLETE SERIES</span>
       <h2>Find the evidence, across every book.</h2>
       <p>Locate exact passages in all {bookCount} imported volumes. Set your reading position to avoid results from later books.</p>
     </div>
     <button type="button" className="series-evidence-collapse"
       aria-expanded={expanded} onClick={()=>setExpanded(value=>!value)}>
       {expanded?'Hide search':'Open series search'} {expanded?'−':'+'}
     </button>
   </div>
   {expanded&&<div className="series-evidence-body">
     <form onSubmit={event=>{event.preventDefault();void run()}} className="series-evidence-searchbar">
       <label htmlFor="series-evidence-query">Find a character, object, place, or story clue</label>
       <div>
         <input id="series-evidence-query" type="search" value={query}
           placeholder="Search all books…" maxLength={120} disabled={searching}
           onChange={event=>setQuery(event.target.value)}/>
         <button type="submit" disabled={searching||query.trim().length<2}>
           {searching?'Indexing / searching…':'Search sources ↗'}
         </button>
       </div>
     </form>
     <div className="series-evidence-controls">
       <div className="series-evidence-booklimit">
         <label htmlFor="series-evidence-timeline">Only show evidence up to <strong>book {maxBook}</strong></label>
         <input id="series-evidence-timeline" type="range" min={1}
           max={Math.max(1,bookCount)} value={maxBook}
           onChange={event=>{cardSequence.current++;setRecentCards([]);setReviewMessage('');askSequence.current++;searchSequence.current++;askAbort.current?.abort();searchAbort.current?.abort();setAnswer(null);setAnswerBusy(false);setAnswerError('');setSearching(false);setMaxBook(Number(event.target.value));setFocusedBook(null);setResult(null)}}/>
         <div><small>Book 1</small><small>Book {Math.max(1,bookCount)}</small></div>
       </div>
       <div className="series-evidence-suggestions">
         <span>TRY A SEARCH</span>
         {EXAMPLES.map(term=><button key={term} type="button" disabled={searching}
           onClick={()=>void run(term)}>{term}</button>)}
       </div>
     </div>
     <details className="grounded-ask">
       <summary>Build story understanding (local)</summary>
       <NarrativeMap key={seriesId+':'+maxBook} seriesId={seriesId} cutoff={maxBook} models={models} model={model} setModel={setModel} modelStatus={modelStatus} recheck={()=>setModelRefresh(value=>value+1)} onOpenSource={onOpenSource}/>
     </details>
     <details className="grounded-ask">
       <summary>Ask with local contextual reasoning and source review</summary>
       <p>Only when you choose Ask, matching passages are sent to the selected local Ollama model. Passages are sent only to the configured loopback Ollama endpoint, but a local proxy or model could forward them. Verify your installation is offline. Results are read-only and never become canon.</p>
       <p>Answers are limited to retrieved passages through the selected book; missing evidence does not prove an event never happened. Check every answer against its sources.</p>
       <form onSubmit={event=>{event.preventDefault();void ask()}}>
         <label htmlFor="grounded-question">Question</label>
         <input id="grounded-question" value={question} onChange={event=>setQuestion(event.target.value)} disabled={answerBusy} maxLength={1000}/>
         <label htmlFor="grounded-query">Search terms for passages</label>
         <input id="grounded-query" value={answerQuery} onChange={event=>setAnswerQuery(event.target.value)} disabled={answerBusy} maxLength={120}/>
         <p>Book cutoff: <strong>book {maxBook}</strong> (use the reading-position slider above).</p>
         <label htmlFor="grounded-model">Installed local model</label>
         <select id="grounded-model" value={model} onChange={event=>setModel(event.target.value)} disabled={answerBusy||!models.length}>
           {!models.length&&<option value="">No local model available</option>}
           {models.map(name=><option key={name} value={name}>{name}</option>)}
         </select>
         {modelStatus&&<p role="status">{modelStatus}</p>}
         <div className="grounded-actions"><button type="button" disabled={answerBusy} onClick={()=>setModelRefresh(value=>value+1)}>Recheck local models</button>
           <button type="submit" disabled={answerBusy||!model||!question.trim()||answerQuery.trim().length<2}>{answerBusy?'Checking passages…':'Ask from passages'}</button></div>
       </form>
       {answerBusy&&<p role="status">Retrieving passages and asking the local model…</p>}
       {answerError&&<p className="series-evidence-error" role="alert">{answerError}</p>}
       {answer&&<div className="grounded-result" aria-live="polite">
         <h3>Read-only answer for review</h3>
         <p><strong>Status: {answer.abstained?'Abstained':answer.status?answer.status.replace(/_/g,' '):answer.review_only?'Review only':'Not reported'}</strong> · Book cutoff {answerCutoff}</p>
         {answer.status==='provisional'&&<p><strong>Provisional interpretation, NOT confirmed canon.</strong> The local model assembled this response from multiple passages and checked it against the cited excerpts, but only your review can confirm its accuracy.</p>}
         {answer.answer&&<p>{answer.answer}</p>}
         {answer.uncertainty&&<p><strong>Model uncertainty:</strong> {answer.uncertainty}</p>}
         {answer.reason_detail&&<p><strong>Verification detail:</strong> {answer.reason_detail}</p>}
         {answer.local_verifier&&<p><strong>Local self-check:</strong> {answer.local_verifier.replace(/_/g,' ')} (not independent expert verification)</p>}
         {answer.retrieval_guidance==='author_feedback_hypotheses_for_search_only'&&<p>Earlier author corrections helped choose search terms. They were not treated as manuscript evidence or preapproved facts.</p>}
         {answer.context_cards?.length? <p>{answer.context_cards.length} contextual interpretation saved locally as pending author review. These proposals are never approved as canon automatically.</p>:null}
         {answer.reasons?.length? <p>Reasons: {answer.reasons.join('; ')}</p>:null}
         {answer.safety_reasons?.length? <p>Safety reasons: {answer.safety_reasons.join('; ')}</p>:null}
         {answer.safety_flags&&<p>Safety flags: {Array.isArray(answer.safety_flags)?answer.safety_flags.join('; ')||'None reported':Object.entries(answer.safety_flags).map(([key,value])=>key.replace(/_/g,' ')+': '+String(value)).join('; ')||'None reported'}</p>}
         {answer.citations?.length?<><h4>Cited primary-source passages</h4>
           <div className="grounded-citations">{answer.citations.map((citation,index)=><article key={'cited-'+index}>
             <strong>{citation.book!=null?'Book '+citation.book:'Source'}</strong>
             {citation.reading_period&&<p>Reading period: {citation.reading_period}</p>}
             {citation.quote&&<blockquote>{citation.quote}</blockquote>}
             <p><small>Exact source span; quotation presence does not prove this passage supports every claim.</small></p>
             {citation.source_id&&typeof citation.start==='number'&&<button type="button" onClick={()=>onOpenSource(citation.source_id!,answerSearch,citation.start!)}>Open cited source</button>}
           </article>)}</div>
         </>:null}
         <h4>Retrieved passages for review</h4>
         {answer.citations?.length?<p>Model cited {answer.citations.length} quotation(s). Exact matches do not prove they support its claims.</p>:null}
         {!(answer.passages?.length?answer.passages:(answer.citations||answer.evidence||[])).length&&<p>No citations returned. Do not treat this as established evidence.</p>}
         <div className="grounded-citations">{(answer.passages?.length?answer.passages:(answer.citations||answer.evidence||[])).map((citation,index)=><article key={(citation.source_id||'source')+'-'+index}>
           <strong>{citation.book!=null?'Book '+citation.book:'Book not reported'}{citation.book!=null?' · '+(citation.book===answerCutoff?'Current cutoff book':citation.book<answerCutoff?'Older book':'Beyond cutoff'):''}</strong>
           <p>{citation.volume||citation.source_title||citation.source_id||'Source not reported'}{citation.source_id&&citation.source_title?' · '+citation.source_id:''}</p>
           {(citation.excerpt||citation.quote)&&<blockquote>{citation.excerpt||citation.quote}</blockquote>}
           {citation.source_id&&typeof (citation.start??citation.excerpt_start??citation.quote_start)==='number'&&<button type="button" onClick={()=>onOpenSource(citation.source_id!,answerSearch,(citation.start??citation.excerpt_start??citation.quote_start)!)}>Open original source</button>}
         </article>)}</div>
         <p>Semantic entailment: {answer.semantic_entailment||'unverified'}. Canon approval: {answer.auto_approval_allowed===false?'not permitted':'not established'}.</p>
         {answer.disclaimer&&<p>{answer.disclaimer}</p>}
         <p>Review the original sources. This answer creates no canon claims.</p>
       </div>}
     </details>
     <details className="grounded-ask">
       <summary>Review retained character and world context</summary>
       <p>These are source-linked, model-proposed interpretations. None is approved canon. You can confirm a note as research context only after checking the cited sources, or reject it.</p>
       <button type="button" disabled={reviewBusy} onClick={()=>void loadResearchCandidates()}>
         {reviewBusy?'Checking local notes…':'Load recent contextual proposals'}
       </button>
       {reviewMessage&&<p role="status">{reviewMessage}</p>}
       {recentCards.map(card=><article className="grounded-result" key={card.id}>
         <h4>{card.facet.replace(/_/g,' ')} · As of Book {card.as_of_book}</h4>
         <p><strong>Question:</strong> {card.question}</p>
         <p>{card.interpretation}</p>
         <p>Review state: {card.review_state.replace(/_/g,' ')}. These are not independently certified facts.</p>
         <div className="grounded-actions">
           {card.citations.map((c,index)=>c.source_id&&typeof c.start==='number'?
             <button key={index} type="button" onClick={()=>onOpenSource(c.source_id!,card.question,c.start!)}>
               Check source · Book {c.book??'?'}
             </button>:null)}
         </div>
         {card.review_state==='pending_author_review'&&<div className="grounded-actions">
           <button type="button" disabled={reviewBusy}
             onClick={()=>void reviewResearchCandidate(card.id,'confirmed_for_research')}>
             Confirm as research context — not canon
           </button>
           <button type="button" disabled={reviewBusy}
             onClick={()=>void reviewResearchCandidate(card.id,'rejected')}>Reject interpretation</button>
         </div>}
       </article>)}
     </details>
     <SeriesCharacterEvidenceMap seriesId={seriesId} maxBook={maxBook}
       characters={characters.filter(entity=>entity.kind==='character')}
       onExploreBook={(book,name)=>{void run(name,book)}}/>
     {focusedBook!==null&&<div className="series-evidence-book-focus">
       <span>Showing cited passages from Book {focusedBook} only</span>
       <button type="button" onClick={()=>{void run(query,null)}}>Return to full reading range ↺</button>
     </div>}
     {error&&<p className="series-evidence-error" role="alert">{error}</p>}
     {searching&&<p className="series-evidence-loading" role="status">Checking the private manuscript index. Large series may take longer to index the first time.</p>}
     {result&&!searching&&<div className="series-evidence-results">
       <div className="series-evidence-resultbar">
         <div><strong>{result.total_hits.toLocaleString()} matching text windows</strong>
           <small>across {result.sources} source files, books {result.min_book}–{result.max_book}</small></div>
         <label>Order <select value={sort} onChange={event=>setSort(event.target.value as typeof sort)}>
           <option value="relevance">Most relevant</option>
           <option value="chronological">Book order</option>
         </select></label>
       </div>
       {!entries.length&&<p className="series-evidence-empty">No matching source passages in this book range. That does not establish that the story event never happened.</p>}
       <div className="series-evidence-grid">{entries.map((entry,index)=>
         <article key={entry.source_id+'-'+entry.excerpt_start+'-'+index}>
           <div className="series-evidence-cardhead">
             <span>BOOK {String(entry.book).padStart(2,'0')}</span>
             <strong>{entry.volume}</strong>
           </div>
           <p>{entry.excerpt}</p>
           <button type="button" onClick={()=>onOpenSource(entry.source_id,query,entry.excerpt_start)}>
             Open original source · position {entry.excerpt_start.toLocaleString()} ↗
           </button>
           <button type="button" className="series-evidence-stage-claim" onClick={()=>onDraftClaim(entry)}>
             Draft a source-backed claim from this passage (author review required)
           </button>
         </article>)}</div>
       {result.total_hits>result.results.length&&<p className="series-evidence-count">
         Displaying the first {result.results.length} ranked text windows. Refine your term or book range for more precise sources.</p>}
       <p className="series-evidence-disclaimer">{result.disclaimer} Author approval is required before any claim becomes canon.</p>
     </div>}
   </div>}
 </section>
}
