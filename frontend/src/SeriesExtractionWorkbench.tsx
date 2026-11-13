import {useEffect,useState} from 'react'
import './series-extraction-workbench.css'

type Suggestion={
  subject_id:string;subject_name:string;predicate:string;object_text:string;
  scope:'world'|'character_belief'|'reader_reveal';knower_id:string|null;
  source_id:string;quote:string;quote_start:number;quote_end:number;start_book:number
}
type Job={
  id:string;source_id:string;model:string;source_length:number;next_offset:number;
  progress_percent:number;status:'ready'|'running'|'error'|'complete'|'cancelled';
  processed_windows:number;candidate_count:number;discarded:number;error:string;
  candidates?:Suggestion[];all_candidates_unsaved:boolean;auto_canon_approved:boolean
}
const BASE='http://127.0.0.1:8000/api/series'
async function api<T>(path:string,init?:RequestInit):Promise<T>{
 const result=await fetch(BASE+path,init)
 const body=await result.json().catch(()=>({}))
 if(!result.ok)throw Error(typeof body.detail==='string'?body.detail:'Extraction request failed')
 return body as T
}
const post=(data?:object):RequestInit=>({
 method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data||{}),
})

export default function SeriesExtractionWorkbench({seriesId,sourceId,model,onUseSuggestion}:{
 seriesId:string;sourceId:string;model:string;onUseSuggestion:(item:Suggestion)=>void
}){
 const [job,setJob]=useState<Job|null>(null)
 const [jobs,setJobs]=useState<Job[]>([])
 const [busy,setBusy]=useState(false)
 const [error,setError]=useState('')
 const [notice,setNotice]=useState('')
 const [visible,setVisible]=useState(15)
 useEffect(()=>{
  const controller=new AbortController()
  setJob(null);setJobs([]);setError('');setNotice('');setVisible(15)
  if(!seriesId||!sourceId)return()=>controller.abort()
  void api<Job[]>(`/${encodeURIComponent(seriesId)}/extraction-jobs?source_id=${encodeURIComponent(sourceId)}`,{
   signal:controller.signal,
  }).then(async entries=>{
   if(controller.signal.aborted)return
   setJobs(entries)
   const sameModel=entries.find(e=>e.model===model&&e.status!=='cancelled')
   if(sameModel){
    const result=await api<Job>(`/${encodeURIComponent(seriesId)}/extraction-jobs/${sameModel.id}`,{signal:controller.signal})
    if(!controller.signal.aborted)setJob(result)
   }
  }).catch(e=>{if(!controller.signal.aborted)setError(String(e))})
  return()=>controller.abort()
 },[seriesId,sourceId,model])

 async function start(){
  if(!model||!sourceId||busy)return
  setBusy(true);setError('');setNotice('')
  try{
   const result=await api<Job>(`/${encodeURIComponent(seriesId)}/extraction-jobs`,
    post({source_id:sourceId,model}))
   setJob(result)
   setNotice('Job prepared locally. No model text sent until you choose Process next window.')
  }catch(e){setError(String(e))}
  finally{setBusy(false)}
 }
 async function next(){
  if(!job||busy)return
  setBusy(true);setError('');setNotice('')
  try{
   const result=await api<Job>(`/${encodeURIComponent(seriesId)}/extraction-jobs/${job.id}/next`,post())
   setJob(result)
   setNotice(result.status==='complete'
     ?'Source scan complete. Every candidate is still unsaved and unapproved.'
     :'One bounded source window processed. Review the evidence or process the next window.')
  }catch(e){
   setError(String(e))
   // Read authoritative checkpoint even after a timeout.
   try{setJob(await api<Job>(`/${encodeURIComponent(seriesId)}/extraction-jobs/${job.id}`))}
   catch{/* Explicit error stays visible */}
  }finally{setBusy(false)}
 }
 async function cancel(){
  if(!job||busy)return
  setBusy(true);setError('');setNotice('')
  try{
   setJob(await api<Job>(`/${encodeURIComponent(seriesId)}/extraction-jobs/${job.id}/cancel`,post()))
   setNotice('Extraction job cancelled. No manuscript or approved canon was changed.')
  }catch(e){setError(String(e))}finally{setBusy(false)}
 }
 return <section className="extraction-workbench" aria-label="Resumable private source extraction">
   <div className="extraction-head">
     <div><small>STAGE II · CONTROLLED SOURCE RESEARCH</small>
       <h3>Extract in small, reviewable windows</h3>
       <p>Process one section at a time with your installed local Ollama model. Progress survives application restarts; every result requires your own review.</p>
     </div>
     <span className="extraction-privacy">Local-only · No automatic canon</span>
   </div>
   {!model&&<p className="extraction-hint">Choose an installed local model above before starting a job.</p>}
   {jobs.length>0&&!job&&<p className="extraction-hint">{jobs.length} previous local extraction job(s) for this source. Choose the same model to resume.</p>}
   {!job&&<button type="button" disabled={!model||!sourceId||busy} onClick={()=>void start()}>
      Prepare a resumable extraction job
   </button>}
   {job&&<div className="extraction-progress">
     <div><strong>{job.status==='complete'?'Scan complete':job.status==='error'?'Paused after error':job.status==='cancelled'?'Cancelled':'Ready for next passage'}</strong>
       <span>{job.progress_percent.toFixed(1)}% · {job.processed_windows} windows · {job.candidate_count} leads · {job.discarded} rejected</span></div>
     <progress max={job.source_length} value={job.next_offset}/>
     <div className="extraction-actions">
       {(job.status==='ready'||job.status==='error'||job.status==='running')&&<button type="button" disabled={busy} onClick={()=>void next()}>
         {busy?'Processing one passage…':job.status==='running'?'Check/recover interrupted window':'Process next window (up to 1,400 characters)'}
       </button>}
       {job.status!=='cancelled'&&job.status!=='running'&&
         <button type="button" className="extraction-cancel" disabled={busy} onClick={()=>void cancel()}>Cancel job</button>}
     </div>
   </div>}
   {error&&<p className="extraction-error" role="alert">{error}</p>}
   {notice&&<p className="extraction-hint" role="status">{notice}</p>}
   {!!job?.candidates?.length&&<div className="extraction-candidates">
     <h4>Unapproved leads ({job.candidates.length})</h4>
     {job.candidates.slice(0,visible).map((item,i)=><article key={item.source_id+':'+item.quote_start+':'+item.predicate+':'+i}>
       <strong>{item.subject_name} · {item.predicate.replaceAll('_',' ')} · {item.object_text}</strong>
       <small>Book {item.start_book} · characters {item.quote_start}–{item.quote_end} · {item.scope.replaceAll('_',' ')}</small>
       <blockquote>{item.quote}</blockquote>
       <button type="button" onClick={()=>onUseSuggestion(item)}>Inspect in proposal form (not approved)</button>
     </article>)}
     {visible<job.candidates.length&&<button type="button" onClick={()=>setVisible(n=>n+15)}>Show 15 more leads</button>}
   </div>}
   <p className="extraction-footnote">A candidate is not a fact. AI can misread narration, irony, POV, consent, emotional motives or chronology. Verify the quoted source and approve canon explicitly in the Review Board.</p>
 </section>
}
