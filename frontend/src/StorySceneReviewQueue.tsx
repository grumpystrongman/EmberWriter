import {useEffect,useMemo,useState} from 'react'
import ReviewQueue from './ReviewQueue'
import type {QueueRow} from './ReviewQueue'
import './story-scene-explorer.css'

type Person={id:string;name:string;kind:string}
export type SceneReview={id:string;source_id:string;book:number;start:number;end:number;
 source_hash:string;range_hash:string;title:string;scene_kind:string;pov_style:string;
 pov_character_id:string|null;note:string;status:string;source_verified:boolean;
 author_confirmed_scene:boolean;excerpt:string}
const BASE='http://127.0.0.1:8000/api/series'
const kinds=[
 ['uncertain','Unclassified — cannot approve'],
 ['actual_scene','Verified narrative scene'],
 ['narrative_transition','Narrative transition'],
 ['recollection','Recollection or reported past'],
 ['dream','Dream or vision'],
 ['front_matter','Front/back matter'],
 ['non_scene','Not a narrative scene'],
] as const
const viewpoints=[
 ['undetermined','Not determined'],
 ['first_person','First-person'],
 ['third_limited','Third-person limited'],
 ['third_omniscient','Third-person omniscient'],
 ['second_person','Second-person'],
 ['mixed_other','Mixed or other'],
] as const

export default function StorySceneReviewQueue({seriesId,book,entities,revision,onInspectSource}:{
 seriesId:string;book:number;entities:Person[];revision:number;
 onInspectSource:(source:string)=>void
}){
 const [reviews,setReviews]=useState<SceneReview[]>([])
 const [error,setError]=useState('')
 const [notice,setNotice]=useState('')
 const [saving,setSaving]=useState(false)
 const [refresh,setRefresh]=useState(0)
 const [title,setTitle]=useState('')
 const [kind,setKind]=useState('uncertain')
 const [pov,setPov]=useState('undetermined')
 const [character,setCharacter]=useState('')
 const [note,setNote]=useState('')
 const [selected,setSelected]=useState<string|null>(null)
 useEffect(()=>{
  const ctrl=new AbortController()
  setError('')
  void fetch(`${BASE}/${encodeURIComponent(seriesId)}/scene-reviews?book=${book}`,
   {signal:ctrl.signal})
   .then(async r=>{if(!r.ok)throw Error('Scene review records unavailable');return r.json() as Promise<SceneReview[]>})
   .then(data=>{if(!ctrl.signal.aborted)setReviews(data)})
   .catch(cause=>{if(!ctrl.signal.aborted)setError(String(cause))})
  return()=>ctrl.abort()
 },[seriesId,book,revision,refresh])
 const rows=useMemo<QueueRow[]>(()=>reviews.map(item=>({
  key:item.id,title:item.title||'Book '+item.book+' · classification required',
  subtitle:item.source_verified?'Exact source verified':'Source fingerprint invalid',
  preview:item.excerpt,meta:'At '+item.start.toLocaleString(),status:item.status,
 })),[reviews])
 const characters=entities.filter(x=>x.kind==='character')
 function focus(review:SceneReview){
  setSelected(review.id);setTitle(review.title);setKind(review.scene_kind)
  setPov(review.pov_style);setCharacter(review.pov_character_id||'')
  setNote(review.note);setError('');setNotice('')
 }
 async function decide(review:SceneReview,decision:'approved'|'rejected'){
  if(saving)return
  setSaving(true);setError('');setNotice('')
  try{
   const r=await fetch(
    `${BASE}/${encodeURIComponent(seriesId)}/scene-reviews/${review.id}/decision`,{
     method:'POST',headers:{'Content-Type':'application/json'},
     body:JSON.stringify({
      decision,title,scene_kind:kind,pov_style:pov,
      pov_character_id:character||null,note,
     }),
    })
   const result=await r.json()
   if(!r.ok)throw Error(result.detail||'Scene decision could not be saved')
   setNotice(decision==='approved'?
    'Author classification saved with an exact source citation. No Canon Graph fact was created.':
    'Reading-window classification rejected.')
   setRefresh(x=>x+1)
  }catch(cause){setError(String(cause))}finally{setSaving(false)}
 }
 function details(row:QueueRow){
  const review=reviews.find(x=>x.id===row.key)
  if(!review)return null
  return <div className="review-queue-detail-fields">
   <h4>{review.title||'Interpret this source window'}</h4>
   <blockquote>{review.excerpt||'Original source no longer verifies'}</blockquote>
   <small>Book {review.book}, characters {review.start.toLocaleString()}–{review.end.toLocaleString()} · {review.status}</small>
   <div className="review-queue-actions">
    <button onClick={()=>onInspectSource(review.source_id)}>Open original source</button>
   </div>
   <label>Author-supplied passage title
    <input key={'title:'+review.id} defaultValue={review.title} maxLength={160}
     onChange={e=>setTitle(e.target.value)} placeholder="What happens in this passage?"/>
   </label>
   <label>Author-verified passage kind
    <select key={'kind:'+review.id} defaultValue={review.scene_kind}
     onChange={e=>setKind(e.target.value)}>
     {kinds.map(([value,label])=><option key={value} value={value}>{label}</option>)}
    </select>
   </label>
   <label>Narrative viewpoint framing
    <select key={'pov:'+review.id} defaultValue={review.pov_style}
     onChange={e=>setPov(e.target.value)}>
     {viewpoints.map(([value,label])=><option key={value} value={value}>{label}</option>)}
    </select>
   </label>
   <label>Viewpoint character (if explicitly supported)
    <select key={'character:'+review.id} defaultValue={review.pov_character_id||''}
     onChange={e=>setCharacter(e.target.value)}>
     <option value="">Unspecified</option>
     {characters.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}
    </select>
   </label>
   <label>Why you classified it this way
    <textarea key={'note:'+review.id} defaultValue={review.note} rows={3} maxLength={1000}
     onChange={e=>setNote(e.target.value)}/>
   </label>
   <div className="review-queue-actions">
    <button disabled={saving||!review.source_verified||
      !(title||review.title).trim()||kind==='uncertain'}
     onClick={()=>void decide(review,'approved')}>Approve classification</button>
    <button disabled={saving||!review.source_verified}
     onClick={()=>void decide(review,'rejected')}>Reject passage lead</button>
   </div>
   <p>This stores your interpretation only. It does not assert dialogue, relationships, character beliefs, or established story chronology.</p>
  </div>
 }
 return <section className="scene-review-queue" aria-label="Author-reviewed scene classifications">
  {error&&<p role="alert">{error}</p>}
  {notice&&<p role="status">{notice}</p>}
  <ReviewQueue title="Author-reviewed passage classifications"
   description="Confirm a scene or classify it as a transition, recollection, dream, or non-scene. Original fingerprints must still match."
   rows={rows} detail={details} emptyText="No passage is staged. Use the source window explorer to stage an exact passage."
   selectedKey={selected} onSelectionChange={key=>{
    const item=reviews.find(x=>x.id===key)
    if(item&&item.id!==selected)focus(item)
   }}
   footer={<span>{reviews.filter(x=>x.status==='proposed').length} pending · {reviews.filter(x=>x.author_confirmed_scene).length} author-confirmed scenes · {reviews.filter(x=>x.status==='rejected').length} rejected</span>}/>
 </section>
}
