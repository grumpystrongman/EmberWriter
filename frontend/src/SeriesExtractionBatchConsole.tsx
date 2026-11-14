import {useEffect,useRef,useState} from 'react'
import './series-extraction-batch-console.css'
import ReviewQueue from './ReviewQueue'
import type {QueueRow} from './ReviewQueue'

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
 const batch=batches.find(item=>item.id===selected)||batches[0]||null
 const rows:QueueRow[]=batches.map(item=>({
  key:item.id,title:item.model+' · '+item.source_count+' sources',
  subtitle:item.current_source_index+'/'+item.source_count+' sources finished',
  preview:item.processed_windows+' bounded windows attempted',status:item.status,
  meta:item.current_source_index===item.source_count?'Complete':'Ready to review',
 }))
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
 async function action(operation:'pause'|'resume'|'cancel',chosen?:Batch){
  const target=chosen||batch
  if(!target||busy)return
  setBusy(true);setError('')
  if(operation==='pause')stopRef.current=true
  try{
   const result=await request(`/${target.id}/${operation}`)
   update(result)
   setNotice('Batch is '+result.status+'. Each successfully processed source window retains its own checkpoint.')
  }catch(cause){setError(String(cause))}
  finally{setBusy(false)}
 }
 async function run(count:number,chosen?:Batch){
  const target=chosen||batch
  if(!target||stepping||busy||target.status!=='ready')return
  setStepping(true);setStop(false);stopRef.current=false;setError('');setNotice('')
  let current=target
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
    const r=await fetch(`${BASE}/${encodeURIComponent(seriesId)}/extraction-batches/${target.id}`)
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
  {batches.length>0&&<ReviewQueue title="Saved extraction plans"
   description="Select a checkpoint to inspect its progress and actions. Each manual step processes at most one source window."
   rows={rows} onSelectionChange={setSelected} emptyText="No saved extraction plans."
   detail={row=>{
    const current=batches.find(item=>item.id===row.key)
    if(!current)return null
    return <div className="series-batch-progress">
   <strong>{current.status.replaceAll('_',' ')} · {current.current_source_index}/{current.source_count} sources completed</strong>
   <progress max={current.source_count} value={current.current_source_index}/>
   <p>{current.processed_windows} bounded windows processed. {current.last_source?'Latest book '+current.last_source.book+', '+current.last_source.source_progress_percent+'% scanned.':'Last progress available from saved checkpoints.'}</p>
   <div className="series-batch-actions">
    <button disabled={busy||stepping||current.status!=='ready'} onClick={()=>{setSelected(current.id);void run(1,current)}}>Process next window</button>
    <button disabled={busy||stepping||current.status!=='ready'} onClick={()=>{setSelected(current.id);void run(3,current)}}>Process 3 and checkpoint</button>
    {(stepping||current.status==='ready'||current.status==='running')&&<button onClick={()=>{stopRef.current=true;setStop(true);setSelected(current.id);void action('pause',current)}} disabled={busy||stop}>Pause after current window</button>}
    {(current.status==='paused'||current.status==='error')&&<button disabled={busy||stepping} onClick={()=>{setSelected(current.id);void action('resume',current)}}>Resume</button>}
    {current.status!=='complete'&&current.status!=='cancelled'&&<button disabled={busy||stepping} onClick={()=>{setSelected(current.id);void action('cancel',current)}}>Cancel plan</button>}
   </div>
  </div>
   }}/>}
  {error&&<p role="alert">{error}</p>}
  {notice&&<p role="status">{notice}</p>}
 </details>
}
