import {useEffect,useMemo,useState} from 'react'
import './story-name-discovery.css'

type Sample={book:number;source_id:string;source_hash:string;start:number;end:number;
 excerpt:string;excerpt_start:number;excerpt_end:number}
type Candidate={label:string;literal_mention_count:number;books_with_mention:number;
 sample_books:number[];samples:Sample[];character_identity_verified:boolean}
type Report={scanned_sources:number;total_candidates:number;candidates:Candidate[];
 disclaimer:string;automatically_created_entities:number}
const BASE='http://127.0.0.1:8000/api/series'

export default function StoryNameDiscovery({seriesId,onAdded,onInspectSource}:{
 seriesId:string;onAdded:()=>void;onInspectSource:(sourceId:string)=>void
}){
 const [opened,setOpened]=useState(false)
 const [report,setReport]=useState<Report|null>(null)
 const [loading,setLoading]=useState(false)
 const [error,setError]=useState('')
 const [query,setQuery]=useState('')
 const [appliedQuery,setAppliedQuery]=useState('')
 const [active,setActive]=useState<string|null>(null)
 const [adding,setAdding]=useState('')
 const [ignored,setIgnored]=useState<string[]>([])
 const [notice,setNotice]=useState('')
 const [revision,setRevision]=useState(0)
 useEffect(()=>{
  const controller=new AbortController()
  setReport(null);setError('');setIgnored([])
  if(!opened)return
  setLoading(true)
  void fetch(`${BASE}/${encodeURIComponent(seriesId)}/name-candidates?q=${encodeURIComponent(appliedQuery)}`,{signal:controller.signal})
   .then(async r=>{if(!r.ok)throw Error('Could not read capitalized-name candidates');return r.json() as Promise<Report>})
   .then(data=>{if(!controller.signal.aborted)setReport(data)})
   .catch(cause=>{if(!controller.signal.aborted)setError(String(cause))})
   .finally(()=>{if(!controller.signal.aborted)setLoading(false)})
  return()=>controller.abort()
 },[seriesId,opened,revision,appliedQuery])
 const filtered=useMemo(()=>report?.candidates.filter(item=>
  !ignored.includes(item.label)
 )||[],[report,ignored])
 async function register(item:Candidate){
  if(adding)return
  setAdding(item.label);setError('');setNotice('')
  try{
   const response=await fetch(`${BASE}/${encodeURIComponent(seriesId)}/entities`,{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({name:item.label,kind:'character',aliases:[],description:''}),
   })
   const result=await response.json()
   if(!response.ok)throw Error(result.detail||'Could not register character')
   setNotice(item.label+' was added as an author-registered character. No relationships or facts were inferred.')
   setRevision(r=>r+1);onAdded()
  }catch(cause){setError(String(cause))}
  finally{setAdding('')}
 }
 return <details className="story-name-discovery" open={opened}
  onToggle={e=>setOpened(e.currentTarget.open)}>
  <summary>Find more possible character names across the books</summary>
  {opened&&<>
   <p>Repeated capitalized words and phrases are review leads. Many will be places, titles, ordinary words or false positives. Nothing is automatically created.</p>
   <form className="story-name-search" onSubmit={e=>{e.preventDefault();setAppliedQuery(query.trim())}}>
    <label>Search all candidate strings across the full series
     <input value={query} maxLength={80} onChange={e=>setQuery(e.target.value)} placeholder="Search a possible name"/>
    </label>
    <button type="submit" disabled={loading}>Search all books</button>
   </form>
   {loading&&<p role="status">Scanning book text for repeated capitalized names…</p>}
   {error&&<p role="alert">{error}</p>}
   {notice&&<p role="status">{notice}</p>}
   {report&&<>
    <p>{report.total_candidates.toLocaleString()} candidate strings from {report.scanned_sources} sources, with the top {report.candidates.length} shown. Each needs your verification.</p>
    <div className="story-name-candidates">{filtered.map(item=><article key={item.label}>
     <button className="story-name-toggle" type="button"
      aria-expanded={active===item.label} onClick={()=>setActive(active===item.label?null:item.label)}>
      <strong>{item.label}</strong>
      <small>{item.books_with_mention} books · {item.literal_mention_count.toLocaleString()} literal matches</small>
     </button>
     {active===item.label&&<div className="story-name-evidence">
      {item.samples.map(sample=><div key={sample.source_id+':'+sample.start}>
       <small>Book {sample.book}, source character {sample.start.toLocaleString()}</small>
       <blockquote>{sample.excerpt}</blockquote>
       <button type="button" onClick={()=>onInspectSource(sample.source_id)}>Inspect original source</button>
      </div>)}
      <div className="story-name-actions">
       <button type="button" disabled={!!adding} onClick={()=>void register(item)}>
        {adding===item.label?'Saving…':'Register as a character'}
       </button>
       <button type="button" onClick={()=>setIgnored(old=>[...old,item.label])}>Dismiss from this view</button>
      </div>
     </div>}
    </article>)}</div>
    <p className="story-name-disclaimer">{report.disclaimer} Registering a character does not approve any alleged events or attributes.</p>
   </>}
  </>}
 </details>
}
