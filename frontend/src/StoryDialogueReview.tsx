import {useEffect,useMemo,useState} from 'react'
import ReviewQueue from './ReviewQueue'
import type {QueueRow} from './ReviewQueue'
import './story-dialogue-review.css'

type Entity={id:string;name:string;kind:string}
type Hint={entity_id:string;name:string;position:string;matched_name:string}
type Lead={source_id:string;book:number;quote_start:number;quote_end:number;quote:string;
 context:string;section_title:string|null;speaker_hints:Hint[];ambiguous_speaker:boolean}
type LeadReport={leads:Lead[];total:number;ambiguous_cues:number;disclaimer:string;truncated:boolean}
type Review={id:string;quote:string;book:number;source_id:string;quote_start:number;quote_end:number;
 speaker_id:string|null;pov_class:string;note:string;status:string;source_verified:boolean;
 author_confirmed_speaker:boolean}
const BASE='http://127.0.0.1:8000/api/series'
export default function StoryDialogueReview({seriesId,book,entities,onInspectSource}:{
 seriesId:string;book:number;entities:Entity[];onInspectSource:(id:string)=>void
}){
 const characters=useMemo(()=>entities.filter(x=>x.kind==='character'),[entities])
 const [filter,setFilter]=useState('')
 const [page,setPage]=useState(0)
 const [view,setView]=useState<'leads'|'reviews'>('leads')
 const [report,setReport]=useState<LeadReport|null>(null)
 const [reviews,setReviews]=useState<Review[]>([])
 const [error,setError]=useState('')
 const [notice,setNotice]=useState('')
 const [busy,setBusy]=useState(false)
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
   .then(async r=>{if(!r.ok)throw Error('Cannot read dialogue reviews');return r.json() as Promise<Review[]>})
   .then(data=>{if(!ctrl.signal.aborted)setReviews(data)})
   .catch(e=>{if(!ctrl.signal.aborted)setError(String(e))})
  return()=>ctrl.abort()
 },[seriesId,book,filter,page,revision])
 const keyed=(source:string,start:number)=>source+':'+start
 const reviewed=(lead:Lead)=>reviews.find(x=>x.source_id===lead.source_id&&x.quote_start===lead.quote_start&&x.quote_end===lead.quote_end)
 const rows=useMemo<QueueRow[]>(()=>{
  if(view==='reviews')return reviews.map(item=>({
   key:'review:'+item.id,title:'Book '+item.book+' · '+(characters.find(x=>x.id===item.speaker_id)?.name||'Speaker unconfirmed'),
   subtitle:item.source_verified?'Exact source verified':'SOURCE CHANGED',
   preview:item.quote,meta:'At '+item.quote_start.toLocaleString(),status:item.status,
  }))
  return (report?.leads||[]).map(lead=>{
   const review=reviewed(lead)
   return {key:keyed(lead.source_id,lead.quote_start),
    title:lead.speaker_hints.map(x=>x.name).filter((x,i,a)=>a.indexOf(x)===i).join(', ')||'Unassigned speaker',
    subtitle:'Book '+lead.book+' · '+(lead.section_title||'Original source'),
    preview:lead.quote,meta:'At '+lead.quote_start.toLocaleString(),
    status:review?.status||(lead.ambiguous_speaker?'ambiguous':'unreviewed'),
    searchText:lead.context}
  })
 },[view,reviews,report,characters])
 async function action(path:string,body:object):Promise<Review>{
  const r=await fetch(`${BASE}/${encodeURIComponent(seriesId)}${path}`,{
   method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),
  })
  const result=await r.json()
  if(!r.ok)throw Error(result.detail||'Dialogue action failed')
  return result as Review
 }
 async function stage(lead:Lead){
  if(busy)return
  setBusy(true);setError('');setNotice('')
  try{
   await action('/dialogue-reviews',{
    source_id:lead.source_id,quote_start:lead.quote_start,quote_end:lead.quote_end,
   })
   setView('reviews');setSpeaker('');setPov('not_determined');setNote('')
   setNotice('Exact quote staged for author review; no speaker or POV approved.')
   setRevision(x=>x+1)
  }catch(e){setError(String(e))}finally{setBusy(false)}
 }
 async function decide(item:Review,decision:'approved'|'rejected'){
  if(busy)return
  setBusy(true);setError('');setNotice('')
  try{
   await action(`/dialogue-reviews/${item.id}/decision`,{
    decision,speaker_id:speaker||item.speaker_id||null,pov_class:pov,note,
   })
   setNotice(decision==='approved'?'Author-confirmed speaker saved. No canon facts were inferred.':'Candidate rejected.')
   setRevision(x=>x+1)
  }catch(e){setError(String(e))}finally{setBusy(false)}
 }
 function detail(row:QueueRow){
  const review=view==='reviews'?reviews.find(x=>'review:'+x.id===row.key):undefined
  const lead=view==='leads'?report?.leads.find(x=>keyed(x.source_id,x.quote_start)===row.key):undefined
  if(review)return <div className="review-queue-detail-fields">
    <h4>{review.status==='approved'?'Approved attribution':'Review speaker attribution'}</h4>
    <blockquote>{review.quote||'Source fingerprint no longer matches'}</blockquote>
    <small>Book {review.book} · Position {review.quote_start.toLocaleString()} · {review.status}</small>
    <button type="button" onClick={()=>onInspectSource(review.source_id)}>Open original source</button>
    <label>Speaker verified in original passage
     <select key={'speaker:'+review.id} defaultValue={review.speaker_id||''}
      onChange={e=>setSpeaker(e.target.value)}>
      <option value="">Not determined — cannot approve</option>
      {characters.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}
     </select>
    </label>
    <label>Viewpoint, only if verified
     <select key={'pov:'+review.id} defaultValue={review.pov_class}
      onChange={e=>setPov(e.target.value)}>
      <option value="not_determined">Undetermined</option>
      <option value="first_person">First person</option>
      <option value="third_limited">Third limited</option>
      <option value="third_omniscient">Third omniscient</option>
      <option value="other">Other / mixed</option>
     </select>
    </label>
    <label>Review notes
     <textarea key={'note:'+review.id} defaultValue={review.note} maxLength={1000} rows={3}
      onChange={e=>setNote(e.target.value)}/>
    </label>
    <div className="review-queue-actions">
     <button disabled={busy||!review.source_verified||!(speaker||review.speaker_id)}
      onClick={()=>void decide(review,'approved')}>Approve verified speaker</button>
     <button disabled={busy||!review.source_verified}
      onClick={()=>void decide(review,'rejected')}>Reject clue</button>
    </div>
   </div>
  if(!lead)return null
  const existing=reviewed(lead)
  return <div className="review-queue-detail-fields">
   <h4>Book {lead.book} · {lead.section_title||'Original source'}</h4>
   <blockquote>{lead.context}</blockquote>
   <small>Exact quote at characters {lead.quote_start.toLocaleString()}–{lead.quote_end.toLocaleString()}</small>
   <p>Named speech clues: {lead.speaker_hints.map(h=>h.name+' ('+h.position.replaceAll('_',' ')+')').join(', ')}. These do not prove who spoke.</p>
   <div className="review-queue-actions">
    <button type="button" onClick={()=>onInspectSource(lead.source_id)}>Open full source</button>
    {existing?
     <button type="button" onClick={()=>{setView('reviews');setSpeaker(existing.speaker_id||'');setPov(existing.pov_class);setNote(existing.note)}}>
      Open staged review</button>:
     <button disabled={busy} type="button" onClick={()=>void stage(lead)}>Stage for review</button>}
   </div>
  </div>
 }
 return <section className="story-dialogue-review" aria-label="Dialogue attribution research">
  <div className="story-review-view-switch" role="group" aria-label="Dialogue queue views">
   <button aria-pressed={view==='leads'} onClick={()=>setView('leads')}>Source clues {report?.total??'…'}</button>
   <button aria-pressed={view==='reviews'} onClick={()=>{setView('reviews');setSpeaker('');setPov('not_determined');setNote('')}}>
    Review queue {reviews.filter(x=>x.status==='proposed').length} pending</button>
   <span>{reviews.filter(x=>x.author_confirmed_speaker).length} author-confirmed</span>
  </div>
  {error&&<p role="alert">{error}</p>}
  {notice&&<p role="status">{notice}</p>}
  <ReviewQueue key={view+':'+book+':'+page} title={view==='leads'?'Dialogue clues · Book '+book:'Speaker review queue · Book '+book}
   description={view==='leads'?'Short source excerpts stay in the list; full context opens alongside your selection. Cues do not establish speakers.':'Confirm a speaker only after checking the original source. No automatic canon approval.'}
   rows={rows} onSelectionChange={key=>{
    const item=reviews.find(x=>'review:'+x.id===key)
    if(item){setSpeaker(item.speaker_id||'');setPov(item.pov_class);setNote(item.note)}
   }} loading={view==='leads'&&!report} emptyText={view==='leads'?'No named dialogue clues found.':'No dialogue has been staged for review.'}
   detail={detail} pageLabel={view==='leads'?'Page '+(page+1):undefined}
   toolbar={view==='leads'?<label>Character
    <select value={filter} onChange={e=>setFilter(e.target.value)}>
     <option value="">All known characters</option>
     {characters.map(x=><option value={x.id} key={x.id}>{x.name}</option>)}
    </select>
   </label>:undefined}
   footer={view==='leads'?<>
    <button type="button" disabled={page===0} onClick={()=>setPage(x=>Math.max(0,x-1))}>Previous page</button>
    <span>{report?Math.min(page*40+1,report.total):0}–{report?Math.min((page+1)*40,report.total):0} of {report?.total||0} clues</span>
    <button type="button" disabled={!report||(page+1)*40>=report.total} onClick={()=>setPage(x=>x+1)}>Next page</button>
   </>:undefined}/>
  <p className="story-dialogue-caveat">Review-only: nearby names and speech verbs cannot establish viewpoint or speaker identity. Original quotes are preserved locally. {report?.disclaimer}</p>
 </section>
}
