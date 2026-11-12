import { useCallback, useEffect, useMemo, useState } from 'react'
import './story-discovery.css'
import StoryDeepRead from './StoryDeepRead'

type Candidate={
  subject_id:string;subject_name:string;predicate:string;object_text:string;
  object_entity_id:string|null;scope:string;knower_id:string|null;
  start_book:number;start_sequence:number;source_id:string;source_title:string;source_path:string;
  quote_start:number;quote_end:number;quote:string;confidence:string
}
type Results={ candidates:Candidate[]; total:number; offset:number; scanned_sources:number;
  skipped_large_sources:number; truncated:boolean; caveat:string }
type Entity={id:string;name:string;kind:string}
const BASE='http://127.0.0.1:8000/api/series'
const label=(value:string)=>value.replace(/_/g,' ')
export default function StoryDiscovery({seriesId,book,entities,onSaved,onOpenCanon}:{
  seriesId:string;book:number;entities:Entity[];onSaved:()=>void;onOpenCanon:()=>void
}){
  const [scope,setScope]=useState<'all'|'book'>('all')
  const [data,setData]=useState<Results|null>(null)
  const [query,setQuery]=useState('')
  const [selected,setSelected]=useState<string|null>(null)
  const [staging,setStaging]=useState<string|null>(null)
  const [error,setError]=useState('')
  const [notice,setNotice]=useState('')
  const [busy,setBusy]=useState(false)
  const [refresh,setRefresh]=useState(0)
  useEffect(()=>{
    const controller=new AbortController()
    setBusy(true);setError('')
    const params=new URLSearchParams({limit:'250'})
    if(scope==='book')params.set('book',String(book))
    void fetch(`${BASE}/${encodeURIComponent(seriesId)}/discover?${params}`,{signal:controller.signal})
      .then(async r=>{if(!r.ok)throw Error(await r.text());return r.json() as Promise<Results>})
      .then(result=>{if(!controller.signal.aborted){setData(result);setSelected(null)}})
      .catch(e=>{if(!controller.signal.aborted)setError(String(e))})
      .finally(()=>{if(!controller.signal.aborted)setBusy(false)})
    return()=>controller.abort()
  },[seriesId,book,scope,refresh])
  const filtered=useMemo(()=>data?.candidates.filter(c=>
    `${c.subject_name} ${c.predicate} ${c.object_text} ${c.quote} ${c.source_title}`
      .toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()))||[],[data,query])
  const active=filtered.find(c=>c.source_id+':'+c.quote_start===selected)||filtered[0]||null
  const key=(c:Candidate)=>c.source_id+':'+c.quote_start
  async function stage(c:Candidate){
    setStaging(key(c));setError('');setNotice('')
    try{
      const response=await fetch(`${BASE}/${encodeURIComponent(seriesId)}/assertions`,{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({
          subject_id:c.subject_id,predicate:c.predicate,object_text:c.object_text,
          object_entity_id:c.object_entity_id,scope:c.scope,knower_id:c.knower_id,
          start_book:c.start_book,start_sequence:c.start_sequence,source_id:c.source_id,
          quote_start:c.quote_start,quote_end:c.quote_end,quote:c.quote,
          note:'Literal candidate from whole-source discovery. Review carefully before approval.',
        }),
      })
      if(!response.ok)throw Error(await response.text())
      setNotice('Evidence staged as a proposed fact. It is not canon until you approve it.')
      setRefresh(n=>n+1)
      onSaved()
    }catch(e){setError(String(e))}
    finally{setStaging(null)}
  }
  return <div className="discovery-workspace" aria-label="Whole manuscript evidence discovery">
    <header className="discovery-intro">
      <div><span className="discovery-eyebrow">MANUSCRIPT DISCOVERY / AUTHOR CONTROL</span>
        <h3>Let the story reveal itself.</h3>
        <p>Search every imported book for concrete, source-backed statements. Read the original sentence, inspect its context, and choose what deserves review. Nothing is accepted automatically.</p></div>
      <div className="discovery-score"><strong>{data?.total??'—'}</strong><span>unreviewed leads</span></div>
    </header>
    <div className="discovery-controls">
      <label className="discovery-search"><span>Search discoveries</span>
        <input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Try a character, object, promise, or place…"/></label>
      <div className="discovery-scope" role="group" aria-label="Source scan scope">
        <button aria-pressed={scope==='all'} onClick={()=>setScope('all')}>Entire series</button>
        <button aria-pressed={scope==='book'} onClick={()=>setScope('book')}>Book {book}</button>
      </div>
      <button className="discovery-rescan" onClick={()=>setRefresh(v=>v+1)} disabled={busy}>↻ Refresh evidence</button>
    </div>
    {error&&<p className="discovery-error" role="alert">{error}</p>}
    {notice&&<p className="discovery-notice" role="status">{notice} <button onClick={onOpenCanon}>Review in Canon Graph ↗</button></p>}
    <div className="discovery-summary"><span>{data?.scanned_sources||0} source snapshots scanned</span><span>{filtered.length} leads in view</span><span>Proposals require deliberate author approval</span></div>
    <div className="discovery-layout">
      <div className="discovery-ledger" aria-label="Candidate source statements">
        {busy&&<p className="discovery-empty">Reading immutable source snapshots…</p>}
        {!busy&&!filtered.length&&<div className="discovery-empty">
          <strong>No matching literal evidence yet.</strong>
          <p>This scanner deliberately avoids guessing when prose is ambiguous. Expand your search or use the Canon Graph for source-specific review.</p>
          <button onClick={onOpenCanon}>Open Canon Graph</button>
        </div>}
        {!busy&&filtered.map((c,i)=><button className="discovery-lead" aria-pressed={key(c)===key(active!)}
          key={key(c)} type="button" onClick={()=>setSelected(key(c))}>
          <span className="discovery-lead-index">{String(i+1).padStart(2,'0')}</span>
          <div className="discovery-lead-body">
            <small>BOOK {c.start_book} / {c.source_title}</small>
            <strong>{c.subject_name} <em>{label(c.predicate)}</em> {c.object_text}</strong>
            <p>“{c.quote}”</p>
          </div>
          <span className="discovery-lead-arrow" aria-hidden="true">↗</span>
        </button>)}
        {data?.truncated&&<p className="discovery-empty">First 1,200 discovery candidates shown. Narrow the scan by book for more detail.</p>}
        {(data?.total||0)>250&&<p className="discovery-empty">Showing the first 250 leads. Choose a book to examine additional candidates; pagination is available through the API.</p>}
      </div>
      <aside className="discovery-inspector" aria-live="polite">
        {active?<div className="discovery-source-card">
          <span className="discovery-eyebrow">SOURCE EVIDENCE / NOT YET CANON</span>
          <div className="discovery-subject-icon">{active.subject_name.slice(0,1)}</div>
          <h4>{active.subject_name}</h4>
          <p className="discovery-relationship">{label(active.predicate)} <strong>{active.object_text}</strong></p>
          <div className="discovery-evidence">
            <span>EXACT MANUSCRIPT QUOTE</span>
            <blockquote>“{active.quote}”</blockquote>
            <small>{active.source_title} · {active.source_path}</small>
            <small>Characters {active.quote_start}–{active.quote_end}</small>
          </div>
          <div className="discovery-evidence-details">
            <div><span>Classification</span><strong>Literal pattern match</strong></div>
            <div><span>Knowledge lens</span><strong>Candidate world claim</strong></div>
            <div><span>First appears</span><strong>Book {active.start_book}</strong></div>
          </div>
          <p className="discovery-caution">This is an unverified sentence-level candidate. Figurative language, unreliable narrators, and context may change its meaning.</p>
          <button className="discovery-stage-button" disabled={!!staging} onClick={()=>void stage(active)}>
            {staging===key(active)?'Staging evidence…':'Add to author review →'}
          </button>
          <button className="discovery-secondary-button" onClick={onOpenCanon}>Open Canon Graph</button>
          <StoryDeepRead seriesId={seriesId} candidate={active} onStage={stage} />
        </div>:<p className="discovery-empty">Select a discovered statement to inspect its original source.</p>}
      </aside>
    </div>
  </div>
}
