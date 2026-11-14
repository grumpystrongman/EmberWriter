import {useEffect,useRef,useState} from 'react'
import './story-evidence-quality-gate.css'

type Case={id:string;label:string;status:string;answer_correct:boolean;quote_correct:boolean;elapsed_ms:number}
type Result={status:string;passed:number;total:number;elapsed_ms:number;cases:Case[];
 limitations:string;grading:string;auto_approval_allowed:boolean;source_text_sent:boolean}
const BASE='http://127.0.0.1:8000/api/series'

export default function StoryEvidenceQualityGate({seriesId,model}:{seriesId:string;model:string}){
 const [running,setRunning]=useState(false)
 const [report,setReport]=useState<Result|null>(null)
 const [error,setError]=useState('')
 const abortRef=useRef<AbortController|null>(null)
 useEffect(()=>()=>{abortRef.current?.abort()},[seriesId,model])
 async function run(){
  if(!model||running)return
  const controller=new AbortController()
  abortRef.current=controller;setRunning(true);setError('');setReport(null)
  try{
   const response=await fetch(`${BASE}/${encodeURIComponent(seriesId)}/local-model-evidence-benchmark`,{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({model}),signal:controller.signal,
   })
   const payload=await response.json()
   if(!response.ok)throw Error(payload.detail||'Synthetic evidence benchmark failed')
   if(!controller.signal.aborted)setReport(payload)
  }catch(cause){if(!controller.signal.aborted)setError(String(cause))}
  finally{if(abortRef.current===controller){abortRef.current=null;setRunning(false)}}
 }
 function cancel(){
  abortRef.current?.abort();abortRef.current=null;setRunning(false)
  setError('Benchmark cancelled; no manuscript or canon changed.')
 }
 return <section className="story-evidence-quality-gate" aria-label="Synthetic story evidence quality checks">
  <div>
   <strong>Five-case story evidence quality check</strong>
   <p>Can this model handle quoted facts, character beliefs, Book 1 knowledge, changing states, and misleading instructions inside fictional text? The exact answers were set before testing. Each case has a 22-second limit; the complete test is bounded to 115 seconds. Results never automatically approve canon.</p>
  </div>
  <div className="story-quality-actions">
   <button type="button" disabled={!model||running} onClick={()=>void run()}>
    {running?'Checking five fictional questions…':'Run five-case evidence check'}
   </button>
   {running&&<button type="button" onClick={cancel}>Cancel check</button>}
  </div>
  {error&&<p role="status">{error}</p>}
  {report&&<div className="story-quality-results" role="status">
   <strong>{report.passed} / {report.total} passed · {report.status.replaceAll('_',' ')}</strong>
   <p>All evidence is fictional. Each answer and its original quotation must match exactly; correct-looking output without the right citation fails.</p>
   <div className="story-quality-cases">{report.cases.map(item=><div key={item.id}>
    <b>{item.label}</b>
    <span>{item.status==='passed'?'Pass':'Not verified: '+item.status}</span>
    <small>{item.elapsed_ms.toLocaleString()} ms · answer {item.answer_correct?'matched':'not verified'} · quote {item.quote_correct?'matched':'not verified'}</small>
   </div>)}</div>
   <p>{report.limitations}</p>
  </div>}
 </section>
}
