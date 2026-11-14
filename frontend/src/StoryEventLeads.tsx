import {useEffect,useState} from 'react'
import './story-event-leads.css'
import StoryEventReviewBoard from './StoryEventReviewBoard'

type Lead={
 source_id:string;book:number;source_title:string;quote:string;
 quote_start:number;quote_end:number;entities_mentioned:string[];
 literal_cues:string[];section_label:string|null;status:string
}
type Report={total:number;scanned_sources:number;leads:Lead[];truncated:boolean;
 caveat:string}
const BASE='http://127.0.0.1:8000/api/series'

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
 async function stage(lead:Lead){
  setStageBusy(lead.source_id+':'+lead.quote_start);setStageNotice('')
  try{
   const r=await fetch(`${BASE}/${encodeURIComponent(seriesId)}/event-reviews`,{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({source_id:lead.source_id,quote_start:lead.quote_start,quote_end:lead.quote_end}),
   })
   const payload=await r.json()
   if(!r.ok)throw Error(payload.detail||'Could not stage this exact source lead')
   setStageNotice('Exact quote staged for author review. It is not approved canon.')
   setReviewRevision(x=>x+1)
  }catch(cause){setStageNotice(String(cause))}
  finally{setStageBusy('')}
 }
 async function inspect(lead:Lead){
  const key=lead.source_id+':'+lead.quote_start
  if(contextKey===key){setContextKey('');setContext('');return}
  setContextKey(key);setContext('');setContextError('')
  try{
   const path=`${BASE}/${encodeURIComponent(seriesId)}/sources/${encodeURIComponent(lead.source_id)}/excerpt?position=${lead.quote_start}&limit=1500`
   const response=await fetch(path)
   if(!response.ok)throw Error('Unable to read original source context')
   const result=await response.json() as {found:boolean;excerpt:string}
   if(!result.found||!result.excerpt.includes(lead.quote))throw Error('Quote could not be verified in the excerpt')
   setContext(result.excerpt)
  }catch(cause){setContextError(String(cause))}
 }
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
 return <section className="story-event-leads" aria-label="Unreviewed source event leads">
  <div><small>CHUNK 4 / EVIDENCE-ANCHORED EVENT DISCOVERY</small>
   <h4>Events and turning points worth examining</h4>
   <p>Literal scene and time-change language linked to exact source passages. These are leads, not claims about what really happened in the story.</p></div>
  <div className="story-event-scope" role="group" aria-label="Event lead scan scope">
   <button type="button" aria-pressed={scope==='book'} onClick={()=>setScope('book')}>Book {book}</button>
   <button type="button" aria-pressed={scope==='all'} onClick={()=>setScope('all')}>All books</button>
  </div>
  {busy&&<p role="status">Checking source quotes and navigation positions…</p>}
  {error&&<p role="alert">{error}</p>}
  {report&&<>
   <p className="story-event-summary">{report.total} literal leads from {report.scanned_sources} source(s){report.truncated?' · scan limit reached':''}. None are approved canon.</p>
   <div className="story-event-items">{report.leads.map(lead=><article key={lead.source_id+':'+lead.quote_start}>
    <div><strong>Book {lead.book} · {lead.section_label||lead.source_title}</strong>
     <small>{lead.entities_mentioned.join(', ')} · cues: {lead.literal_cues.join(', ')}</small></div>
    <blockquote>{lead.quote}</blockquote>
    <small>Exact source characters {lead.quote_start.toLocaleString()}–{lead.quote_end.toLocaleString()}</small>
    <div className="story-event-scope">
     <button type="button" onClick={()=>void inspect(lead)}>Read exact surrounding context</button>
     <button type="button" onClick={()=>onInspectSource(lead.source_id)}>Open original source</button>
     <button type="button" disabled={!!stageBusy} onClick={()=>void stage(lead)}>
      {stageBusy===lead.source_id+':'+lead.quote_start?'Staging…':'Stage exact quote for author review'}
     </button>
    </div>
    {contextKey===lead.source_id+':'+lead.quote_start&&<div className="story-event-context" role="region" aria-label="Original source context">
      {contextError&&<p role="alert">{contextError}</p>}
      {!context&&!contextError&&<p>Loading exact source context…</p>}
      {context&&<blockquote>{context}</blockquote>}
     </div>}
   </article>)}</div>
   <div className="story-event-scope" aria-label="Event leads page navigation">
    <button type="button" disabled={offset===0} onClick={()=>setOffset(v=>Math.max(0,v-80))}>Previous leads</button>
    <span>Showing {report.total?Math.min(offset+1,report.total):0}–{Math.min(offset+80,report.total)} of {report.total}</span>
    <button type="button" disabled={offset+80>=report.total} onClick={()=>setOffset(v=>v+80)}>Next leads</button>
   </div>
   {!report.leads.length&&<p>No literal event leads for this selection. This does not mean no events occurred.</p>}
   {stageNotice&&<p role="status">{stageNotice}</p>}
   <StoryEventReviewBoard seriesId={seriesId} revision={reviewRevision}/>
   <p className="story-event-caveat">{report.caveat}</p>
  </>}
 </section>
}
