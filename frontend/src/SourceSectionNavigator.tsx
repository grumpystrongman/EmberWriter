import {useEffect,useMemo,useState} from 'react'
import './series-source-sections.css'

type Section={index:number;title:string;start:number;end:number;characters:number;
 heading_detected:boolean;confidence:string;author_confirmed:boolean}
type Structure={sections:Section[];book:number;selected_section:number|null;
 source_length:number;heading_limit_reached:boolean;story_sequence_inferred:boolean}
const BASE='http://127.0.0.1:8000/api/series'

export default function SourceSectionNavigator({seriesId,sourceId,onJump}:{
 seriesId:string;sourceId:string;onJump:(position:number)=>void
}){
 const [data,setData]=useState<Structure|null>(null)
 const [error,setError]=useState('')
 const [filter,setFilter]=useState('')
 const [expanded,setExpanded]=useState(false)
 useEffect(()=>{
  setData(null);setError('');setFilter('');setExpanded(false)
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
     <p>Only literal source headings are detected. This navigation does not establish story-time, scene order, character knowledge, or canon.</p>
     <label>Find a chapter heading
       <input type="search" value={filter} onChange={e=>setFilter(e.target.value)}
         placeholder="Chapter 12, Epilogue…"/></label>
     <div className="source-section-list">
       {matched.slice(0,35).map(section=><button key={section.index} type="button"
         onClick={()=>onJump(section.start)}>
         <span>{String(section.index).padStart(2,'0')} · {section.title}</span>
         <small>{section.heading_detected?'Literal heading':'Unverified'} · source character {section.start.toLocaleString()}</small>
       </button>)}
       {!matched.length&&<p>No matching section headings in this source.</p>}
       {matched.length>35&&<p>Showing 35 of {matched.length}. Refine the search to find another section.</p>}
     </div>
     {data.heading_limit_reached&&<p>Heading limit reached; this index may be incomplete.</p>}
   </div>}
 </details>
}
