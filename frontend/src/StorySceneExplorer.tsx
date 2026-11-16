import {useEffect,useMemo,useState} from 'react'
import ReviewQueue from './ReviewQueue'
import type {QueueRow} from './ReviewQueue'
import StorySceneReviewQueue from './StorySceneReviewQueue'
import StorySceneEvaluation from './StorySceneEvaluation'
import './story-scene-explorer.css'

type Mention={entity_id:string;name:string;literal_form:string}
type Window={source_id:string;source_hash:string;book:number;start:number;end:number;
 length:number;range_hash:string;section_title:string;section_index:number|null;
 confirmed_epub_structure:boolean;boundary_kind:string;preview:string;
 character_mentions:Mention[];scene_confirmed:boolean;pov_inferred:boolean}
type Report={series_id:string;book:number;total:number;windows:Window[];
 source_count:number;truncated:boolean;auto_scene_approved:boolean;disclaimer:string}
type WindowDetail={text:string;source_verified:boolean;start:number;end:number;range_hash:string}
const BASE='http://127.0.0.1:8000/api/series'
const keyOf=(row:Window)=>row.source_id+':'+row.start+':'+row.end

export default function StorySceneExplorer({seriesId,book,entities,onInspectSource}:{
 seriesId:string;book:number;entities:{id:string;name:string;kind:string}[];
 onInspectSource:(sourceId:string)=>void
}){
 const [opened,setOpened]=useState(false)
 const [page,setPage]=useState(0)
 const [report,setReport]=useState<Report|null>(null)
 const [error,setError]=useState('')
 const [loaded,setLoaded]=useState(false)
 const [selected,setSelected]=useState<string|null>(null)
 const [detail,setDetail]=useState<WindowDetail|null>(null)
 const [detailError,setDetailError]=useState('')
 const [verifiedOnly,setVerifiedOnly]=useState(false)
 const [reviewsOpen,setReviewsOpen]=useState(false)
 const [stageBusy,setStageBusy]=useState(false)
 const [notice,setNotice]=useState('')
 const [reviewRevision,setReviewRevision]=useState(0)
 useEffect(()=>{setPage(0);setSelected(null);setVerifiedOnly(false)},[seriesId,book])
 useEffect(()=>{
  const controller=new AbortController()
  setReport(null);setError('')
  if(!opened)return
  setLoaded(false)
  const params=new URLSearchParams({book:String(book),offset:String(page*40),limit:'40'})
  void fetch(`${BASE}/${encodeURIComponent(seriesId)}/scene-windows?${params}`,
   {signal:controller.signal})
   .then(async r=>{if(!r.ok)throw Error('Could not load source reading windows');return r.json() as Promise<Report>})
   .then(value=>{if(!controller.signal.aborted)setReport(value)})
   .catch(cause=>{if(!controller.signal.aborted)setError(String(cause))})
   .finally(()=>{if(!controller.signal.aborted)setLoaded(true)})
  return()=>controller.abort()
 },[seriesId,book,page,opened])
 const windows=useMemo(()=>report?.windows.filter(x=>!verifiedOnly||x.confirmed_epub_structure)||[],
  [report,verifiedOnly])
 const rows=useMemo<QueueRow[]>(()=>windows.map(w=>({
  key:keyOf(w),title:w.section_title,
  subtitle:w.character_mentions.map(x=>x.name).join(' · ')||'No known character name detected',
  preview:w.preview,meta:Math.round(w.length/100)/10+'k chars',
  status:w.boundary_kind==='length_limited_reading_window'?'reading_window':(
   w.confirmed_epub_structure?'epub_section':'source_span'),
  searchText:w.character_mentions.map(x=>x.literal_form).join(' '),
 })),[windows])
 const chosen=windows.find(w=>keyOf(w)===selected)||windows[0]||null
 useEffect(()=>{
  const controller=new AbortController()
  setDetail(null);setDetailError('')
  if(!opened||!chosen)return
  const params=new URLSearchParams({book:String(book),start:String(chosen.start),end:String(chosen.end)})
  void fetch(`${BASE}/${encodeURIComponent(seriesId)}/scene-windows/${encodeURIComponent(chosen.source_id)}/detail?${params}`,
    {signal:controller.signal})
   .then(async r=>{if(!r.ok)throw Error('Exact reading window failed verification');return r.json() as Promise<WindowDetail>})
   .then(result=>{
    if(!controller.signal.aborted){
     if(result.range_hash!==chosen.range_hash||!result.source_verified)
      throw Error('Source fingerprint mismatch; passage will not be shown')
     setDetail(result)
    }
   })
   .catch(cause=>{if(!controller.signal.aborted)setDetailError(String(cause))})
  return()=>controller.abort()
 },[seriesId,book,opened,chosen?.source_id,chosen?.start,chosen?.end,chosen?.range_hash])
 async function stage(window:Window){
  if(stageBusy)return
  setStageBusy(true);setNotice('');setError('')
  try{
   const response=await fetch(`${BASE}/${encodeURIComponent(seriesId)}/scene-reviews`,{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({source_id:window.source_id,book,start:window.start,end:window.end}),
   })
   const value=await response.json()
   if(!response.ok)throw Error(value.detail||'Could not stage the source window')
   setNotice('Exact window staged; no scene or POV has been confirmed automatically.')
   setReviewsOpen(true);setReviewRevision(r=>r+1)
  }catch(cause){setError(String(cause))}finally{setStageBusy(false)}
 }
 function inspect(row:QueueRow){
  const w=windows.find(item=>keyOf(item)===row.key)
  if(!w)return null
  const showing=chosen&&keyOf(chosen)===row.key&&detail
  return <div className="review-queue-detail-fields">
   <h4>{w.section_title}</h4>
   <p>{w.confirmed_epub_structure?'This passage belongs to an author-confirmed EPUB structural section.':
    'This span is a navigation window; its boundaries are not confirmed scene boundaries.'}</p>
   <small>Book {w.book} · Source coordinates {w.start.toLocaleString()}–{w.end.toLocaleString()} · {w.length.toLocaleString()} characters</small>
   <small>Break provenance: {w.boundary_kind.replaceAll('_',' ')}</small>
   {w.character_mentions.length>0&&<p>Literal names in this span: {w.character_mentions.map(x=>x.name).join(', ')}. A textual mention is not proof of participation in the scene.</p>}
   {detailError&&<p role="alert">{detailError}</p>}
   {!showing&&!detailError&&<p role="status">Checking source fingerprint and loading bounded passage…</p>}
   {showing&&<blockquote className="scene-explorer-full-text">{detail.text}</blockquote>}
   <div className="review-queue-actions">
    <button type="button" onClick={()=>onInspectSource(w.source_id)}>Open original book</button>
    <button type="button" disabled={stageBusy||!showing} onClick={()=>void stage(w)}>
     {stageBusy?'Staging…':'Stage exact passage for author review'}
    </button>
   </div>
   <p>Scene identity, speaker, POV, timeline position, beliefs and relationships are **not** automatically determined here. This is a source research window.</p>
  </div>
 }
 return <details className="story-scene-explorer" open={opened}
  onToggle={event=>setOpened(event.currentTarget.open)}>
  <summary>Explore chapter structure and bounded reading windows · Book {book}</summary>
  {opened&&<>
   {error&&<p role="alert">{error}</p>}
   {notice&&<p role="status">{notice}</p>}
   <ReviewQueue key={book+':'+page} title={'Chapter and passage explorer · Book '+book}
    description="Navigate exact source text in manageable pieces. EPUB chapter headings are structural evidence, not automatically identified narrative scenes."
    rows={rows} detail={inspect} loading={!loaded} emptyText="No source spans found for this book."
    onSelectionChange={setSelected} pageLabel={'Page '+(page+1)}
    toolbar={<label className="scene-explorer-filter">Structure
     <select value={verifiedOnly?'epub':'all'} onChange={e=>setVerifiedOnly(e.target.value==='epub')}>
      <option value="all">All reading windows</option>
      <option value="epub">Verified EPUB sections only</option>
     </select>
    </label>}
    footer={<>
     <button disabled={page===0} onClick={()=>{setSelected(null);setPage(x=>Math.max(0,x-1))}}>Previous</button>
     <span>{report?.total?Math.min(page*40+1,report.total):0}–{Math.min((page+1)*40,report?.total||0)} of {report?.total||0} windows</span>
     <button disabled={!report||(page+1)*40>=report.total}
      onClick={()=>{setSelected(null);setPage(x=>x+1)}}>Next</button>
     {report?.truncated&&<small>Bounded scan limit reached</small>}
    </>}/>
   <details className="scene-review-ledger" open={reviewsOpen}
    onToggle={event=>setReviewsOpen(event.currentTarget.open)}>
    <summary>Author scene decisions · verified source passages</summary>
    {reviewsOpen&&<StorySceneReviewQueue seriesId={seriesId} book={book}
     entities={entities} revision={reviewRevision} onInspectSource={onInspectSource}/>}
   </details>
   <StorySceneEvaluation seriesId={seriesId} book={book} revision={reviewRevision}/>
   {report&&<p className="scene-explorer-caveat">{report.disclaimer}</p>}
  </>}
 </details>
}
