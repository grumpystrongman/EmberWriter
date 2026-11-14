import {useEffect,useMemo,useState} from 'react'
import './series-source-sections.css'
import SeriesEpubCollectionRecovery from './SeriesEpubCollectionRecovery'

type Section={index:number;title:string;start:number;end:number;characters:number;
 heading_detected:boolean;confidence:string;author_confirmed:boolean;toc_href?:string;toc_fragment?:string}
type Structure={sections:Section[];book:number;selected_section:number|null;
 source_length:number;heading_limit_reached:boolean;story_sequence_inferred:boolean;
 structure_index_saved?:boolean;metadata_origin?:string}
const BASE='http://127.0.0.1:8000/api/series'

export default function SourceSectionNavigator({seriesId,sourceId,onJump}:{
 seriesId:string;sourceId:string;onJump:(position:number)=>void
}){
 const [data,setData]=useState<Structure|null>(null)
 const [error,setError]=useState('')
 const [filter,setFilter]=useState('')
 const [expanded,setExpanded]=useState(false)
 const [originalEpub,setOriginalEpub]=useState<File|null>(null)
 const [preview,setPreview]=useState<(Structure & {exact_snapshot_match:boolean;status:string;message:string;matched_sections:number;spine_sections?:number;toc_fragment_sections?:number})|null>(null)
 const [previewBusy,setPreviewBusy]=useState(false)
 const [previewError,setPreviewError]=useState('')
 const [indexSaved,setIndexSaved]=useState(false)
 async function confirmIndex(){
  if(!originalEpub||!preview?.exact_snapshot_match||previewBusy)return
  setPreviewBusy(true);setPreviewError('')
  try{
   const body=new FormData();body.set('file',originalEpub)
   const response=await fetch(`${BASE}/${encodeURIComponent(seriesId)}/sources/${encodeURIComponent(sourceId)}/epub-structure-confirm`,{method:'POST',body})
   const result=await response.json()
   if(!response.ok)throw Error(result.detail||'Could not save the verified index')
   setIndexSaved(true)
   const updated=await fetch(`${BASE}/${encodeURIComponent(seriesId)}/sources/${encodeURIComponent(sourceId)}/sections`)
   if(updated.ok)setData(await updated.json())
  }catch(e){setPreviewError(String(e))}finally{setPreviewBusy(false)}
 }
 async function previewOriginal(){
  if(!originalEpub||previewBusy)return
  setPreviewBusy(true);setPreviewError('');setPreview(null)
  try{
   const body=new FormData();body.set('file',originalEpub)
   const response=await fetch(`${BASE}/${encodeURIComponent(seriesId)}/sources/${encodeURIComponent(sourceId)}/epub-structure-preview`,{method:'POST',body})
   const result=await response.json()
   if(!response.ok)throw Error(result.detail||'Unable to reconcile EPUB structure')
   setPreview(result)
  }catch(e){setPreviewError(String(e))}finally{setPreviewBusy(false)}
 }
 useEffect(()=>{
  setData(null);setError('');setFilter('');setExpanded(false)
  setOriginalEpub(null);setPreview(null);setPreviewError('');setIndexSaved(false)
  const controller=new AbortController()
  void fetch(`${BASE}/${encodeURIComponent(seriesId)}/sources/${encodeURIComponent(sourceId)}/sections`,{
   signal:controller.signal,
  }).then(async response=>{
   const payload=await response.json()
   if(!response.ok)throw Error(payload.detail||'Could not locate source sections')
   return payload as Structure
  }).then(payload=>{if(!controller.signal.aborted)setData(payload)})
    .catch(cause=>{if(!controller.signal.aborted)setError(String(cause))})
  return()=>controller.abort()
 },[seriesId,sourceId])
 const matched=useMemo(()=>data?.sections.filter(s=>s.title.toLocaleLowerCase().includes(filter.toLocaleLowerCase()))||[],[data,filter])
 return <details className="source-sections" open={expanded}
   onToggle={e=>setExpanded(e.currentTarget.open)}>
   <summary>Jump to a source chapter or section <span>{data?.sections.length??'…'} structural sections</span></summary>
   {error&&<p role="alert">{error}</p>}
   {data&&<div className="source-section-content">
     <p>{data.structure_index_saved?'Saved exact-match EPUB spine and table-of-contents index. Source coordinates are verified; publication labels do not establish story chronology or canon.':'Only literal source headings are detected until an exact EPUB spine index is saved. This navigation does not establish story-time, scene order, character knowledge, or canon.'}</p>
     <label>Find a chapter heading
       <input type="search" value={filter} onChange={e=>setFilter(e.target.value)}
         placeholder="Chapter 12, Epilogue…"/></label>
     <div className="source-section-list">
       {matched.slice(0,35).map(section=><button key={section.index} type="button"
         onClick={()=>onJump(section.start)}>
         <span>{String(section.index).padStart(2,'0')} · {section.title}</span>
         <small>{section.confidence==='exact_epub_toc_fragment'?'Exact EPUB ToC anchor':section.confidence.startsWith('exact_')?'Verified EPUB spine':section.heading_detected?'Literal heading':'Unverified'} · source character {section.start.toLocaleString()}</small>
       </button>)}
       {!matched.length&&<p>No matching section headings in this source.</p>}
       {matched.length>35&&<p>Showing 35 of {matched.length}. Refine the search to find another section.</p>}
     </div>
     {data.heading_limit_reached&&<p>Heading limit reached; this index may be incomplete.</p>}
     <div className="source-original-preview">
       <strong>Chunk 4 · Restore original EPUB structure</strong>
       <p>If the imported text lost chapter headings, select the original EPUB for this exact book. EmberWriter compares its entire extracted text against the saved snapshot before offering any spine positions. Nothing is saved or replaced.</p>
       <label>Original EPUB (checked locally)
         <input type="file" accept=".epub,application/epub+zip" onChange={e=>{setOriginalEpub(e.target.files?.[0]||null);setPreview(null);setPreviewError('')}}/>
       </label>
       <button type="button" disabled={!originalEpub||previewBusy} onClick={()=>void previewOriginal()}>{previewBusy?'Comparing exact source…':'Preview original EPUB spine'}</button>
       {previewError&&<p role="alert">{previewError}</p>}
       {preview&&<div role="status" className="source-original-results">
         <p><strong>{preview.exact_snapshot_match?'Exact source match':'Edition / extraction mismatch'}</strong> · {preview.message}</p>
         {preview.exact_snapshot_match&&<>
           <p>{preview.spine_sections??preview.matched_sections} exact EPUB spine documents and {preview.toc_fragment_sections??0} uniquely matched ToC fragment links recovered. Labels come from the original publication; none establish story-time chronology.</p>
           <div className="source-section-list">{preview.sections.slice(0,40).map(row=><button type="button" key={row.index} onClick={()=>onJump(row.start)}>
             {row.title} · {row.confidence==='exact_epub_toc_fragment'?'ToC anchor':'spine'} · character {row.start.toLocaleString()}
           </button>)}</div>
           {preview.sections.length>40&&<p>First 40 sections shown; no positions inferred.</p>}
           <button type="button" disabled={previewBusy||indexSaved} onClick={()=>void confirmIndex()}>{indexSaved?'Verified index saved':'Save verified chapter index'}</button>
           {indexSaved&&<p role="status">Index saved to your local private Series Vault. It will now appear in this source navigator after refresh. Original EPUB and manuscript text were not stored or replaced.</p>}
         </>}
       </div>}
     </div>
     <SeriesEpubCollectionRecovery seriesId={seriesId} onIndexed={()=>{
       void fetch(`${BASE}/${encodeURIComponent(seriesId)}/sources/${encodeURIComponent(sourceId)}/sections`)
         .then(async response=>{if(response.ok)setData(await response.json())})
     }}/>
   </div>}
 </details>
}
