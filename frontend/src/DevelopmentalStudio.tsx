import { useEffect, useMemo, useState } from 'react'
import './developmental-studio.css'

type Evidence={line:number;excerpt:string}
type Chapter={
  index:number;path:string;title:string;status:string;words:number;word_share:number;
  average_sentence_words:number;dialogue_passages:number;mechanical_flags:number;
  editable:boolean;review_prompts:{kind:string;label:string;question:string;quote:string;line:number;path:string}[];
  tracked_subjects:{name:string;evidence:Evidence[]}[];
  diagnostics:{kind:string;label:string;evidence:string}[]
}
type Alert={id:string;kind:string;label:string;detail:string;references:string[];confidence:string}
type PromiseRow={id:string;title:string;tracking_phrase:string;status:string;reference_count:number;resolution_note:string}
type Overview={chapters:Chapter[];total_words:number;chapter_count:number;average_chapter_words:number;
  subject_presence:{name:string;chapters:{path:string;title:string;index:number;evidence:Evidence[]}[]}[];
  alerts:Alert[];promises:PromiseRow[];limitations:string;local_only:boolean}
type Paragraph={id:string;start:number;end:number;text:string;words:number;line:number;dialogue:number;transition_cues:number}
type Document={path:string;content:string;source_hash:string;paragraphs:Paragraph[];words:number;
  dialogue_passages:number;revision_history:{id:string;created_at:string;source:string;note:string;word_count:number;content_hash:string}[]}
type DialogueReport={path:string;source_hash:string;quote_count:number;attributed_count:number;unattributed_count:number;
  profiles:{name:string;quote_count:number;total_words:number;mean_quote_words:number;
    lexical_signatures:{word:string;frequency:number}[];quotes:{id:string;text:string;line:number;words:number}[];caveat:string}[];
  timeline:{id:string;speaker:string;text:string;line:number}[];limitations:string}
type Mode='pulse'|'arcs'|'dialogue'|'revisions'
const PERSPECTIVES=[{id:'pulse',icon:'▥',name:'Manuscript Pulse',detail:'Pacing, voice patterns and chapter shape'},
  {id:'arcs',icon:'✧',name:'Arc & Promise Atlas',detail:'Character presence and unresolved narrative promises'},
  {id:'dialogue',icon:'❝',name:'Dialogue Studio',detail:'Compare actual voices and speaking patterns'},
  {id:'revisions',icon:'◫',name:'Revision Workbench',detail:'Compare, selectively approve and preserve the original'}] as const

const API=(base:string,slug:string)=>`${base}/projects/${encodeURIComponent(slug)}/developmental-editor`
async function request<T>(url:string,options?:RequestInit):Promise<T>{
  const response=await fetch(url,options)
  const body=await response.json().catch(()=>({}))
  if(!response.ok)throw Error(typeof body.detail==='string'?body.detail:`Request failed: ${response.status}`)
  return body as T
}
function makeRequest(data:unknown):RequestInit{
  return {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}
}
function proportional(value:number,max:number){return Math.max(4,Math.round(100*value/Math.max(1,max)))}
function number(value:number){return value.toLocaleString()}

export default function DevelopmentalStudio({apiBase,projectSlug,onOpenSource,onOpenEditorTool}:{
  apiBase:string;projectSlug:string;onOpenSource:(path:string)=>void;
  onOpenEditorTool:(tool:'story_arcs'|'voiceprint'|'editorial_board'|'prose_editor',path:string)=>void
}){
  const endpoint=API(apiBase,projectSlug)
  const [mode,setMode]=useState<Mode>(()=>{
    try{
      const requested=sessionStorage.getItem('emberwriter:editorial-mode:'+projectSlug)
      sessionStorage.removeItem('emberwriter:editorial-mode:'+projectSlug)
      if(requested==='pulse'||requested==='arcs'||requested==='dialogue'||requested==='revisions')return requested
    }catch{/* Use default mode */}
    return 'pulse'
  })
  const [overview,setOverview]=useState<Overview|null>(null)
  const [query,setQuery]=useState('')
  const [subjects,setSubjects]=useState<string[]>([])
  const [chapterPath,setChapterPath]=useState('')
  const [document,setDocument]=useState<Document|null>(null)
  const [dialogue,setDialogue]=useState<DialogueReport|null>(null)
  const [speaker,setSpeaker]=useState<string>('')
  const [drafts,setDrafts]=useState<Record<string,string>>({})
  const [approved,setApproved]=useState<string[]>([])
  const [focused,setFocused]=useState<string|null>(null)
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  const [notice,setNotice]=useState('')
  const [filter,setFilter]=useState<'all'|'mechanics'|'outliers'>('all')
  const [confirmation,setConfirmation]=useState(false)
  const [restoreTarget,setRestoreTarget]=useState<string|null>(null)
  const [showUnchanged,setShowUnchanged]=useState(true)

  const candidates=useMemo(()=>overview?.chapters.filter(ch=>ch.editable)||[],[overview])
  const selectedChapter=overview?.chapters.find(ch=>ch.path===chapterPath)||null
  const changed=useMemo(()=>document?.paragraphs.filter(p=>drafts[p.id]!==undefined&&drafts[p.id]!==p.text)||[],[document,drafts])
  const selectedChanges=changed.filter(p=>approved.includes(p.id))
  const activeVoice=dialogue?.profiles.find(profile=>profile.name===speaker)||dialogue?.profiles[0]||null
  const maxWords=Math.max(1,...(overview?.chapters.map(c=>c.words)||[]))
  const filtered=overview?.chapters.filter(ch=>filter==='all'
    ||(filter==='mechanics'&&ch.mechanical_flags>0)
    ||(filter==='outliers'&&ch.diagnostics.some(d=>d.kind==='length')))||[]

  async function scan(nextSubjects=subjects){
    setBusy(true);setError('');setNotice('')
    try{
      const params=new URLSearchParams()
      nextSubjects.forEach(term=>params.append('subjects',term))
      const result=await request<Overview>(endpoint+'/overview?'+params)
      setOverview(result)
      setSubjects(nextSubjects)
      if(!chapterPath||!result.chapters.some(ch=>ch.path===chapterPath&&ch.editable)){
        setChapterPath(result.chapters.find(ch=>ch.editable)?.path||'')
        setDocument(null);setApproved([]);setDrafts({})
      }
    }catch(e){setError(String(e))}
    finally{setBusy(false)}
  }
  useEffect(()=>{
    let active=true
    setOverview(null);setDocument(null);setDrafts({});setApproved([]);setError('')
    void request<Overview>(endpoint+'/overview').then(result=>{
      if(!active)return
      setOverview(result);setChapterPath(result.chapters.find(ch=>ch.editable)?.path||'')
    }).catch(e=>{if(active)setError(String(e))})
    return()=>{active=false}
  },[endpoint])
  useEffect(()=>{
    if(mode!=='dialogue'||!chapterPath){setDialogue(null);return}
    const controller=new AbortController()
    setDialogue(null);setSpeaker('')
    void request<DialogueReport>(endpoint+'/dialogue?'+new URLSearchParams({path:chapterPath}),
      {signal:controller.signal})
      .then(result=>{if(!controller.signal.aborted){setDialogue(result);setSpeaker(result.profiles[0]?.name||'')}})
      .catch(e=>{if(!controller.signal.aborted)setError(String(e))})
    return()=>controller.abort()
  },[mode,chapterPath,endpoint])
  async function openDocument(path:string){
    if(!path)return
    setBusy(true);setError('')
    try{
      const item=await request<Document>(endpoint+'/document?'+new URLSearchParams({path}))
      setDocument(item);setChapterPath(path);setDrafts({});setApproved([]);setFocused(null);setConfirmation(false);setRestoreTarget(null)
    }catch(e){setError(String(e))}
    finally{setBusy(false)}
  }
  async function accept(){
    if(!document||!selectedChanges.length||busy)return
    setBusy(true);setError('');setConfirmation(false)
    try{
      const result=await request<{edited_paragraphs:number;snapshot_id:string;before_revision:string;after_revision:string}>(
        endpoint+'/apply',makeRequest({
          path:document.path,source_hash:document.source_hash,
          edits:selectedChanges.map(p=>({id:p.id,replacement:drafts[p.id]})),
        }))
      setNotice(`${result.edited_paragraphs} paragraph change(s) accepted. The original was archived and recorded in revision history.`)
      await openDocument(document.path)
      await scan()
      setNotice('Accepted paragraph changes were saved. The previous manuscript was archived and the revision is recorded.')
    }catch(e){setError(String(e))}
    finally{setBusy(false)}
  }
  async function restoreVersion(){
    if(!document||!restoreTarget||busy)return
    setBusy(true);setError('')
    try{
      await request(endpoint+'/restore',makeRequest({
        path:document.path,source_hash:document.source_hash,revision_id:restoreTarget,
      }))
      await openDocument(document.path)
      await scan()
      setNotice('An earlier manuscript version was restored. The overwritten chapter was archived as another recoverable version.')
    }catch(e){setError(String(e))}
    finally{setBusy(false);setRestoreTarget(null)}
  }
  function selectChapter(path:string){
    setChapterPath(path)
    setDocument(null);setDrafts({});setApproved([]);setFocused(null);setConfirmation(false)
    if(mode==='revisions')void openDocument(path)
  }
  function edit(p:Paragraph,value:string){
    setDrafts(old=>({...old,[p.id]:value}))
    setApproved(old=>old.filter(id=>id!==p.id))
    setConfirmation(false)
  }
  function toggleSelection(id:string){
    setApproved(old=>old.includes(id)?old.filter(x=>x!==id):[...old,id])
    setConfirmation(false)
  }
  return <section className="devstudio" aria-label="Developmental editing studio">
    <header className="devstudio-hero">
      <div className="devstudio-eyebrow">THE AUTHOR'S EDITORIAL ATELIER</div>
      <div className="devstudio-hero-line"><div>
        <h2>See the book beneath the words.</h2>
        <p>Read the manuscript's shape. Trace the promises you've made. Refine only what you choose—without losing the prose you started with.</p>
      </div><div className="devstudio-hero-actions">
         <button type="button" onClick={()=>setMode('pulse')}>Explore chapters</button>
         <button type="button" onClick={()=>setMode('revisions')}>Revise a chapter</button>
       </div></div>
      <nav className="devstudio-nav" aria-label="Editorial workspaces">{PERSPECTIVES.map(item=>
        <button key={item.id} type="button" aria-pressed={mode===item.id} onClick={()=>{setMode(item.id);setNotice('');setError('')}}>
          <span aria-hidden="true">{item.icon}</span><strong>{item.name}</strong><small>{item.detail}</small>
        </button>)}</nav>
    </header>
    {error&&<div className="devstudio-message devstudio-error" role="alert">{error}</div>}
    {notice&&<div className="devstudio-message" role="status">{notice}</div>}
    {!overview?<div className="devstudio-loading" role="status">{busy?'Reading your manuscript…':'Loading editorial evidence…'}</div>:<>
      <div className="devstudio-overview-stats" aria-label="Manuscript summary">
        <div><span>MANUSCRIPT WORDS</span><strong>{number(overview.total_words)}</strong></div>
        <div><span>CHAPTERS</span><strong>{overview.chapter_count}</strong></div>
        <div><span>AVG CHAPTER</span><strong>{number(overview.average_chapter_words)}</strong></div>
        <div><span>OPEN PROMISES</span><strong>{overview.promises.filter(p=>p.status==='open').length}</strong></div>
        <button type="button" disabled={busy} onClick={()=>void scan()}><span>↻</span> Rescan manuscript</button>
      </div>

      {mode==='pulse'&&<div className="devstudio-pulse">
        <div className="devstudio-section-intro"><div><span>MANUSCRIPT HEALTH</span><h3>The rhythm of your draft.</h3><p>Look for chapters that deserve a closer reading. These are descriptive measurements, not arbitrary quality grades.</p></div>
          <div className="devstudio-filter" role="group" aria-label="Filter chapters">
            {([['all','All'],['mechanics','Mechanical flags'],['outliers','Length outliers']] as const).map(([id,label])=>
              <button key={id} type="button" aria-pressed={filter===id} onClick={()=>setFilter(id)}>{label}</button>)}
          </div></div>
        <div className="devstudio-pulse-layout">
          <section className="devstudio-heatmap" aria-label="Clickable chapter pulse">
            <div className="devstudio-smallhead"><strong>THE CHAPTER RIVER</strong><small>Height reflects words, not quality</small></div>
            <div className="devstudio-bars">
              {filtered.map(ch=><button type="button" key={ch.path}
                aria-pressed={chapterPath===ch.path}
                aria-label={`Open ${ch.title}, ${ch.words} words, ${ch.mechanical_flags} mechanical flags`}
                onClick={()=>selectChapter(ch.path)}>
                <span className="devstudio-bar-body" style={{height:proportional(ch.words,maxWords)+'%'}}/>
                <strong>{ch.index.toString().padStart(2,'0')}</strong>
              </button>)}
            </div>
            <div className="devstudio-heatmap-legend"><span>SHORTER</span><span>RELATIVE CHAPTER LENGTH</span><span>LONGER</span></div>
            {!filtered.length&&<p className="devstudio-muted">No chapters match this filter.</p>}
          </section>
          <aside className="devstudio-chapter-inspector">
            {selectedChapter?<><span>CHAPTER {selectedChapter.index} · {selectedChapter.status.toUpperCase()}</span>
              <h4>{selectedChapter.title}</h4>
              <div className="devstudio-chapter-metrics"><div><strong>{number(selectedChapter.words)}</strong><small>words</small></div>
                <div><strong>{selectedChapter.average_sentence_words}</strong><small>avg sentence words</small></div>
                <div><strong>{selectedChapter.mechanical_flags}</strong><small>mechanical flags</small></div></div>
              {selectedChapter.diagnostics.length?<div className="devstudio-diagnostics">{selectedChapter.diagnostics.map((d,i)=>
                <article key={i}><span>{d.kind.toUpperCase()}</span><strong>{d.label}</strong><small>{d.evidence}</small></article>)}</div>:
                <p className="devstudio-muted">No mechanical or relative-length outliers were detected here. That does not establish story quality.</p>}
              {selectedChapter.review_prompts?.length>0&&<div className="devstudio-review-questions">
                <span>DEVELOPMENTAL READING PROMPTS</span>
                {selectedChapter.review_prompts.map((prompt,i)=><article key={i}>
                  <strong>{prompt.label}</strong><p>{prompt.question}</p>
                  <blockquote>“{prompt.quote}”</blockquote>
                  <button type="button" disabled={!selectedChapter.editable} onClick={()=>onOpenSource(prompt.path)}>
                    Read chapter · line {prompt.line} ↗
                  </button>
                </article>)}
              </div>}
              {selectedChapter.editable&&<button className="devstudio-primary" type="button" onClick={()=>{setMode('revisions');void openDocument(selectedChapter.path)}}>Open revision canvas ↗</button>}
              <button className="devstudio-link" type="button" onClick={()=>onOpenSource(selectedChapter.path)} disabled={!selectedChapter.editable}>Open source chapter →</button>
              <div className="devstudio-editor-links">
                <span>MORE EDITORIAL INSTRUMENTS</span>
                <button type="button" onClick={()=>onOpenEditorTool('story_arcs',selectedChapter.path)}>
                  ✧ Deep narrative inspection <small>Evidence-checked analysis using a local model</small>
                </button>
                <button type="button" onClick={()=>onOpenEditorTool('prose_editor',selectedChapter.path)}>
                  ◈ Sentence & dialogue cleanup <small>Review source-backed prose findings</small>
                </button>
                <button type="button" onClick={()=>onOpenEditorTool('editorial_board',selectedChapter.path)}>
                  ▥ Whole-book editorial queue <small>Prioritize existing suggestions</small>
                </button>
                <button type="button" onClick={()=>onOpenEditorTool('voiceprint',selectedChapter.path)}>
                  ❝ Author voice fingerprint <small>Compare your writing with a reference sample</small>
                </button>
              </div>
            </>:<p>Select a chapter in the river to inspect it.</p>}
          </aside>
        </div>
        <div className="devstudio-section-intro"><div><span>MANUSCRIPT SIGNALS</span><h3>Patterns worth investigating.</h3><p>Recurring phrases and unresolved author-tracked promises, with direct chapter references.</p></div></div>
        <div className="devstudio-alerts">{overview.alerts.length?overview.alerts.slice(0,18).map(alert=>
          <article key={alert.id}><div className="devstudio-alert-glyph">{alert.kind==='plot'?'◇':'❝'}</div>
            <div><span>{alert.kind==='plot'?'PLOT PROMISE':'REPETITION'} · {alert.confidence}</span>
              <h4>{alert.label}</h4><p>{alert.detail}</p><div>{alert.references.slice(0,5).map(path=>
                <button key={path} type="button" onClick={()=>selectChapter(path)}>{overview.chapters.find(c=>c.path===path)?.title||path} ↗</button>)}</div></div>
          </article>):<p className="devstudio-muted">No repeated cross-chapter phrases or open tracked promises detected.</p>}</div>
      </div>}

      {mode==='arcs'&&<div className="devstudio-arcspace">
        <div className="devstudio-section-intro"><div><span>THE ARC & PROMISE ATLAS</span><h3>Follow the narrative threads.</h3><p>Track named characters and motifs across chapters. Presence alone never proves a meaningful arc or earned payoff.</p></div></div>
        <form className="devstudio-track-form" onSubmit={e=>{e.preventDefault();void scan(query.split(',').map(x=>x.trim()).filter(Boolean))}}>
          <label>Characters, objects, and motifs to follow
            <input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Mira, the glass compass, Rowan"/>
          </label><button type="submit" disabled={busy}>✧ Trace through the book</button>
        </form>
        {overview.subject_presence.length?<div className="devstudio-presence">
          <div className="devstudio-smallhead"><strong>CHARACTER & MOTIF PRESENCE</strong><small>Each mark has a cited passage</small></div>
          <div className="devstudio-presence-scroll"><table><thead><tr><th>TRACKED SUBJECT</th>{overview.chapters.map(ch=><th key={ch.path} title={ch.title}>{ch.index.toString().padStart(2,'0')}</th>)}</tr></thead><tbody>
            {overview.subject_presence.map(subject=><tr key={subject.name}><th>{subject.name}</th>{subject.chapters.map(ch=>
              <td key={ch.path}><button type="button" aria-label={`${subject.name}: ${ch.evidence.length} citations in ${ch.title}`}
                className={ch.evidence.length?'present':'absent'} disabled={!ch.evidence.length}
                onClick={()=>{selectChapter(ch.path);setFocused(subject.name)}}>{ch.evidence.length?'✦':'·'}</button></td>)}</tr>)}
          </tbody></table></div>
          {focused&&<div className="devstudio-evidence-drawer"><h4>{focused} · Chapter evidence</h4>
            {overview.subject_presence.find(s=>s.name===focused)?.chapters.filter(ch=>ch.path===chapterPath).flatMap(ch=>ch.evidence).map((hit,i)=>
              <blockquote key={i}>Line {hit.line}: “{hit.excerpt}”</blockquote>)}
            <button type="button" onClick={()=>onOpenSource(chapterPath)}>Open source ↗</button>
          </div>}
        </div>:<div className="devstudio-empty">Choose a character or motif to trace where it appears in the story. No biography or motivation will be invented.</div>}
        <div className="devstudio-section-intro"><div><span>AUTHOR-OWNED PROMISES</span><h3>What must the story eventually deliver?</h3></div></div>
        <div className="devstudio-promise-grid">{overview.promises.length?overview.promises.map(item=><article key={item.id}>
          <span>{item.status.toUpperCase()} · {item.reference_count} CHAPTER(S)</span><h4>{item.title}</h4><p>Tracking phrase: “{item.tracking_phrase}”</p>
          {item.resolution_note&&<blockquote>{item.resolution_note}</blockquote>}
        </article>):<div className="devstudio-empty">No author-tracked promises yet. Add them in Manuscript Intelligence; they will appear here with their evidence.</div>}</div>
        <p className="devstudio-caveat">{overview.limitations}</p>
      </div>}

      {mode==='dialogue'&&<div className="devstudio-dialogue">
        <div className="devstudio-section-intro"><div><span>THE DIALOGUE STUDIO</span><h3>Listen to the people on the page.</h3>
          <p>See actual quoted speech, identifiable speaker tags and recurring vocabulary. This is a voice comparison instrument, not a machine verdict about authenticity.</p></div></div>
        <div className="devstudio-revision-toolbar"><label>Examine chapter
          <select value={chapterPath} onChange={e=>selectChapter(e.target.value)}>
            {!candidates.length&&<option value="">No editable chapters available</option>}
            {candidates.map(ch=><option key={ch.path} value={ch.path}>{ch.index}. {ch.title}</option>)}
          </select></label>
          <button type="button" disabled={!chapterPath||busy} onClick={()=>{setDialogue(null);setSpeaker('');void request<DialogueReport>(endpoint+'/dialogue?'+new URLSearchParams({path:chapterPath})).then(result=>{setDialogue(result);setSpeaker(result.profiles[0]?.name||'')}).catch(e=>setError(String(e)))}}>Refresh dialogue ↻</button>
        </div>
        {dialogue?<div className="devstudio-dialogue-body">
          <div className="devstudio-dialogue-stats">
            <div><span>QUOTED PASSAGES</span><strong>{dialogue.quote_count}</strong></div>
            <div><span>EXPLICITLY TAGGED</span><strong>{dialogue.attributed_count}</strong></div>
            <div><span>UNATTRIBUTED</span><strong>{dialogue.unattributed_count}</strong></div>
          </div>
          <div className="devstudio-voice-cast" role="group" aria-label="Compare speaker excerpts">
            {dialogue.profiles.map((profile,i)=><button type="button" key={profile.name} aria-pressed={activeVoice?.name===profile.name}
              onClick={()=>setSpeaker(profile.name)}>
              <span className="devstudio-voice-seal" aria-hidden="true">{profile.name.slice(0,1)}</span>
              <strong>{profile.name}</strong><small>{profile.quote_count} quoted passage(s)</small>
            </button>)}
          </div>
          {activeVoice&&<div className="devstudio-voice-detail">
            <aside><span>SPEAKER STUDY</span><h4>{activeVoice.name}</h4>
              <p>{activeVoice.caveat}</p>
              <div className="devstudio-voice-metrics"><div><strong>{activeVoice.total_words}</strong><small>quoted words</small></div>
                <div><strong>{activeVoice.mean_quote_words}</strong><small>mean words per quote</small></div></div>
              <h5>Recurring words in these quotations</h5>
              <div className="devstudio-voice-terms">{activeVoice.lexical_signatures.map(term=><span key={term.word}>{term.word} <small>×{term.frequency}</small></span>)}</div>
              <p>Coaching question: What do this character's vocabulary, sentence rhythm, choices and silences reveal that other speakers would not?</p>
            </aside>
            <section><div className="devstudio-smallhead"><strong>ORIGINAL SPOKEN EVIDENCE</strong><small>Exact text and source line</small></div>
              {activeVoice.quotes.map(quote=><article key={quote.id}><span>LINE {quote.line} · {quote.words} WORDS</span>
                <blockquote>{quote.text}</blockquote>
                <button type="button" onClick={()=>onOpenSource(chapterPath)}>Open quoted source ↗</button>
              </article>)}
            </section>
          </div>}
          <div className="devstudio-dialogue-river"><div className="devstudio-smallhead"><strong>CONVERSATION RIVER</strong><small>Order of quotes as they appear on the page</small></div>
            <div>{dialogue.timeline.map((utterance,index)=><button type="button" key={utterance.id}
              aria-label={`Quote ${index+1}, ${utterance.speaker}, line ${utterance.line}`}
              onClick={()=>setSpeaker(utterance.speaker)}
              aria-pressed={speaker===utterance.speaker}
              title={utterance.speaker+': '+utterance.text.slice(0,110)}>
              <span>{index+1}</span><strong>{utterance.speaker.slice(0,2)}</strong></button>)}</div>
          </div>
          <p className="devstudio-caveat">{dialogue.limitations}</p>
        </div>:<div className="devstudio-empty">{chapterPath?'Reading quoted dialogue from this chapter…':'Select a manuscript chapter to examine its dialogue.'}</div>}
      </div>}

      {mode==='revisions'&&<div className="devstudio-revision">
        <div className="devstudio-section-intro"><div><span>THE AUTHOR'S REVISION WORKBENCH</span><h3>Revise without surrendering the original.</h3><p>Edit individual paragraphs, inspect both versions, and explicitly approve the changes you want. Every accepted edit creates a recoverable manuscript snapshot and revision record.</p></div></div>
        <div className="devstudio-revision-toolbar">
          <label>Manuscript chapter<select value={chapterPath} onChange={e=>selectChapter(e.target.value)}>
            {!candidates.length&&<option value="">No editable manuscript chapters</option>}
            {candidates.map(ch=><option key={ch.path} value={ch.path}>{ch.index}. {ch.title}</option>)}
          </select></label>
          <button type="button" disabled={!chapterPath||busy} onClick={()=>void openDocument(chapterPath)}>{busy?'Opening…':'Load chapter →'}</button>
          <button type="button" disabled={!document||!changed.length} onClick={()=>{setDrafts({});setApproved([]);setConfirmation(false)}}>Discard unaccepted edits</button>
        </div>
        {document?<><div className="devstudio-revision-info">
          <div><span>ORIGINAL MANUSCRIPT</span><strong>{number(document.words)} words</strong></div>
          <div><span>PARAGRAPHS MODIFIED</span><strong>{changed.length}</strong></div>
          <div><span>SELECTED TO ACCEPT</span><strong>{selectedChanges.length}</strong></div>
          <div><span>PRESERVED REVISIONS</span><strong>{document.revision_history.length}</strong></div>
        </div>
          <div className="devstudio-revision-head"><div><strong>ORIGINAL</strong><small>Read-only preserved source</small></div>
            <div><strong>YOUR ALTERNATIVE</strong><small>Only selected changes are applied</small></div></div>
          <div className="devstudio-paragraphs">{document.paragraphs.map(p=>{
            const editText=drafts[p.id]??p.text
            const modified=editText!==p.text
            return showUnchanged||modified?<article className={'devstudio-paragraph'+(modified?' modified':'')} key={p.id}>
              <div className="devstudio-paragraph-meta"><span>¶ {p.id.slice(1)} · LINE {p.line}</span><span>{p.words} ORIGINAL WORDS · {p.dialogue} QUOTED PASSAGES</span></div>
              <div className="devstudio-paragraph-columns"><pre>{p.text}</pre>
                <textarea aria-label={`Edit paragraph ${p.id.slice(1)}`} value={editText} onChange={e=>edit(p,e.target.value)} rows={Math.max(3,Math.min(12,p.text.split('\n').length+2))} maxLength={20_000}/></div>
              <div className="devstudio-paragraph-controls">{modified?<><label><input type="checkbox" checked={approved.includes(p.id)} onChange={()=>toggleSelection(p.id)}/> Accept this paragraph change</label>
                <button type="button" onClick={()=>{setDrafts(old=>({...old,[p.id]:p.text}));setApproved(old=>old.filter(id=>id!==p.id))}}>Revert alternative</button></>:<span>Unchanged · your original remains intact</span>}</div>
            </article>:null
          })}</div>
          <div className="devstudio-revision-footer"><label><input type="checkbox" checked={showUnchanged} onChange={e=>setShowUnchanged(e.target.checked)}/> Show unchanged paragraphs</label>
            <div><strong>{selectedChanges.length} selected change(s)</strong><button className="devstudio-primary" type="button" disabled={!selectedChanges.length||busy} onClick={()=>setConfirmation(true)}>Review selected changes →</button></div>
          </div>
          {confirmation&&<div className="devstudio-confirmation" role="dialog" aria-label="Confirm manuscript edits">
            <strong>Apply {selectedChanges.length} paragraph change(s)?</strong>
            <p>Only checked changes will be written. The previous chapter is archived. If the source changed since you loaded it, the operation will be rejected.</p>
            <div><button type="button" disabled={busy} onClick={()=>void accept()} className="devstudio-primary">Yes, archive original and apply</button>
              <button type="button" onClick={()=>setConfirmation(false)}>Cancel</button></div>
          </div>}
          <details className="devstudio-history"><summary>Revision history · {document.revision_history.length} recorded versions</summary>
            {document.revision_history.map(rev=><div key={rev.id}><strong>{rev.source}</strong><span>{new Date(rev.created_at).toLocaleString()} · {rev.word_count} words</span>
              <small>{rev.note}</small>
              <button type="button" disabled={busy||rev.content_hash===document.source_hash}
                onClick={()=>{setRestoreTarget(rev.id);setConfirmation(false)}}>
                {rev.content_hash===document.source_hash?'Current text':'Restore this saved version ↶'}
              </button></div>)}
          </details>
          {restoreTarget&&<div className="devstudio-confirmation" role="dialog" aria-label="Restore saved manuscript version">
            <strong>Restore this earlier manuscript version?</strong>
            <p>The current chapter will be archived before restoration. Only this manuscript document changes, and restoration is rejected if the source has changed since you opened it.</p>
            <div><button type="button" className="devstudio-primary" disabled={busy} onClick={()=>void restoreVersion()}>Restore the selected version</button>
              <button type="button" onClick={()=>setRestoreTarget(null)}>Cancel</button></div>
          </div>}
        </>:<div className="devstudio-empty">{chapterPath?'Choose “Load chapter” to open its paragraph-by-paragraph revision canvas.':'This project has no independently editable manuscript documents. Book Studio candidates retain their own approval workflow.'}</div>}
      </div>}
      <footer className="devstudio-disclaimer"><span>LOCAL EVIDENCE · AUTHOR CONTROL</span>{overview.limitations}</footer>
    </>}
  </section>
}
