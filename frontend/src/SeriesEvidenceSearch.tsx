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

export default function SeriesEvidenceSearch({seriesId,bookCount,characters,onOpenSource,onDraftClaim}:Props){
 const [query,setQuery]=useState('')
 const [maxBook,setMaxBook]=useState(bookCount||1)
 const [searching,setSearching]=useState(false)
 const [result,setResult]=useState<SearchResponse|null>(null)
 const [error,setError]=useState('')
 const [sort,setSort]=useState<'relevance'|'chronological'>('relevance')
 const [focusedBook,setFocusedBook]=useState<number|null>(null)
 const [expanded,setExpanded]=useState(bookCount>12)
 useEffect(()=>{
   setMaxBook(Math.max(1,bookCount));setResult(null);setError('')
   setExpanded(bookCount>12);setFocusedBook(null)
 },[seriesId,bookCount])
 const entries=useMemo(()=>{
   if(!result)return []
   return sort==='chronological'
     ?[...result.results].sort((a,b)=>a.book-b.book||a.excerpt_start-b.excerpt_start)
     :result.results
 },[result,sort])
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
