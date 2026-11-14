import {useEffect,useState} from 'react'
import './story-dialogue-review.css'
type Entity={id:string;name:string;kind:string}
type Hint={entity_id:string;name:string;position:string;matched_name:string}
type Lead={source_id:string;book:number;quote_start:number;quote_end:number;quote:string;
 context:string;section_title:string|null;speaker_hints:Hint[];ambiguous_speaker:boolean;
 unique_candidate_speaker:string|null}
type LeadReport={leads:Lead[];total:number;ambiguous_cues:number;disclaimer:string;truncated:boolean}
type Review={id:string;quote:string;book:number;source_id:string;quote_start:number;quote_end:number;speaker_id:string|null;
 pov_class:string;note:string;status:string;source_verified:boolean;author_confirmed_speaker:boolean}
const BASE='http://127.0.0.1:8000/api/series'
export default function StoryDialogueReview({seriesId,book,entities,onInspectSource}:{
 seriesId:string;book:number;entities:Entity[];onInspectSource:(id:string)=>void
}){
 const characters=entities.filter(x=>x.kind==='character')
 const [filter,setFilter]=useState('')
 const [page,setPage]=useState(0)
 const [report,setReport]=useState<LeadReport|null>(null)
 const [reviews,setReviews]=useState<Review[]>([])
 const [error,setError]=useState('')
 const [notice,setNotice]=useState('')
 const [busy,setBusy]=useState(false)
 const [active,setActive]=useState<string|null>(null)
 const [speaker,setSpeaker]=useState('')
 const [pov,setPov]=useState('not_determined')
 const [note,setNote]=useState('')
 const [revision,setRevision]=useState(0)
 useEffect(()=>setPage(0),[book,seriesId,filter])
 useEffect(()=>{
  const ctrl=new AbortController();setReport(null);setError('')
  const params=new URLSearchParams({book:String(book),limit:'40',offset:String(page*40)})
  if(filter)params.set('entity_id',filter)
  void fetch(`${BASE}/${encodeURIComponent(seriesId)}/dialogue-leads?${params}`,{signal:ctrl.signal})
   .then(async r=>{if(!r.ok)throw Error('Dialogue leads unavailable');return r.json() as Promise<LeadReport>})
   .then(data=>{if(!ctrl.signal.aborted)setReport(data)})
   .catch(e=>{if(!ctrl.signal.aborted)setError(String(e))})
  void fetch(`${BASE}/${encodeURIComponent(seriesId)}/dialogue-reviews?book=${book}`,{signal:ctrl.signal})
   .then(async r=>{if(!r.ok)throw Error('Cannot read dialogue review ledger');return r.json() as Promise<Review[]>})
   .then(data=>{if(!ctrl.signal.aborted)setReviews(data)})
   .catch(e=>{if(!ctrl.signal.aborted)setError(String(e))})
  return()=>ctrl.abort()
 },[seriesId,book,filter,page,revision])
 const selected=reviews.find(x=>x.id===active)||null
 const reviewed=(lead:Lead)=>reviews.find(x=>x.source_id===lead.source_id&&x.quote_start===lead.quote_start&&x.quote_end===lead.quote_end)
 async function action(url:string,body:object){
  const r=await fetch(`${BASE}/${encodeURIComponent(seriesId)}${url}`,{
   method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),
  })
  const result=await r.json()
  if(!r.ok)throw Error(result.detail||'Dialogue review failed')
  return result as Review
 }
 async function stage(lead:Lead){
  if(busy)return
  setBusy(true);setError('');setNotice('')
  try{
   const record=await action('/dialogue-reviews',{
    source_id:lead.source_id,quote_start:lead.quote_start,quote_end:lead.quote_end,
   })
   setActive(record.id);setSpeaker('');setPov('not_determined');setNote('')
   setNotice('Exact dialogue quote staged. No speaker or POV has been approved.')
   setRevision(x=>x+1)
  }catch(e){setError(String(e))}finally{setBusy(false)}
 }
 async function decide(decision:'approved'|'rejected'){
  if(!selected||busy)return
  setBusy(true);setError('');setNotice('')
  try{
   await action(`/dialogue-reviews/${selected.id}/decision`,{
    decision,speaker_id:speaker||null,pov_class:pov,note,
   })
   setNotice(decision==='approved'?'Your verified speaker decision was saved, separate from canon facts.':'Dialogue candidate rejected.')
   setRevision(x=>x+1)
  }catch(e){setError(String(e))}finally{setBusy(false)}
 }
 return <section className="story-dialogue-review" aria-label="Dialogue attribution research">
  <header>
   <span>SCENE / VOICE RESEARCH</span><h3>Who might be speaking in Book {book}?</h3>
   <p>Find quotations with nearby named speech verbs. These are clues, not reliable speaker attributions or viewpoint classifications. You decide after reading the passage.</p>
  </header>
  <label>Filter nearby character name
   <select value={filter} onChange={e=>setFilter(e.target.value)}>
    <option value="">All known characters</option>
    {characters.map(e=><option value={e.id} key={e.id}>{e.name}</option>)}
   </select>
  </label>
  {error&&<p role="alert">{error}</p>}
  {notice&&<p role="status">{notice}</p>}
  {report?<><p>{report.total} attribution clues in this book; {report.ambiguous_cues} with multiple character hints. The first {report.leads.length} in this page are shown. No speech is approved automatically.</p>
   <div className="story-dialogue-pages">
    <button disabled={!page} onClick={()=>setPage(x=>Math.max(0,x-1))}>Previous</button>
    <span>Page {page+1}</span>
    <button disabled={(page+1)*40>=report.total} onClick={()=>setPage(x=>x+1)}>Next</button>
   </div>
   <div className="story-dialogue-leads">{report.leads.map(lead=>{
    const prior=reviewed(lead)
    return <article key={lead.source_id+':'+lead.quote_start}>
     <small>{lead.section_title||'Original source'} · Quote at character {lead.quote_start.toLocaleString()} · {lead.ambiguous_speaker?'Multiple cues':'Single nearby cue'} · {prior?.status||'unreviewed'}</small>
     <blockquote>{lead.context}</blockquote>
     <p>Possible named cue(s): {lead.speaker_hints.map(x=>x.name+' ('+x.position.replaceAll('_',' ')+')').join(', ')}</p>
     <div className="story-dialogue-actions">
      <button onClick={()=>onInspectSource(lead.source_id)}>Open original source</button>
      {prior?<button onClick={()=>{
       setActive(prior.id);setSpeaker(prior.speaker_id||'');setPov(prior.pov_class);setNote(prior.note)
      }}>Review staged attribution</button>:
      <button disabled={busy} onClick={()=>void stage(lead)}>Stage for author review</button>}
     </div>
    </article>
   })}</div>
   <p className="story-dialogue-caveat">{report.disclaimer}</p>
  </>:<p role="status">Checking source quotations for Book {book}…</p>}
  <div className="story-dialogue-ledger">
   <strong>Author-reviewed dialogue · {reviews.filter(r=>r.author_confirmed_speaker).length} confirmed · {reviews.filter(r=>r.status==='proposed').length} pending</strong>
   {reviews.map(item=><button className="story-dialogue-record" key={item.id}
    onClick={()=>{setActive(item.id);setSpeaker(item.speaker_id||'');setPov(item.pov_class);setNote(item.note)}}>
    {item.status} · {item.quote.slice(0,90)}
   </button>)}
   {selected&&<div className="story-dialogue-decision">
    <strong>Review exact source quote</strong>
    <blockquote>{selected.quote||'Source fingerprint invalid'}</blockquote>
    <label>Speaker you verified in the source
     <select value={speaker} onChange={e=>setSpeaker(e.target.value)}>
      <option value="">Not determined — cannot approve</option>
      {characters.map(e=><option key={e.id} value={e.id}>{e.name}</option>)}
     </select>
    </label>
    <label>Viewpoint framing (optional, author classification)
     <select value={pov} onChange={e=>setPov(e.target.value)}>
      <option value="not_determined">Not determined</option>
      <option value="first_person">First-person</option>
      <option value="third_limited">Third-person limited</option>
      <option value="third_omniscient">Third-person omniscient</option>
      <option value="other">Other / mixed</option>
     </select>
    </label>
    <label>Reason for your interpretation
     <textarea maxLength={1000} rows={3} value={note} onChange={e=>setNote(e.target.value)}/>
    </label>
    <div className="story-dialogue-actions">
     <button disabled={busy||!speaker||!selected.source_verified} onClick={()=>void decide('approved')}>Approve speaker attribution</button>
     <button disabled={busy||!selected.source_verified} onClick={()=>void decide('rejected')}>Reject attribution lead</button>
    </div>
   </div>}
  </div>
 </section>
}
