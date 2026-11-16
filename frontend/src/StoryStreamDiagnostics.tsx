import {useEffect,useRef,useState} from 'react'
import './story-stream-diagnostics.css'

type Diagnostic={
 status:string;detail:string;elapsed_ms:number;first_token_ms:number|null;
 load_ms:number|null;prompt_eval_ms:number|null;generation_ms:number|null;
 generated_tokens:number|null;tokens_per_second:number|null;stream_completed:boolean;limitations:string
}
const API='http://127.0.0.1:8000/api/series'
export default function StoryStreamDiagnostics({seriesId,model}:{seriesId:string;model:string}){
 const [busy,setBusy]=useState(false)
 const [error,setError]=useState('')
 const [result,setResult]=useState<Diagnostic|null>(null)
 const controller=useRef<AbortController|null>(null)
 useEffect(()=>()=>{controller.current?.abort()},[seriesId])
 async function run(){
  if(!model||busy)return
  const request=new AbortController()
  controller.current=request
  setBusy(true);setError('');setResult(null)
  try{
   const response=await fetch(`${API}/${encodeURIComponent(seriesId)}/local-model-stream-probe`,{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({model}),signal:request.signal,
   })
   const payload=await response.json()
   if(!response.ok)throw Error(payload.detail||'Streaming diagnostic failed')
   if(!request.signal.aborted)setResult(payload as Diagnostic)
  }catch(cause){if(!request.signal.aborted)setError(String(cause))}
  finally{if(controller.current===request){controller.current=null;setBusy(false)}}
 }
 function cancel(){
  controller.current?.abort();controller.current=null
  setBusy(false)
  setError('Cancelled. Model request interrupted; no manuscript was sent.')
 }
 const metric=(value:number|null,unit='ms')=>value===null?'Not reported':value.toLocaleString()+' '+unit
 return <section className="story-stream-diagnostics" aria-label="Local inference streaming diagnostics">
  <div><strong>Measure local model startup and streaming</strong>
   <p>Use a synthetic one-sentence evidence check to distinguish first-token wait from model load and generation. Real manuscripts are never sent. Runs only when you click.</p></div>
  <div className="story-stream-actions">
   <button type="button" disabled={!model||busy} onClick={()=>void run()}>{busy?'Measuring response…':'Run 45-second streaming diagnostic'}</button>
   {busy&&<button type="button" onClick={cancel}>Cancel test</button>}
  </div>
  {error&&<p role="status">{error}</p>}
  {result&&<div className="story-stream-metrics" role="status">
   <strong>{result.status==='passed'?'Exact synthetic task passed':'Not verified — '+result.status}</strong>
   <p>{result.detail} · Stream complete: {result.stream_completed?'yes':'no'}</p>
   <dl>
    <div><dt>Time to first text</dt><dd>{metric(result.first_token_ms)}</dd></div>
    <div><dt>Request elapsed</dt><dd>{metric(result.elapsed_ms)}</dd></div>
    <div><dt>Model load</dt><dd>{metric(result.load_ms)}</dd></div>
    <div><dt>Prompt evaluation</dt><dd>{metric(result.prompt_eval_ms)}</dd></div>
    <div><dt>Generation</dt><dd>{metric(result.generation_ms)}</dd></div>
    <div><dt>Generated tokens</dt><dd>{metric(result.generated_tokens,'tokens')}</dd></div>
    <div><dt>Generation rate</dt><dd>{metric(result.tokens_per_second,'tokens/sec')}</dd></div>
   </dl>
   <small>{result.limitations}</small>
  </div>}
 </section>
}
