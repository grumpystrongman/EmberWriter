import {useEffect,useRef,useState} from 'react'
import './series-extraction-batch-console.css'

type Batch={
 id:string;model:string;source_count:number;current_source_index:number;
 processed_windows:number;status:string;error:string;source_ids:string[];
 auto_canon_approved:boolean;last_source?:{book:number;source_progress_percent:number;candidate_count:number}
}
const BASE='http://127.0.0.1:8000/api/series'
export default function SeriesExtractionBatchConsole({seriesId,model}:{
 seriesId:string;model:string
}){
 const [from,setFrom]=useState(1)
 const [to,setTo]=useState(2)
 const [batches,setBatches]=useState<Batch[]>([])
 const [selected,setSelected]=useState<string|null>(null)
 const [busy,setBusy]=useState(false)
 const [stepping,setStepping]=useState(false)
 const [stop,setStop]=useState(false)
 const [error,setError]=useState('')
 const [notice,setNotice]=useState('')
 const stopRef=useRef(false)
 useEffect(()=>{
  stopRef.current=true
  const controller=new AbortController()
  setSelected(null);setBatches([]);setError('');setNotice('')
  void fetch(`${BASE}/${encodeURIComponent(seriesId)}/extraction-batches`,{signal:controller.signal})
   .then(async r=>{if(!r.ok)throw Error('Could not read batch checkpoints');return r.json() as Promise<Batch[]>})
   .then(rows=>{if(!controller.signal.aborted){setBatches(rows);setSelected(rows[0]?.id||null)}})
   .catch(e=>{if(!controller.signal.aborted)setError(String(e))})
  return()=>controller.abort()
 },[seriesId])
 const batch=batches.find(item=>item.id===selected)||null
 async function request(path:string,body?:object):Promise<Batch>{
  const r=await fetch(`${BASE}/${encodeURIComponent(seriesId)}/extraction-batches${path}`,{
   method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body||{}),
  })
  const payload=await r.json()
  if(!r.ok)throw Error(payload.detail||'Batch action failed')
  return payload as Batch
 }
 function update(value:Batch){
  setBatches(list=>[value,...list.filter(item=>item.id!==value.id)])
  setSelected(value.id)
 }
 async function prepare(){
  if(busy||stepping||!model)return
  setBusy(true);setError('');setNotice('')
  try{
   const result=await request('',{model,book_from:from,book_to:to})
   update(result)
   setNotice('Book plan saved locally. Nothing has been sent to a model yet.')
  }catch(cause){setError(String(cause))}finally{setBusy(false)}
 }
 async function action(operation:'pause'|'resume'|'cancel'){
  if(!batch||busy)return
  setBusy(true);setError('')
  if(operation==='pause')stopRef.current=true
  try{
   const result=await request(`/${batch.id}/${operation}`)
   update(result)
   setNotice('Batch is '+result.status+'. Each successfully processed source window retains its own checkpoint.')
  }catch(cause){setError(String(cause))}
  finally{setBusy(false)}
 }
 async function run(count:number){
  if(!batch||stepping||busy||batch.status!=='ready')return
  setStepping(true);setStop(false);stopRef.current=false;setError('');setNotice('')
  let current=batch
  let completed=0
  try{
   for(let index=0;index<count;index++){
    if(stopRef.current||current.status!=='ready')break
    current=await request(`/${current.id}/next`)
    update(current)
    completed++
   }
   setNotice(`${completed} passage(s) attempted; every returned lead remains unapproved.`)
  }catch(cause){
   setError(String(cause))
   try{
    const r=await fetch(`${BASE}/${encodeURIComponent(seriesId)}/extraction-batches/${batch.id}`)
    if(r.ok)update(await r.json() as Batch)
   }catch{/* Preserve original problem */}
  }finally{setStepping(false);setStop(false)}
 }
 return <details className="series-extraction-batches">
  <summary>Durable multi-book extraction queue · review-only</summary>
  <p>Queue up to 80 imported sources. Processing happens only when you press Next or Process 3; passage checkpoints persist across restarts. All model leads require author review. Model accuracy is not certified.</p>
  <div className="series-batch-setup">
   <label>Starting book<input aria-label="Batch starting book" type="number" min={1} max={9999} value={from} onChange={e=>setFrom(Number(e.target.value))}/></label>
   <label>Ending book<input aria-label="Batch ending book" type="number" min={1} max={9999} value={to} onChange={e=>setTo(Number(e.target.value))}/></label>
   <button type="button" disabled={!model||busy||stepping||from<1||to<from} onClick={()=>void prepare()}>Prepare source range</button>
  </div>
  {batches.length>0&&<label>Saved plans
    <select aria-label="Saved extraction batches" value={selected||''} onChange={e=>setSelected(e.target.value)}>
     {batches.map(item=><option value={item.id} key={item.id}>{item.model} · {item.source_count} sources · {item.status} · {item.processed_windows} windows</option>)}
    </select>
  </label>}
  {batch&&<div className="series-batch-progress">
   <strong>{batch.status.replaceAll('_',' ')} · {batch.current_source_index}/{batch.source_count} sources completed</strong>
   <progress max={batch.source_count} value={batch.current_source_index}/>
   <p>{batch.processed_windows} bounded windows processed. {batch.last_source?'Latest book '+batch.last_source.book+', '+batch.last_source.source_progress_percent+'% scanned.':'No windows processed in this browser session.'}</p>
   <div className="series-batch-actions">
    <button disabled={busy||stepping||batch.status!=='ready'} onClick={()=>void run(1)}>Process next window</button>
    <button disabled={busy||stepping||batch.status!=='ready'} onClick={()=>void run(3)}>Process 3 and checkpoint</button>
    {(stepping||batch.status==='ready'||batch.status==='running')&&<button onClick={()=>{stopRef.current=true;setStop(true);void action('pause')}} disabled={busy||stop}>Pause after current window</button>}
    {(batch.status==='paused'||batch.status==='error')&&<button disabled={busy||stepping} onClick={()=>void action('resume')}>Resume</button>}
    {batch.status!=='complete'&&batch.status!=='cancelled'&&<button disabled={busy||stepping} onClick={()=>void action('cancel')}>Cancel plan</button>}
   </div>
  </div>}
  {error&&<p role="alert">{error}</p>}
  {notice&&<p role="status">{notice}</p>}
 </details>
}
