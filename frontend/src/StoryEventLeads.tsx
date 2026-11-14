import {useEffect,useMemo,useState} from 'react'
import ReviewQueue from './ReviewQueue'
import type {QueueRow} from './ReviewQueue'
import StoryEventReviewBoard from './StoryEventReviewBoard'
import './story-dialogue-review.css'

type Lead={source_id:string;book:number;source_title:string;quote:string;
 quote_start:number;quote_end:number;entities_mentioned:string[];
 literal_cues:string[];section_label:string|null;status:string}
type Report={total:number;scanned_sources:number;leads:Lead[];truncated:boolean;caveat:string}
const BASE='http://127.0.0.1:8000/api/series'
const keyOf=(lead:Lead)=>lead.source_id+':'+lead.quote_start

export default function StoryEventLeads({seriesId,book,onInspectSource}:{
 seriesId:string;book:number;onInspectSource:(sourceId:string)=>void
}){
 const [scope,setScope]=useState<'book'|'all'>('book')
 const [report,setReport]=useState<Report|null>(null)
 const [error,setError]=useState('')
 const [busy,setBusy]=useState(false)
 const [offset,setOffset]=useState(0)
 const [contextKey,setContextKey]=useState('')
 const [context,setContext]=useState('')
 const [contextError,setContextError]=useState('')
 const [reviewRevision,setReviewRevision]=useState(0)
 const [stageBusy,setStageBusy]=useState('')
 const [stageNotice,setStageNotice]=useState('')
 const [reviewOpen,setReviewOpen]=useState(false)
 useEffect(()=>setOffset(0),[seriesId,book,scope])
 useEffect(()=>{
  const controller=new AbortController()
  setBusy(true);setError('');setReport(null)
  const params=new URLSearchParams({limit:'80',offset:String(offset)})
  if(scope==='book')params.set('book',String(book))
  void fetch(`${BASE}/${encodeURIComponent(seriesId)}/event-leads?${params}`,{signal:controller.signal})
   .then(async response=>{if(!response.ok)throw Error('Could not scan source event leads');return response.json() as Promise<Report>})
   .then(value=>{if(!controller.signal.aborted)setReport(value)})
   .catch(cause=>{if(!controller.signal.aborted)setError(String(cause))})
   .finally(()=>{if(!controller.signal.aborted)setBusy(false)})
  return()=>controller.abort()
 },[seriesId,book,scope,offset])
 const rows=useMemo<QueueRow[]>(()=>report?.leads.map(lead=>({
  key:keyOf(lead),title:'Book '+lead.book+' · '+(lead.section_label||lead.source_title),
  subtitle:lead.entities_mentioned.join(', ')||'Named event cue',
  preview:lead.quote,
  status:'unreviewed',
  meta:lead.literal_cues.slice(0,2).join(', '),
  searchText:lead.literal_cues.join(' '),
 }))||[],[report])
 async function stage(lead:Lead){
  setStageBusy(keyOf(lead));setStageNotice('')
  try{
   const r=await fetch(`${BASE}/${encodeURIComponent(seriesId)}/event-reviews`,{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({source_id:lead.source_id,quote_start:lead.quote_start,quote_end:lead.quote_end}),
   })
   const payload=await r.json()
   if(!r.ok)throw Error(payload.detail||'Could not stage source lead')
   setStageNotice('Quote staged for explicit author interpretation. Not approved canon.')
   setReviewRevision(x=>x+1);setReviewOpen(true)
  }catch(cause){setStageNotice(String(cause))}
  finally{setStageBusy('')}
 }
 async function inspect(lead:Lead){
  const key=keyOf(lead)
  if(contextKey===key&&context){setContextKey('');setContext('');return}
  setContextKey(key);setContext('');setContextError('')
  try{
   const path=`${BASE}/${encodeURIComponent(seriesId)}/sources/${encodeURIComponent(lead.source_id)}/excerpt?position=${lead.quote_start}&limit=1500`
   const response=await fetch(path)
   if(!response.ok)throw Error('Unable to read original source context')
   const result=await response.json() as {found:boolean;excerpt:string}
   if(!result.found||!result.excerpt.includes(lead.quote))throw Error('Exact source quote could not be verified')
   setContext(result.excerpt)
  }catch(cause){setContextError(String(cause))}
 }
 function detail(row:QueueRow){
  const lead=report?.leads.find(x=>keyOf(x)===row.key)
  if(!lead)return null
  return <div className="review-queue-detail-fields">
   <h4>Book {lead.book} · {lead.section_label||lead.source_title}</h4>
   <blockquote>{lead.quote}</blockquote>
   <small>Exact source position {lead.quote_start.toLocaleString()}–{lead.quote_end.toLocaleString()}</small>
   <p>Names: {lead.entities_mentioned.join(', ')||'None identified'} · literal cues: {lead.literal_cues.join(', ')}</p>
   <div className="review-queue-actions">
    <button onClick={()=>void inspect(lead)}>Read surrounding passage</button>
    <button onClick={()=>onInspectSource(lead.source_id)}>Open original source</button>
    <button disabled={!!stageBusy} onClick={()=>void stage(lead)}>
     {stageBusy===keyOf(lead)?'Staging…':'Stage for author review'}
    </button>
   </div>
   {contextKey===keyOf(lead)&&<>
    {contextError&&<p role="alert">{contextError}</p>}
    {!context&&!contextError&&<p role="status">Reading original source…</p>}
    {context&&<blockquote aria-label="Verified original source context">{context}</blockquote>}
   </>}
  </div>
 }
 return <section className="story-event-leads" aria-label="Unreviewed source event leads">
  {error&&<p role="alert">{error}</p>}
  {stageNotice&&<p role="status">{stageNotice}</p>}
  <ReviewQueue title="Event and chronology leads"
   description="Exact source evidence, presented as a triage queue. A temporal phrase is not a proven event."
   rows={rows} detail={detail} loading={busy} emptyText="No matching literal event clues were found."
   pageLabel={'Source page '+(Math.floor(offset/80)+1)}
   toolbar={<label>Scope
    <select value={scope} onChange={e=>setScope(e.target.value as 'book'|'all')}>
     <option value="book">Book {book}</option>
     <option value="all">All books</option>
    </select>
   </label>}
   footer={<>
    <button disabled={offset===0} onClick={()=>setOffset(x=>Math.max(0,x-80))}>Previous</button>
    <span>{report?.total?offset+1:0}–{Math.min(offset+80,report?.total||0)} of {report?.total||0} leads · {report?.scanned_sources||0} source(s)</span>
    <button disabled={!report||offset+80>=report.total} onClick={()=>setOffset(x=>x+80)}>Next</button>
    {report?.truncated&&<span>Scan safety limit reached</span>}
   </>}/>
  <details className="review-queue-secondary" open={reviewOpen}
   onToggle={e=>setReviewOpen(e.currentTarget.open)}>
   <summary>Author decision ledger · verify or reject staged events</summary>
   {reviewOpen&&<StoryEventReviewBoard seriesId={seriesId} revision={reviewRevision}/>}
  </details>
  {report&&<p className="review-queue-disclaimer">{report.caveat}</p>}
 </section>
}
