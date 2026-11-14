import {useEffect,useState} from 'react'
import './story-event-review-board.css'

type Review = {
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
export default function StoryEventReviewBoard({seriesId,revision=0}:{
 seriesId:string;revision?:number
}){
 const [events,setEvents]=useState<Review[]>([])
 const [active,setActive]=useState<string|null>(null)
 const [busy,setBusy]=useState(false)
 const [error,setError]=useState('')
 const [notice,setNotice]=useState('')
 const [refresh,setRefresh]=useState(0)
 const [title,setTitle]=useState('')
 const [kind,setKind]=useState('observed_event')
 const [time,setTime]=useState('time_unknown')
 const [note,setNote]=useState('')
 const selected=events.find(item=>item.id===active)||null
 useEffect(()=>{
  const controller=new AbortController()
  void fetch(`${BASE}/${encodeURIComponent(seriesId)}/event-reviews`,{signal:controller.signal})
   .then(async r=>{if(!r.ok)throw Error('Could not load author event reviews');return r.json() as Promise<Report>})
   .then(data=>{if(!controller.signal.aborted)setEvents(data.events)})
   .catch(cause=>{if(!controller.signal.aborted)setError(String(cause))})
  return()=>controller.abort()
 },[seriesId,revision,refresh])
 function focus(item:Review){
  setActive(item.id)
  setTitle(item.title||'')
  setKind(item.event_kind==='uncertain'?'observed_event':item.event_kind)
  setTime(item.timeline_class||'time_unknown')
  setNote(item.note||'')
  setError('');setNotice('')
 }
 async function decide(decision:'approved'|'rejected'){
  if(!selected||busy)return
  setBusy(true);setError('');setNotice('')
  try{
   const response=await fetch(
    `${BASE}/${encodeURIComponent(seriesId)}/event-reviews/${selected.id}/decision`,{
     method:'POST',headers:{'Content-Type':'application/json'},
     body:JSON.stringify({decision,title,event_kind:kind,timeline_class:time,note}),
    })
   const result=await response.json()
   if(!response.ok)throw Error(result.detail||'Author review was not saved')
   setNotice(decision==='approved'?'Reviewed event saved. This is an author interpretation, not inferred by AI.':'Lead rejected as an event.')
   setRefresh(n=>n+1)
  }catch(cause){setError(String(cause))}
  finally{setBusy(false)}
 }
 return <section className="story-event-review-board" aria-label="Author event review ledger">
  <div><strong>Author-reviewed narrative events</strong>
   <p>Only events you explicitly interpret and approve appear as confirmed event records. A citation alone is not proof of an event or its chronology.</p></div>
  <div className="story-event-review-stats">
   <span>{events.filter(item=>item.is_author_approved).length} author-approved</span>
   <span>{events.filter(item=>item.status==='proposed').length} awaiting review</span>
   <span>{events.filter(item=>item.status==='rejected').length} rejected</span>
  </div>
  <div className="story-event-review-entries">
   {events.map(item=><button type="button" key={item.id}
    aria-pressed={item.id===active} onClick={()=>focus(item)}>
    <strong>Book {item.book} · {item.title||'Unreviewed event lead'}</strong>
    <small>{item.status} · {item.source_verified?'exact source verified':'SOURCE CHANGED — BLOCKED'}</small>
    <span>{item.quote}</span>
   </button>)}
   {!events.length&&<p>No events have been staged. Stage an exact source quote in the Event Leads panel to begin.</p>}
  </div>
  {selected&&<div className="story-event-review-decision">
   <strong>Interpret original quote · Book {selected.book}</strong>
   <blockquote>{selected.quote||'Source mismatch; review blocked'}</blockquote>
   <label>Author-confirmed event title
    <input value={title} maxLength={160} onChange={e=>setTitle(e.target.value)}
      placeholder="What genuinely occurs in this passage?"/>
   </label>
   <label>Meaning of this passage
    <select value={kind} onChange={e=>setKind(e.target.value)}>
     {kinds.map(item=><option value={item.value} key={item.value}>{item.label}</option>)}
    </select>
   </label>
   <label>Position in story time
    <select value={time} onChange={e=>setTime(e.target.value)}>
     {times.map(item=><option value={item.value} key={item.value}>{item.label}</option>)}
    </select>
   </label>
   <label>Reason or caveat (optional)
    <textarea value={note} maxLength={1000} onChange={e=>setNote(e.target.value)} rows={3}/>
   </label>
   <div className="story-event-review-actions">
    <button disabled={busy||!selected.source_verified||!title.trim()} onClick={()=>void decide('approved')}>Approve interpreted event</button>
    <button disabled={busy||!selected.source_verified} onClick={()=>void decide('rejected')}>Reject event lead</button>
   </div>
  </div>}
  {error&&<p role="alert">{error}</p>}
  {notice&&<p role="status">{notice}</p>}
 </section>
}
