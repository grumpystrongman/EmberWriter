import {useEffect,useMemo,useState} from 'react'
import ReviewQueue from './ReviewQueue'
import type {QueueRow} from './ReviewQueue'
import './story-event-review-board.css'

type Review={
 id:string;book:number;source_id:string;quote:string;quote_start:number;
 status:'proposed'|'approved'|'rejected';title:string;
 event_kind:string;timeline_class:string;note:string;
 source_verified:boolean;is_author_approved:boolean
}
type Report={events:Review[];total_visible:number}
const BASE='http://127.0.0.1:8000/api/series'
const kinds=[
 {value:'observed_event',label:'Confirmed scene event'},
 {value:'character_memory',label:'Character recollection'},
 {value:'dream',label:'Dream or vision'},
 {value:'rumor',label:'Rumor or reported claim'},
 {value:'hypothetical',label:'Hypothetical'},
]
const times=[
 {value:'time_unknown',label:'Story time not confirmed'},
 {value:'book_sequence',label:'Occurs in this book’s sequence'},
 {value:'flashback',label:'Flashback to earlier story time'},
 {value:'flashforward',label:'Flashforward to later story time'},
]
export default function StoryEventReviewBoard({seriesId,revision=0}:{seriesId:string;revision?:number}){
 const [events,setEvents]=useState<Review[]>([])
 const [active,setActive]=useState<string|null>(null)
 const [busy,setBusy]=useState(false)
 const [error,setError]=useState('')
 const [notice,setNotice]=useState('')
 const [refresh,setRefresh]=useState(0)
 const [eventTitle,setEventTitle]=useState('')
 const [kind,setKind]=useState('observed_event')
 const [timeline,setTimeline]=useState('time_unknown')
 const [note,setNote]=useState('')
 useEffect(()=>{
  const controller=new AbortController()
  void fetch(`${BASE}/${encodeURIComponent(seriesId)}/event-reviews`,{signal:controller.signal})
   .then(async r=>{if(!r.ok)throw Error('Could not load event reviews');return r.json() as Promise<Report>})
   .then(data=>{if(!controller.signal.aborted)setEvents(data.events)})
   .catch(cause=>{if(!controller.signal.aborted)setError(String(cause))})
  return()=>controller.abort()
 },[seriesId,revision,refresh])
 const rows=useMemo<QueueRow[]>(()=>events.map(item=>({
  key:item.id,title:'Book '+item.book+' · '+(item.title||'Event interpretation needed'),
  subtitle:item.source_verified?'Source verified':'Source fingerprint changed',
  preview:item.quote,meta:'At '+item.quote_start.toLocaleString(),status:item.status,
 })),[events])
 function focus(item:Review){
  setActive(item.id)
  setEventTitle(item.title||'')
  setKind(item.event_kind==='uncertain'?'observed_event':item.event_kind)
  setTimeline(item.timeline_class||'time_unknown')
  setNote(item.note||'')
  setError('');setNotice('')
 }
 async function decide(item:Review,decision:'approved'|'rejected'){
  if(busy)return
  setBusy(true);setError('');setNotice('')
  try{
   const response=await fetch(
    `${BASE}/${encodeURIComponent(seriesId)}/event-reviews/${item.id}/decision`,{
     method:'POST',headers:{'Content-Type':'application/json'},
     body:JSON.stringify({decision,title:eventTitle,event_kind:kind,timeline_class:timeline,note}),
    })
   const result=await response.json()
   if(!response.ok)throw Error(result.detail||'Author review was not saved')
   setNotice(decision==='approved'?'Event saved as an author interpretation, not AI-inferred canon.':'Lead rejected.')
   setRefresh(n=>n+1)
  }catch(cause){setError(String(cause))}
  finally{setBusy(false)}
 }
 function detail(row:QueueRow){
  const item=events.find(x=>x.id===row.key)
  if(!item)return null
  return <div className="review-queue-detail-fields">
   <h4>Book {item.book} · {item.title||'Review original context'}</h4>
   <blockquote>{item.quote||'SOURCE HAS CHANGED — REVIEW BLOCKED'}</blockquote>
   <small>Exact source offset: {item.quote_start.toLocaleString()} · {item.source_verified?'Verified':'Invalid fingerprint'}</small>
   <label>Author-confirmed event title
    <input key={'title:'+item.id} defaultValue={item.title} maxLength={160}
     onChange={e=>setEventTitle(e.target.value)} placeholder="What actually happened?"/>
   </label>
   <label>Meaning of this passage
    <select key={'kind:'+item.id} defaultValue={item.event_kind==='uncertain'?'observed_event':item.event_kind}
     onChange={e=>setKind(e.target.value)}>
     {kinds.map(option=><option key={option.value} value={option.value}>{option.label}</option>)}
    </select>
   </label>
   <label>Position in story time
    <select key={'time:'+item.id} defaultValue={item.timeline_class}
     onChange={e=>setTimeline(e.target.value)}>
     {times.map(option=><option key={option.value} value={option.value}>{option.label}</option>)}
    </select>
   </label>
   <label>Reason or caveat
    <textarea key={'note:'+item.id} defaultValue={item.note} rows={3} maxLength={1000}
     onChange={e=>setNote(e.target.value)}/>
   </label>
   <div className="review-queue-actions">
    <button disabled={busy||!item.source_verified||!(eventTitle||item.title).trim()}
     onClick={()=>void decide(item,'approved')}>Approve event</button>
    <button disabled={busy||!item.source_verified}
     onClick={()=>void decide(item,'rejected')}>Reject event</button>
   </div>
  </div>
 }
 return <section className="story-event-review-board" aria-label="Author event review ledger">
  {error&&<p role="alert">{error}</p>}
  {notice&&<p role="status">{notice}</p>}
  <ReviewQueue title="Author decision queue"
   description="Every event and story-time interpretation requires direct author review. The original source evidence remains attached."
   rows={rows} detail={detail} emptyText="No staged events. Select a source lead and stage it to begin."
   onSelectionChange={key=>{
    const item=events.find(x=>x.id===key)
    if(item)focus(item)
   }}
   footer={<span>{events.filter(x=>x.status==='proposed').length} awaiting review · {events.filter(x=>x.is_author_approved).length} author-approved · {events.filter(x=>x.status==='rejected').length} rejected</span>}/>
 </section>
}
