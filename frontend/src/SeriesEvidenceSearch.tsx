import { useEffect, useMemo, useState } from 'react'
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
type Citation={book?:number;volume?:string;source_id?:string;source_title?:string;excerpt?:string;excerpt_start?:number;quote?:string;quote_start?:number}
type GroundedAnswer={answer?:string;status?:string;abstained?:boolean;review_only?:boolean;reasons?:string[];safety_reasons?:string[];safety_flags?:string[]|Record<string,boolean|string>;citations?:Citation[];evidence?:Citation[];disclaimer?:string}
const API='http://127.0.0.1:8000/api'

export default function SeriesEvidenceSearch({seriesId,bookCount,characters,onOpenSource,onDraftClaim}:Props){
 const [query,setQuery]=useState('')
 const [question,setQuestion]=useState('')
 const [answerQuery,setAnswerQuery]=useState('')
 const [models,setModels]=useState<string[]>([])
 const [model,setModel]=useState('')
 const [modelStatus,setModelStatus]=useState('')
 const [modelRefresh,setModelRefresh]=useState(0)
 const [answerBusy,setAnswerBusy]=useState(false)
 const [answer,setAnswer]=useState<GroundedAnswer|null>(null)
 const [answerError,setAnswerError]=useState('')
 const [answerCutoff,setAnswerCutoff]=useState(1)
 const [answerSearch,setAnswerSearch]=useState('')
 useEffect(()=>{
   let active=true
   setModelStatus('Checking installed local models…')
   void fetch(API+'/models',{method:'POST',headers:{'Content-Type':'application/json'},
     body:JSON.stringify({provider:'ollama',base_url:'http://127.0.0.1:11434',model:''})})
     .then(async response=>{if(!response.ok)throw Error();return response.json()})
     .then(data=>{
       if(!active)return
       const local=(Array.isArray(data.models)?data.models:[]).filter((name:unknown):name is string=>
         typeof name==='string'&&!/(?:^|[-:])(cloud|remote)(?:$|[-:])/i.test(name))
       setModels(local);setModel(previous=>local.includes(previous)?previous:local[0]||'')
       setModelStatus(local.length?'':'No installed local Ollama models detected. Start Ollama or install a local model, then recheck.')
     }).catch(()=>{if(active){setModels([]);setModel('');setModelStatus('Could not check local models. Start Ollama and recheck.')}})
   return()=>{active=false}
 },[modelRefresh])
 const [maxBook,setMaxBook]=useState(bookCount||1)
 const [searching,setSearching]=useState(false)
 const [result,setResult]=useState<SearchResponse|null>(null)
 const [error,setError]=useState('')
 const [sort,setSort]=useState<'relevance'|'chronological'>('relevance')
 const [focusedBook,setFocusedBook]=useState<number|null>(null)
 const [expanded,setExpanded]=useState(bookCount>12)
 useEffect(()=>{
   setMaxBook(Math.max(1,bookCount));setResult(null);setError('')
   setExpanded(bookCount>12);setFocusedBook(null);setAnswer(null);setAnswerError('');setQuestion('');setAnswerQuery('')
 },[seriesId,bookCount])
 const entries=useMemo(()=>{
   if(!result)return []
   return sort==='chronological'
     ?[...result.results].sort((a,b)=>a.book-b.book||a.excerpt_start-b.excerpt_start)
     :result.results
 },[result,sort])
 async function ask(){
   if(answerBusy||!question.trim()||answerQuery.trim().length<2||!models.includes(model))return
   const cutoff=maxBook,terms=answerQuery.trim()
   setAnswerBusy(true);setAnswerError('');setAnswer(null)
   try{
     const response=await fetch(API+'/series/'+encodeURIComponent(seriesId)+'/grounded-answer',{
       method:'POST',headers:{'Content-Type':'application/json'},
       body:JSON.stringify({question:question.trim(),query:terms,max_book:cutoff,model})
     })
     const data=await response.json()
     if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:'Grounded answer could not complete')
     setAnswer(data as GroundedAnswer);setAnswerCutoff(cutoff);setAnswerSearch(terms)
   }catch(cause){setAnswerError(cause instanceof Error?cause.message:'Grounded answer could not complete')}
   finally{setAnswerBusy(false)}
 }
 async function run(term=query,book:number|null=null){
   const q=term.trim()
   if(q.length<2||searching)return
   setQuery(q);setError('');setSearching(true);setFocusedBook(book)
   try{
     const params=new URLSearchParams({query:q,max_book:String(book||maxBook),limit:'35'})
   if(book!==null)params.set('min_book',String(book))
     const response=await fetch(
       'http://127.0.0.1:8000/api/series/'+encodeURIComponent(seriesId)+'/evidence-search?'+params
     )
     const data=await response.json()
     if(!response.ok)throw Error(data.detail||'Series search could not complete')
     setResult(data as SearchResponse)
   }catch(cause){setResult(null);setError(String(cause))}
   finally{setSearching(false)}
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
           onChange={event=>{setMaxBook(Number(event.target.value));setFocusedBook(null);setResult(null)}}/>
         <div><small>Book 1</small><small>Book {Math.max(1,bookCount)}</small></div>
       </div>
       <div className="series-evidence-suggestions">
         <span>TRY A SEARCH</span>
         {EXAMPLES.map(term=><button key={term} type="button" disabled={searching}
           onClick={()=>void run(term)}>{term}</button>)}
       </div>
     </div>
     <details className="grounded-ask">
       <summary>Ask from passages (local model)</summary>
       <p>Only when you choose Ask, matching passages are sent to the selected local Ollama model. No hosted AI is used. Results are read-only and never become canon.</p>
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
         {answer.answer&&<p>{answer.answer}</p>}
         {answer.reasons?.length? <p>Reasons: {answer.reasons.join('; ')}</p>:null}
         {answer.safety_reasons?.length? <p>Safety reasons: {answer.safety_reasons.join('; ')}</p>:null}
         {answer.safety_flags&&<p>Safety flags: {Array.isArray(answer.safety_flags)?answer.safety_flags.join('; ')||'None reported':Object.entries(answer.safety_flags).map(([key,value])=>key.replace(/_/g,' ')+': '+String(value)).join('; ')||'None reported'}</p>}
         <h4>Passages returned for review</h4>
         {!(answer.citations||answer.evidence||[]).length&&<p>No citations returned. Do not treat this as established evidence.</p>}
         <div className="grounded-citations">{(answer.citations||answer.evidence||[]).map((citation,index)=><article key={(citation.source_id||'source')+'-'+index}>
           <strong>{citation.book!=null?'Book '+citation.book:'Book not reported'}{citation.book!=null?' · '+(citation.book===answerCutoff?'Current cutoff book':citation.book<answerCutoff?'Older book':'Beyond cutoff'):''}</strong>
           <p>{citation.volume||citation.source_title||citation.source_id||'Source not reported'}{citation.source_id&&citation.source_title?' · '+citation.source_id:''}</p>
           {(citation.excerpt||citation.quote)&&<blockquote>{citation.excerpt||citation.quote}</blockquote>}
           {citation.source_id&&typeof (citation.excerpt_start??citation.quote_start)==='number'&&<button type="button" onClick={()=>onOpenSource(citation.source_id!,answerSearch,(citation.excerpt_start??citation.quote_start)!)}>Open original source</button>}
         </article>)}</div>
         {answer.disclaimer&&<p>{answer.disclaimer}</p>}
         <p>Review the original sources. This answer creates no canon claims.</p>
       </div>}
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
