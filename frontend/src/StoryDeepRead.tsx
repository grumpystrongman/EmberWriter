import { useEffect, useState } from 'react'

type DiscoveryFact={
  subject_id:string;subject_name:string;predicate:string;object_text:string;
  object_entity_id:string|null;scope:string;knower_id:string|null;
  start_book:number;start_sequence:number;source_id:string;source_title:string;source_path:string;
  quote_start:number;quote_end:number;quote:string;confidence:string
}
type Suggestion={subject_id:string;subject_name:string;predicate:string;object_text:string;
  scope:string;knower_id:string|null;source_id:string;quote_start:number;quote_end:number;
  quote:string;start_book:number;start_sequence:number}
const API='http://127.0.0.1:8000/api'
export default function StoryDeepRead({seriesId,candidate,onStage}:{
  seriesId:string;candidate:DiscoveryFact;onStage:(candidate:DiscoveryFact)=>Promise<void>
}){
  const [models,setModels]=useState<string[]>([])
  const [model,setModel]=useState('')
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  const [suggestions,setSuggestions]=useState<Suggestion[]>([])
  const [discarded,setDiscarded]=useState(0)
  const [scanned,setScanned]=useState(false)
  useEffect(()=>{
    let current=true
    void fetch(`${API}/models`,{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({provider:'ollama',base_url:'http://127.0.0.1:11434',model:''})})
      .then(r=>r.json()).then(data=>{
        if(!current)return
        const local=(data.models||[]).filter((name:string)=>!/(?:^|[-:])(cloud|remote)(?:$|[-:])/i.test(name))
        setModels(local)
        setModel(local.find((m:string)=>m==='llama3.2:3b')||local[0]||'')
      }).catch(()=>{})
    return()=>{current=false}
  },[])
  useEffect(()=>{setSuggestions([]);setError('');setScanned(false)},[candidate.source_id,candidate.quote_start])
  async function analyze(){
    if(!model||busy)return
    setBusy(true);setError('');setSuggestions([]);setScanned(false)
    try{
      // Source excerpt is returned by the local backend from its checksum-
      // verified immutable snapshot, not from a client-provided model prompt.
      const query=encodeURIComponent(candidate.quote.slice(0,180))
      const excerptResponse=await fetch(`${API}/series/${seriesId}/sources/${candidate.source_id}/excerpt?query=${query}&limit=1600`)
      if(!excerptResponse.ok)throw Error('Could not retrieve verified source context')
      const excerpt=await excerptResponse.json() as {found:boolean;excerpt_start:number;excerpt_end:number}
      if(!excerpt.found)throw Error('The original quote is no longer present in the preserved source')
      const response=await fetch(`${API}/series/${seriesId}/sources/${candidate.source_id}/suggest`,{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({model,start:excerpt.excerpt_start,end:excerpt.excerpt_end}),
      })
      const body=await response.json()
      if(!response.ok)throw Error(body.detail||'Local model did not complete; original evidence is unchanged')
      setSuggestions(body.suggestions||[]);setDiscarded(body.discarded||0);setScanned(true)
    }catch(e){setError(String(e))}
    finally{setBusy(false)}
  }
  return <section className="discovery-deep-read" aria-label="Local AI deep reading">
    <div className="discovery-deep-heading"><span aria-hidden="true">✦</span><div>
      <strong>Deep Read</strong><p>Ask a local model to suggest additional facts from the surrounding passage. Suggestions never become canon without your review.</p>
    </div></div>
    <div className="discovery-deep-actions">
      <label>Local writing model
        <select value={model} onChange={e=>setModel(e.target.value)} disabled={busy}>
          {!models.length&&<option value="">No local models detected</option>}
          {models.map(name=><option key={name} value={name}>{name}</option>)}
        </select>
      </label>
      <button onClick={()=>void analyze()} disabled={busy||!model}>
        {busy?'Analyzing local source…':'Analyze surrounding passage'}
      </button>
    </div>
    {error&&<p role="alert" className="discovery-deep-error">{error}</p>}
    {scanned&&!suggestions.length&&<p className="discovery-deep-empty">No verifiable suggestions were returned. The original passage stays available for manual review.</p>}
    {suggestions.length>0&&<div className="discovery-deep-proposals">
      <strong>{suggestions.length} source-verifiable suggestions <small>· {discarded} discarded</small></strong>
      {suggestions.map((s,i)=><article key={s.source_id+':'+s.quote_start+':'+i}>
        <p><strong>{s.subject_name}</strong> {s.predicate.replace(/_/g,' ')} {s.object_text}</p>
        <blockquote>“{s.quote}”</blockquote>
        <span>{s.scope.replace(/_/g,' ')}</span>
        <button onClick={()=>void onStage({...candidate,...s,object_entity_id:null,
          source_title:candidate.source_title,source_path:candidate.source_path,confidence:'local_ai_review'})}>
          Stage as proposal ↗
        </button>
      </article>)}
    </div>}
  </section>
}
