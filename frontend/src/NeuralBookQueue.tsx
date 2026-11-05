import { useEffect, useRef, useState } from 'react'

type Chapter = {path:string; title:string; status:string; filename:string}
type Batch = {exists:boolean; status:string; id?:string; total:number; completed:number; stale?:boolean; stale_reason?:string;
  chapters?:Chapter[]; message?:string; publication_approved?:boolean}

export default function NeuralBookQueue({endpoint, disabled}: {endpoint:string;disabled:boolean}) {
  const [batch,setBatch] = useState<Batch|null>(null)
  const [working,setWorking] = useState(false)
  const [running,setRunning] = useState(false)
  const [error,setError] = useState('')
  const stop = useRef(false)
  const live = useRef(true)
  useEffect(()=>{
    live.current=true
    void fetch(endpoint+'/kokoro/book').then(r=>r.json() as Promise<Batch>)
      .then(s=>{if(live.current)setBatch(s)})
      .catch(e=>{if(live.current)setError(String(e))})
    return ()=>{live.current=false;stop.current=true}
  },[endpoint])
  async function request(path:string) {
    const response=await fetch(endpoint+path,{method:'POST'})
    const data=await response.json()
    if(!response.ok)throw new Error(data.detail||'Neural production request failed')
    return data as Batch
  }
  async function start() {
    setWorking(true);setError('')
    try {setBatch(await request('/kokoro/book'))}
    catch(e){setError(String(e))}
    finally{setWorking(false)}
  }
  async function produce() {
    stop.current=false;setRunning(true);setError('')
    try{
      let current=batch
      while(!stop.current && live.current && current?.status!=='completed'){
        current=await request('/kokoro/book/next')
        if(live.current)setBatch(current)
      }
    }catch(e){if(live.current)setError(String(e))}
    finally{if(live.current)setRunning(false)}
  }
  const total=batch?.total||0,completed=batch?.completed||0
  return <section className="neural-book-queue" aria-labelledby="neural-book-title">
    <div className="neural-book-heading">
      <span>OFFLINE · AUTHOR-DIRECTED</span>
      <h3 id="neural-book-title">Neural Audiobook Production</h3>
      <p>Generate your Binder Draft chapter by chapter with saved Kokoro voices. Every voice change and manuscript revision is checked before recording. All results are <strong>draft recordings awaiting your listening and approval</strong>.</p>
    </div>
    {error&&<p role="alert" className="audiobook-alert">{error}</p>}
    <div className="neural-book-progress">
      <strong>{completed} / {total} voice segments recorded</strong>
      <progress aria-label="Neural audiobook production" max={Math.max(total,1)} value={completed}/>
      <p role="status">{batch?.message || 'No neural audiobook job started.'}</p>
      {batch?.stale&&<p className="audiobook-alert" role="alert">Manuscript or casting changed: {batch.stale_reason}. Start a new batch after reviewing your edits. Existing audio remains saved but is not current.</p>}
    </div>
    <div className="audiobook-job-buttons">
      <button disabled={disabled||working||running||batch?.status==='queued'||batch?.status==='running'}
        onClick={()=>void start()}>Prepare a new Draft batch</button>
      <button disabled={disabled||working||running||!batch?.exists||batch.status==='completed'||!!batch.stale}
        onClick={()=>void produce()}>Generate remaining audiobook draft</button>
      {running&&<button onClick={()=>{stop.current=true}}>Pause after this segment</button>}
    </div>
    <p>The browser runs one short generation request at a time. Close it or pause safely; completed segments survive restart. Return here and select Generate remaining to resume. Starting a new batch replaces the active job reference, but previous WAV files remain in the project folder. No cloud API calls are made.</p>
    {batch?.chapters?.length ? <details>
      <summary>Listen to draft chapter recordings ({batch.chapters.filter(ch=>!!ch.filename).length} completed)</summary>
      <div className="neural-book-chapters">
      {batch.chapters.map(ch=><div key={ch.path}>
        <strong>{ch.title}</strong><small>{ch.status==='rendered_unapproved'?'Listen before approving':'Not yet rendered'} · {ch.path}</small>
        {ch.filename&&!batch.stale&&<><audio controls preload="none" aria-label={'Draft neural chapter '+ch.title}
          src={endpoint+'/kokoro/book/audio/'+encodeURIComponent(ch.filename)}/>
          <a download href={endpoint+'/kokoro/book/audio/'+encodeURIComponent(ch.filename)}>Save draft WAV</a></>}
      </div>)}
      </div>
    </details>:null}
    <p><strong>Release safeguard:</strong> This queue does not automatically approve takes, apply mastering, or include recordings in retail exports. Listening, corrections, and production sign-off are still required.</p>
  </section>
}
