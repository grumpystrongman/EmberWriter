import {useEffect,useMemo,useState} from 'react'
import ReviewQueue from './ReviewQueue'
import type {QueueRow} from './ReviewQueue'
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
 const [adding,setAdding]=useState('')
 const [ignored,setIgnored]=useState<string[]>([])
 const [notice,setNotice]=useState('')
 const [revision,setRevision]=useState(0)
 useEffect(()=>{
  const controller=new AbortController()
  setReport(null);setError('')
  if(!opened)return
  setLoading(true)
  void fetch(`${BASE}/${encodeURIComponent(seriesId)}/name-candidates?q=${encodeURIComponent(appliedQuery)}`,{signal:controller.signal})
   .then(async r=>{if(!r.ok)throw Error('Could not read candidate names');return r.json() as Promise<Report>})
   .then(data=>{if(!controller.signal.aborted)setReport(data)})
   .catch(cause=>{if(!controller.signal.aborted)setError(String(cause))})
   .finally(()=>{if(!controller.signal.aborted)setLoading(false)})
  return()=>controller.abort()
 },[seriesId,opened,revision,appliedQuery])
 const rows=useMemo<QueueRow[]>(()=>report?.candidates.filter(item=>!ignored.includes(item.label)).map(item=>({
  key:item.label,title:item.label,subtitle:item.books_with_mention+' books with a literal match',
  preview:item.samples[0]?.excerpt||'',meta:item.literal_mention_count.toLocaleString()+' matches',
  status:'unreviewed',
 }))||[],[report,ignored])
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
   setNotice(item.label+' was registered as a character. No relationship or canon fact was inferred.')
   setRevision(r=>r+1);onAdded()
  }catch(cause){setError(String(cause))}
  finally{setAdding('')}
 }
 function detail(row:QueueRow){
  const item=report?.candidates.find(x=>x.label===row.key)
  if(!item)return null
  return <div className="review-queue-detail-fields">
   <h4>{item.label}</h4>
   <p>{item.books_with_mention} books · {item.literal_mention_count.toLocaleString()} literal matches. This string may be a person, place, organization, title, or ordinary word.</p>
   {item.samples.map(sample=><div key={sample.source_id+':'+sample.start}>
    <small>Book {sample.book}, source character {sample.start.toLocaleString()}</small>
    <blockquote>{sample.excerpt}</blockquote>
    <div className="review-queue-actions">
     <button onClick={()=>onInspectSource(sample.source_id)}>Inspect original source</button>
    </div>
   </div>)}
   <div className="review-queue-actions">
    <button disabled={!!adding} onClick={()=>void register(item)}>
     {adding===item.label?'Saving…':'Register as a character'}</button>
    <button onClick={()=>setIgnored(old=>[...old,item.label])}>Dismiss from this view</button>
   </div>
  </div>
 }
 return <details className="story-name-discovery" open={opened}
  onToggle={e=>setOpened(e.currentTarget.open)}>
  <summary>Discover possible characters · triage queue</summary>
  {opened&&<>
   <div className="story-name-search">
    <form onSubmit={e=>{e.preventDefault();setAppliedQuery(query.trim())}}>
     <label>Search all book text for name candidates
      <input type="search" value={query} maxLength={80} onChange={e=>setQuery(e.target.value)} placeholder="Possible name or title"/>
     </label>
     <button type="submit" disabled={loading}>Search all 80 books</button>
    </form>
   </div>
   {error&&<p role="alert">{error}</p>}
   {notice&&<p role="status">{notice}</p>}
   <ReviewQueue title="Unverified name candidates"
    description="Recurring capitalization across books is a discovery hint, not a character record. Inspect the original text before registration."
    rows={rows} loading={loading} detail={detail}
    emptyText="No candidates match this search and its minimum multi-book threshold."
    pageLabel={report?report.total_candidates+' total candidates':undefined}
    footer={<span>{report?.scanned_sources||0} source snapshots scanned · {report?.total_candidates||0} candidates · top {report?.candidates.length||0} loaded. Search above to query the full collection.</span>}/>
   {report&&<p className="review-queue-disclaimer">{report.disclaimer}</p>}
  </>}
 </details>
}
