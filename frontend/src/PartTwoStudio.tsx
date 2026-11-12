import { useEffect, useMemo, useState } from 'react'
import type { CSSProperties, DragEvent } from 'react'
import './part-two-studio.css'

type Entity = {id:string;name:string;kind:string;description:string;aliases:string[]}
type Fact = {
  id:string;subject_id:string;subject_name:string;object_entity_id?:string|null;
  object_name:string|null;object_text:string;predicate:string;scope:string;status:string;
  start_book:number;start_sequence?:number;end_book:number|null;end_sequence?:number|null;
  quote:string;reference:{source_id?:string;volume:string;source_path:string;book:number;start:number;end:number}
}
type Volume = {id:string;title:string;ordinal:number}
type Beat = {id:string;kind:BeatKind;title:string;detail:string;pressure:number}
type BeatKind = 'arrival'|'spark'|'obstacle'|'reversal'|'choice'|'aftermath'
type Board = {id:string;version:number;created_at:string;updated_at:string;title:string;book:number;
  sequence:number;objective:string;conflict:string;opening:string;aftermath:string;voice_notes:string;
  pov_id:string|null;location_id:string|null;participants:string[];beats:Beat[]}
type StudioView = 'characters'|'relationships'|'scenes'
const API='http://127.0.0.1:8000/api'
const RELATIONSHIPS=new Set(['trusts','distrusts','loves','fears','protects','betrays','allied_with','rivals','bonded_to','related_to','works_with',
  'forgives','doubts','desires','avoids','respects','suspects','owes','confides_in','consents_to','sets_boundary_with','reconciles_with','jealous_of'])
const FACETS=[
  {key:'goals',label:'What they want',glyph:'✧',words:['wants','goal','seeks','desires','needs','intends','motivation']},
  {key:'wounds',label:'What haunts them',glyph:'◈',words:['fears','fear','avoids','dreads','wound','trauma','grieves','regrets']},
  {key:'values',label:'What they believe',glyph:'✦',words:['values','believes','identity','vulnerability','role','loyal_to']},
  {key:'voice',label:'How they sound',glyph:'❝',words:['speaks_like','speech_style','voice','dialogue_style']},
  {key:'secrets',label:'What they conceal',glyph:'◇',words:['hides','secret','conceals','secret_from','knows']},
]
const BEAT_STYLES:Record<BeatKind,{label:string,icon:string,pressure:number}>={
  arrival:{label:'Arrival',icon:'⌂',pressure:20},
  spark:{label:'Inciting spark',icon:'✧',pressure:40},
  obstacle:{label:'Obstacle',icon:'◈',pressure:65},
  reversal:{label:'Reversal',icon:'↝',pressure:88},
  choice:{label:'Decision',icon:'◆',pressure:78},
  aftermath:{label:'Aftermath',icon:'☾',pressure:35},
}
const TEMPLATES:BeatKind[]=['arrival','spark','obstacle','reversal','choice','aftermath']
const display=(x:string)=>x.replaceAll('_',' ')
const uuid=()=>crypto.randomUUID().replaceAll('-','').slice(0,24)
const initialBoard=(book:number):Board=>({
  id:'',version:0,created_at:'',updated_at:'',title:'The next turning point',book,sequence:0,
  objective:'',conflict:'',opening:'',aftermath:'',voice_notes:'',pov_id:null,location_id:null,
  participants:[],beats:TEMPLATES.map((kind,i)=>({id:uuid(),kind,title:BEAT_STYLES[kind].label,detail:'',pressure:BEAT_STYLES[kind].pressure+i%2*2})),
})
const subjectColor=(i:number)=>['#d7a8e8','#93c6ba','#edbd8d','#98b6ef','#dab3a5','#d5c77d'][i%6]
const earlier=(fact:Fact,book:number,sequence:number)=>fact.start_book<book||
  (fact.start_book===book&&(fact.start_sequence||0)<=sequence)

async function api<T>(path:string,init?:RequestInit):Promise<T>{
  const response=await fetch(API+path,init)
  const data=await response.json().catch(()=>({}))
  if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:`Request failed (${response.status})`)
  return data as T
}
const json=(method:string,data:unknown):RequestInit=>({method,headers:{'Content-Type':'application/json'},body:JSON.stringify(data)})

function Portrait({entity,index,large=false}:{entity:Entity;index:number;large?:boolean}){
  return <div className={'p2-portrait'+(large?' large':'')} style={{'--portrait-accent':subjectColor(index)} as CSSProperties} aria-hidden="true">
    <div className="p2-portrait-halo"/><span className="p2-portrait-letter">{entity.name.slice(0,1).toUpperCase()}</span>
    <span className="p2-portrait-ornament">✦</span>
  </div>
}

function Evidence({fact,onSource}:{fact:Fact;onSource:(id:string)=>void}){
  return <div className="p2-evidence">
    <span className="p2-evidence-kind">{display(fact.predicate)} · {fact.scope.replaceAll('_',' ')}</span>
    <blockquote>“{fact.quote}”</blockquote>
    <div className="p2-evidence-footer"><small>{fact.reference.volume} · Book {fact.reference.book}</small>
      {fact.reference.source_id&&<button type="button" onClick={()=>onSource(fact.reference.source_id!)}>See source ↗</button>}</div>
  </div>
}

export default function PartTwoStudio({seriesId,entities,facts,volumes,onSource,onCanon}:{
  seriesId:string;entities:Entity[];facts:Fact[];volumes:Volume[];
  onSource:(sourceId:string)=>void;onCanon:()=>void
}){
  const characters=useMemo(()=>entities.filter(e=>e.kind==='character'),[entities])
  const [view,setView]=useState<StudioView>('characters')
  const [book,setBook]=useState(()=>Math.max(...volumes.map(v=>v.ordinal),1))
  const [sequence,setSequence]=useState(999999)
  const [selected,setSelected]=useState<string|null>(null)
  const [pair,setPair]=useState<string|null>(null)
  const [search,setSearch]=useState('')
  const [boards,setBoards]=useState<Board[]>([])
  const [board,setBoard]=useState<Board|null>(null)
  const [beatId,setBeatId]=useState<string|null>(null)
  const [saving,setSaving]=useState(false)
  const [message,setMessage]=useState('')
  const [error,setError]=useState('')
  const [dragId,setDragId]=useState<string|null>(null)
  const [check,setCheck]=useState<{findings:{reason:string;existing_values?:string[]}[];mentions:{name:string}[];limitations:string}|null>(null)
  const [claim,setClaim]=useState({subject_id:'',predicate:'',object_text:''})
  const [preflight,setPreflight]=useState<{
    checks:{category:string;level:string;title:string;reason:string;quote:string;
      reference:{volume:string;source_id?:string}}[];
    staging_flags:number;limitations:string;total_checks:number
  }|null>(null)
  const [dirty,setDirty]=useState(false)
  const [deleteConfirm,setDeleteConfirm]=useState(false)
  const approved=useMemo(()=>facts.filter(f=>f.status==='approved'),[facts])
  const atTime=useMemo(()=>approved.filter(f=>earlier(f,book,sequence) &&
    (!f.end_book|| f.end_book>book||(f.end_book===book&&(f.end_sequence??999999)>=sequence))),[approved,book,sequence])
  const current=characters.find(c=>c.id===selected)||characters[0]||null
  const relationships=useMemo(()=>atTime.filter(f=>f.object_entity_id&&RELATIONSHIPS.has(f.predicate)&&
    characters.some(c=>c.id===f.subject_id)&&characters.some(c=>c.id===f.object_entity_id)),[atTime,characters])
  const related=relationships.filter(f=>f.subject_id===current?.id||f.object_entity_id===current?.id)
  const profile=atTime.filter(f=>f.subject_id===current?.id)
  const filteredCharacters=characters.filter(c=>c.name.toLowerCase().includes(search.toLowerCase())).slice(0,24)
  const connections=useMemo(()=>{
    const map=new Map<string,{key:string,a:string,b:string;events:Fact[]}>()
    for(const fact of relationships){
      const key=[fact.subject_id,fact.object_entity_id!].sort().join(':')
      if(!map.has(key))map.set(key,{key,a:fact.subject_id,b:fact.object_entity_id!,events:[]})
      map.get(key)!.events.push(fact)
    }
    return [...map.values()]
  },[relationships])
  const focusedPair=connections.find(x=>x.key===pair)||connections[0]||null
  const beat=board?.beats.find(b=>b.id===beatId)||board?.beats[0]||null
  const sceneContext=useMemo(()=>{
    if(!board)return []
    return board.participants.map(id=>{
      const entity=characters.find(c=>c.id===id)
      const known=approved.filter(f=>earlier(f,board.book,board.sequence) &&
        (!f.end_book||f.end_book>board.book||(f.end_book===board.book&&(f.end_sequence??999999)>=board.sequence)) &&
        (f.subject_id===id||(f.scope==='character_belief'&&f.subject_id===board.pov_id)))
      return {entity,known:known.slice(-7)}
    })
  },[board,characters,approved])
  async function copySceneBrief(){
    if(!board)return
    const name=(id:string|null)=>entities.find(e=>e.id===id)?.name||'Not chosen'
    const brief=[
      `SCENE: ${board.title}`,`Book ${board.book}, scene position ${board.sequence}`,
      `POV: ${name(board.pov_id)}`,`Location: ${name(board.location_id)}`,
      `Cast: ${board.participants.map(id=>name(id)).join(', ')||'Not chosen'}`,
      `Objective: ${board.objective||'Not defined'}`,`Conflict: ${board.conflict||'Not defined'}`,
      `Opening: ${board.opening||'Not defined'}`,
      ...board.beats.map((b,i)=>`${i+1}. ${b.title} (${display(b.kind)}, pressure ${b.pressure}%): ${b.detail}`),
      `Aftermath: ${board.aftermath||'Not defined'}`,
      `Voice / boundaries: ${board.voice_notes||'Not defined'}`,
      'Respect previously established canon, POV knowledge boundaries, consent and character individuality.',
      'This is an author-controlled planning artifact, not established canon.',
    ].join('\n')
    try{await navigator.clipboard.writeText(brief);setMessage('Scene brief copied. Paste into the Writer or Scene Architect to develop prose.')}
    catch{setError('Clipboard access unavailable in this browser; the scene remains saved privately.')}
  }
  const allPaths=[...volumes].sort((a,b)=>a.ordinal-b.ordinal)

  useEffect(()=>{
    let live=true
    void api<Board[]>(`/series/${seriesId}/scene-boards`).then(data=>{if(live){setBoards(data);setBoard(null);setDirty(false)}})
      .catch(e=>{if(live)setError(String(e))})
    return ()=>{live=false}
  },[seriesId])
  function modify(update:Partial<Board>){setBoard(old=>old?{...old,...update}:old);setDirty(true);setMessage('');setCheck(null);setPreflight(null)}
  function editBeat(change:Partial<Beat>){
    if(!board||!beat)return
    modify({beats:board.beats.map(item=>item.id===beat.id?{...item,...change}:item)})
  }
  function moveBeat(id:string,to:number){
    if(!board)return
    const copy=[...board.beats],from=copy.findIndex(b=>b.id===id)
    if(from<0||to<0||to>=copy.length||from===to)return
    const [item]=copy.splice(from,1);copy.splice(to,0,item)
    modify({beats:copy});setBeatId(id)
  }
  function dropBeat(event:DragEvent<HTMLButtonElement>,target:string){
    event.preventDefault()
    if(!dragId||!board)return
    moveBeat(dragId,board.beats.findIndex(b=>b.id===target));setDragId(null)
  }
  async function save(){
    if(!board||saving)return
    setSaving(true);setError('');setMessage('')
    try{
      const {id,version,created_at,updated_at,...payload}=board
      const result=board.id?await api<Board>(`/series/${seriesId}/scene-boards/${board.id}`,json('PUT',{...payload,version}))
        :await api<Board>(`/series/${seriesId}/scene-boards`,json('POST',payload))
      setBoards(old=>[...old.filter(b=>b.id!==board.id),result].sort((a,b)=>a.book-b.book||a.sequence-b.sequence))
      setBoard(result);setDirty(false);setMessage('Storyboard saved privately. Canon and manuscript remain unchanged.')
    }catch(e){setError(String(e))}
    finally{setSaving(false)}
  }
  async function remove(){
    if(!board?.id||saving)return
    setSaving(true);setError('')
    try{
      await api(`/series/${seriesId}/scene-boards/${board.id}/delete`,json('POST',{version:board.version}))
      setBoards(old=>old.filter(x=>x.id!==board.id));setBoard(null);setDirty(false);setMessage('Storyboard removed.')
    }catch(e){setError(String(e))}
    finally{setSaving(false);setDeleteConfirm(false)}
  }
  async function inspectContinuity(){
    if(!board||saving)return
    setSaving(true);setError('');setCheck(null);setPreflight(null)
    const charactersById=new Map(entities.map(e=>[e.id,e.name]))
    const narrative=[board.title,board.opening,board.objective,board.conflict,...board.beats.map(b=>b.title+' '+b.detail),board.aftermath,
      ...board.participants.map(id=>charactersById.get(id)||'')].filter(Boolean).join('\n')
    try{
      const {id,version,created_at,updated_at,...payload}=board
      const [output,preview]=await Promise.all([
        api<{findings:{reason:string;existing_values?:string[]}[];mentions:{name:string}[];limitations:string}>(
          `/series/${seriesId}/continuity/check`,json('POST',{scene:narrative,book:board.book,sequence:board.sequence,
            assertions:claim.subject_id&&claim.predicate&&claim.object_text?[{...claim,scope:'world'}]:[]})),
        api<{checks:{category:string;level:string;title:string;reason:string;quote:string;
            reference:{volume:string;source_id?:string}}[];
            staging_flags:number;limitations:string;total_checks:number}>(
          `/series/${seriesId}/scene-preflight`,json('POST',payload))
      ])
      setCheck(output)
      setPreflight(preview)
    }catch(e){setError(String(e))}
    finally{setSaving(false)}
  }

  return <section className="p2-studio" aria-label="Part Two character relationship and scene studio">
    <header className="p2-header">
      <div className="p2-eyebrow">THE AUTHOR'S CREATIVE STUDIO · PART II</div>
      <div className="p2-heading"><div><h2>People. Promises. Turning points.</h2><p>Explore character truth, the relationships that change them, and the scenes that make those changes matter.</p></div>
        <div className="p2-header-orb" aria-hidden="true"><span>✧</span></div></div>
      <div className="p2-navigation" role="group" aria-label="Creative studio views">
        {([['characters','♙','Character arcs'],['relationships','✧','Relationship orbit'],['scenes','▤','Scene Director']] as const).map(([key,icon,label])=>
          <button type="button" key={key} aria-pressed={view===key} onClick={()=>{setView(key);setError('');setMessage('')}}><span aria-hidden="true">{icon}</span>{label}</button>)}
      </div>
    </header>
    {error&&<div className="p2-message error" role="alert">{error}</div>}
    {message&&<div className="p2-message" role="status">{message}</div>}
    {view!=='scenes'&&<div className="p2-timebar">
      <div><span>STORY POSITION</span><strong>{allPaths.find(v=>v.ordinal===book)?.title||'Choose a book'}</strong></div>
      <div className="p2-books" role="group" aria-label="Choose story book">{allPaths.map(v=>
        <button type="button" key={v.id} aria-pressed={book===v.ordinal} onClick={()=>{setBook(v.ordinal);setSequence(999999)}}>Book {v.ordinal}</button>)}</div>
      <label>Scene <input aria-label="Scene sequence" type="number" min={0} max={999999} value={sequence} onChange={e=>setSequence(Math.max(0,Math.min(999999,Number(e.target.value)||0)))}/></label>
    </div>}

    {view==='characters'&&<div className="p2-character-view">
      <div className="p2-section-lead"><span>CHARACTER ARCS</span><h3>Who are they becoming?</h3><p>Follow motivations and contradictions through accepted manuscript evidence. Personality is never invented to fill a card.</p></div>
      {characters.length?<><div className="p2-cast-strip">
        <label className="p2-cast-search"><span>⌕</span><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search the cast…" aria-label="Search characters"/></label>
        <div className="p2-cast-portraits">{filteredCharacters.map((c,i)=>
          <button type="button" key={c.id} className="p2-cast-button" aria-pressed={current?.id===c.id} onClick={()=>{setSelected(c.id);setPair(null)}}>
            <Portrait entity={c} index={i}/><strong>{c.name}</strong></button>)}</div>
      </div>
      {current&&<div className="p2-character-detail">
        <aside className="p2-character-hero"><Portrait entity={current} index={Math.max(0,characters.indexOf(current))} large/>
          <span>CHARACTER STUDY · BOOK {book}</span><h3>{current.name}</h3><p>{current.description||'No author-approved biography supplied yet.'}</p>
          <div className="p2-character-tally"><strong>{profile.length}</strong><small>cited story facts</small><strong>{related.length}</strong><small>relationships</small></div>
        </aside>
        <div className="p2-character-report">
          <div className="p2-facets">{FACETS.map(facet=>{
            const items=profile.filter(f=>facet.words.includes(f.predicate))
            return <article key={facet.key} className="p2-facet"><header><span>{facet.glyph}</span><strong>{facet.label}</strong><small>{items.length} sources</small></header>
              {items.length?items.slice(-3).map(f=><Evidence key={f.id} fact={f} onSource={onSource}/>):<p>Not yet established in accepted canon.</p>}</article>
          })}</div>
          <div className="p2-arc-river"><div className="p2-subtitle"><strong>The arc across your books</strong><small>Select a moment to examine its evidence</small></div>
            <div className="p2-arc-items">{allPaths.map(v=>{
              const events=approved.filter(f=>f.subject_id===current.id&&f.start_book===v.ordinal)
              return <button key={v.id} type="button" aria-pressed={book===v.ordinal} onClick={()=>{setBook(v.ordinal);setSequence(999999)}}>
                <span className="p2-arc-marker">✧</span><strong>Book {v.ordinal}</strong><small>{events.length} developments</small>
                <span>{events[0]?display(events[0].predicate)+' '+(events[0].object_name||events[0].object_text):'No sourced changes'}</span>
              </button>})}</div>
          </div>
        </div>
      </div>}</>:<div className="p2-empty">Build your cast in the Canon Graph to reveal their stories here. <button onClick={onCanon}>Open Canon Graph →</button></div>}
    </div>}

    {view==='relationships'&&<div className="p2-relationship-view">
      <div className="p2-section-lead"><span>RELATIONSHIP ORBIT</span><h3>Every bond has a history.</h3><p>Explore trust, conflict, affection, protection and boundaries as distinct, directional story facts. Every connection points to manuscript evidence.</p></div>
      {connections.length?<div className="p2-relationship-layout">
        <div className="p2-orbit-wrap">
          <div className="p2-orbit-head"><strong>{connections.length} established connections</strong><small>Choose a connecting line or pair below</small></div>
          <div className="p2-orbit">
            <svg viewBox="0 0 720 580" className="p2-orbit-lines" aria-hidden="true">
              {connections.filter(e=>characters.slice(0,12).some(c=>c.id===e.a)&&characters.slice(0,12).some(c=>c.id===e.b)).map(edge=>{
                const a=characters.slice(0,12).findIndex(c=>c.id===edge.a),b=characters.slice(0,12).findIndex(c=>c.id===edge.b),n=Math.min(12,characters.length)
                const theta=(i:number)=>Math.PI*2*i/n-Math.PI/2
                return <line key={edge.key} x1={360+Math.cos(theta(a))*255} y1={290+Math.sin(theta(a))*205}
                  x2={360+Math.cos(theta(b))*255} y2={290+Math.sin(theta(b))*205}
                  stroke={focusedPair?.key===edge.key?'#e9bad9':'#63859e'} strokeWidth={focusedPair?.key===edge.key?4:2}
                  strokeOpacity={focusedPair?.key===edge.key?1:.5}/>
              })}
            </svg>
            {characters.slice(0,12).map((c,i)=>{
              const n=Math.min(12,characters.length),theta=Math.PI*2*i/n-Math.PI/2
              return <button className="p2-orbit-person" type="button" key={c.id} style={{left:`${50+Math.cos(theta)*35.4}%`,top:`${50+Math.sin(theta)*35.4}%`, '--portrait-accent':subjectColor(i)} as CSSProperties}
                onClick={()=>{setSelected(c.id);setView('characters')}} aria-label={`Explore ${c.name} in Character Arcs`}>
                <span>{c.name.slice(0,1)}</span><strong>{c.name}</strong></button>
            })}
            <div className="p2-orbit-core" aria-hidden="true">✧</div>
          </div>
          <div className="p2-connection-pills">{connections.slice(0,30).map(edge=>
            <button type="button" aria-pressed={focusedPair?.key===edge.key} key={edge.key} onClick={()=>setPair(edge.key)}>
              {entities.find(c=>c.id===edge.a)?.name} <span>↔</span> {entities.find(c=>c.id===edge.b)?.name}</button>)}</div>
        </div>
        <aside className="p2-relationship-history">
          {focusedPair&&<><span>THE SHARED HISTORY</span><h3>{entities.find(e=>e.id===focusedPair.a)?.name} <i>and</i> {entities.find(e=>e.id===focusedPair.b)?.name}</h3>
            <p>Direction and knowledge scope matter: these claims do not imply that both people feel the same way.</p>
            <div className="p2-bond-timeline">{focusedPair.events.map(f=><article key={f.id} className="p2-bond-event">
              <span>BOOK {f.start_book}{f.start_sequence?' · SCENE '+f.start_sequence:''}</span>
              <h4>{f.subject_name} {display(f.predicate)} {f.object_name||f.object_text}</h4>
              <Evidence fact={f} onSource={onSource}/></article>)}</div></>}
        </aside>
      </div>:<div className="p2-empty">No accepted, entity-linked character relationships are established at this story point. Discover or approve manuscript evidence to create genuine connections. <button onClick={onCanon}>Review canon →</button></div>}
    </div>}

    {view==='scenes'&&<div className="p2-director">
      <div className="p2-section-lead"><span>THE SCENE DIRECTOR</span><h3>Direct the turning point.</h3><p>Arrange dramatic beats, sculpt tension and inspect continuity. Storyboards are private planning drafts—not canon or manuscript edits.</p></div>
      <div className="p2-director-shelf"><div className="p2-saved-boards"><span>YOUR SCENE BOARDS</span>
        {boards.slice(0,25).map(item=><button type="button" key={item.id} aria-pressed={board?.id===item.id} onClick={()=>{
          if(dirty&&!window.confirm('Discard unsaved storyboard edits?'))return
          setBoard(structuredClone(item));setBeatId(item.beats[0]?.id||null);setDirty(false);setDeleteConfirm(false);setCheck(null)
        }}><strong>{item.title}</strong><small>Book {item.book} · {item.beats.length} beats</small></button>)}
        {!boards.length&&<small>No saved scenes yet.</small>}</div>
        <button type="button" className="p2-new-board" onClick={()=>{
          if(dirty&&!window.confirm('Discard unsaved storyboard edits?'))return
          const newBoard=initialBoard(book);setBoard(newBoard);setBeatId(newBoard.beats[0].id);setDirty(true);setCheck(null)
        }}><span>＋</span><strong>Create scene board</strong><small>Start with six movable dramatic beats</small></button>
      </div>
      {board?<><div className="p2-board-heading">
        <div><span>{board.id?'SAVED SCENE PLAN':'NEW SCENE PLAN'} {dirty?'· UNSAVED CHANGES':''}</span>
          <input aria-label="Scene title" maxLength={160} value={board.title} onChange={e=>modify({title:e.target.value})}/>
        </div>
        <div className="p2-board-actions"><button type="button" disabled={saving||!dirty} onClick={()=>void save()}>{saving?'Working…':'◆ Save scene plan'}</button>
          <button type="button" onClick={()=>void copySceneBrief()}>↗ Copy directing brief</button>
          {board.id&&<button type="button" onClick={()=>setDeleteConfirm(!deleteConfirm)}>Delete</button>}
          {deleteConfirm&&<button type="button" className="p2-danger" onClick={()=>void remove()} disabled={saving}>Confirm delete</button>}
        </div>
      </div>
      <div className="p2-tension-chart"><div className="p2-subtitle"><strong>The tension curve</strong><small>Each scene beat sets its own pressure level</small></div>
        <svg viewBox="0 0 940 160" preserveAspectRatio="none" role="img" aria-label="Scene tension from first beat to last beat">
          {[25,50,75].map(p=><line key={p} x1="24" y1={148-p*1.25} x2="916" y2={148-p*1.25} stroke="#4b6177" strokeDasharray="5 8"/>)}
          <polyline points={board.beats.map((b,i)=>`${24+(892*i/Math.max(1,board.beats.length-1))},${148-b.pressure*1.25}`).join(' ')}
            fill="none" stroke="#ddb2dc" strokeWidth="4" strokeLinejoin="round"/>
          {board.beats.map((b,i)=><circle key={b.id} cx={24+892*i/Math.max(1,board.beats.length-1)}
            cy={148-b.pressure*1.25} r={beat?.id===b.id?8:5} fill={beat?.id===b.id?'#f8d6bb':'#d4a9db'}/>)}
        </svg>
      </div>
      <div className="p2-beat-rail" aria-label="Reorderable dramatic scene beats">
        {board.beats.map((item,i)=><div className="p2-beat-frame" key={item.id}>
          <button type="button" className="p2-beat-card" aria-pressed={beat?.id===item.id}
            draggable onDragStart={()=>setDragId(item.id)} onDragOver={event=>event.preventDefault()} onDrop={event=>dropBeat(event,item.id)} onDragEnd={()=>setDragId(null)}
            onClick={()=>setBeatId(item.id)}>
            <span className="p2-beat-counter">{String(i+1).padStart(2,'0')} <small>{BEAT_STYLES[item.kind].icon}</small></span>
            <strong>{item.title}</strong><small>{BEAT_STYLES[item.kind].label}</small>
            <span className="p2-beat-pressure"><i style={{width:item.pressure+'%'}}/></span>
          </button>
          <div className="p2-beat-move" role="group" aria-label={'Reorder '+item.title}>
            <button type="button" disabled={i===0} onClick={()=>moveBeat(item.id,i-1)} aria-label={'Move '+item.title+' earlier'}>←</button>
            <button type="button" disabled={i===board.beats.length-1} onClick={()=>moveBeat(item.id,i+1)} aria-label={'Move '+item.title+' later'}>→</button>
          </div>
        </div>)}
        {board.beats.length<24&&<button type="button" className="p2-add-beat" onClick={()=>{
          const newBeat:Beat={id:uuid(),kind:'obstacle',title:'New obstacle',detail:'',pressure:65}
          modify({beats:[...board.beats,newBeat]});setBeatId(newBeat.id)
        }}>＋<small>Add a beat</small></button>}
      </div>
      <div className="p2-director-bottom">
        <section className="p2-director-inspector"><div className="p2-subtitle"><strong>Direct this beat</strong><small>Only the selected beat is editable</small></div>
          {beat&&<><div className="p2-kind-choices">{Object.entries(BEAT_STYLES).map(([kind,meta])=>
            <button type="button" key={kind} aria-pressed={beat.kind===kind} onClick={()=>editBeat({kind:kind as BeatKind,title:beat.title===BEAT_STYLES[beat.kind].label?meta.label:beat.title})}><span>{meta.icon}</span>{meta.label}</button>)}</div>
            <label>Beat title<input maxLength={120} value={beat.title} onChange={e=>editBeat({title:e.target.value})}/></label>
            <label>What changes in this beat?<textarea rows={3} maxLength={1200} value={beat.detail} onChange={e=>editBeat({detail:e.target.value})} placeholder="A secret surfaces, trust shifts, or the obstacle escalates…"/></label>
            <label className="p2-pressure-control">Emotional pressure <strong>{beat.pressure}%</strong><input type="range" min={0} max={100} value={beat.pressure} onChange={e=>editBeat({pressure:Number(e.target.value)})}/></label>
            {board.beats.length>1&&<button type="button" className="p2-remove-beat" onClick={()=>{
              const others=board.beats.filter(b=>b.id!==beat.id);modify({beats:others});setBeatId(others[0]?.id||null)
            }}>Remove this beat</button>}</>}
        </section>
        <section className="p2-scene-brief"><div className="p2-subtitle"><strong>Scene intentions & aftermath</strong><small>Advanced direction lives here, not in a giant starting form</small></div>
          <div className="p2-scene-fields">
            <label>Book<select value={board.book} onChange={e=>modify({book:Number(e.target.value)})}>{allPaths.map(v=><option key={v.id} value={v.ordinal}>Book {v.ordinal} · {v.title}</option>)}</select></label>
            <label>Story position<input type="number" min={0} max={999999} value={board.sequence} onChange={e=>modify({sequence:Math.min(999999,Math.max(0,Number(e.target.value)||0))})}/></label>
            <label>POV<select value={board.pov_id||''} onChange={e=>modify({pov_id:e.target.value||null})}><option value="">Not chosen</option>{characters.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
            <label>Location<select value={board.location_id||''} onChange={e=>modify({location_id:e.target.value||null})}><option value="">Not chosen</option>{entities.filter(e=>e.kind==='place').map(e=><option key={e.id} value={e.id}>{e.name}</option>)}</select></label>
          </div>
          <label>What must this scene accomplish?<textarea value={board.objective} maxLength={1200} rows={2} onChange={e=>modify({objective:e.target.value})}/></label>
          <label>What stands in the way?<textarea value={board.conflict} maxLength={1200} rows={2} onChange={e=>modify({conflict:e.target.value})}/></label>
          <label>Opening state<textarea value={board.opening} maxLength={1600} rows={2} onChange={e=>modify({opening:e.target.value})}/></label>
          <label>What changes permanently?<textarea value={board.aftermath} maxLength={1600} rows={2} onChange={e=>modify({aftermath:e.target.value})}/></label>
          <details><summary>Cast and author voice notes</summary><div className="p2-character-choices">{characters.slice(0,30).map(c=><label key={c.id}><input type="checkbox" checked={board.participants.includes(c.id)} onChange={e=>modify({participants:e.target.checked?[...board.participants,c.id]:board.participants.filter(id=>id!==c.id)})}/>{c.name}</label>)}</div>
            <label>Dialogue / intimacy / boundaries / style notes<textarea rows={3} value={board.voice_notes} maxLength={1200} onChange={e=>modify({voice_notes:e.target.value})}/></label></details>
        </section>
      </div>
      <section className="p2-before-after">
        <div className="p2-subtitle"><strong>Before the scene / after the choice</strong><small>The scene is informed by existing evidence, but a draft never rewrites canon</small></div>
        <div className="p2-before-after-grid">
          <div className="p2-before-panel"><span>01 · ESTABLISHED BEFORE</span>
            {sceneContext.length?sceneContext.map(({entity,known})=>entity&&<article key={entity.id}>
              <strong>{entity.name}</strong><small>{known.length} relevant source-backed facts</small>
              {known.slice(-3).map(f=><div key={f.id}><span>{display(f.predicate)} {f.object_name||f.object_text}</span>
                <button type="button" onClick={()=>{if(f.reference.source_id)onSource(f.reference.source_id)}}>{f.reference.volume} ↗</button></div>)}
              {!known.length&&<p>No approved facts found for this character at this scene point.</p>}
            </article>):<p>Choose scene participants in the cast drawer to inspect their approved story state before writing.</p>}
          </div>
          <div className="p2-after-panel"><span>02 · AUTHOR-PLANNED AFTER</span>
            <blockquote>{board.aftermath||'What has changed permanently by the final beat? Record the consequence in Scene Intentions.'}</blockquote>
            <p>Planning only. The consequences stay proposals until the manuscript establishes them and you approve their source evidence.</p>
          </div>
        </div>
      </section>
      <section className="p2-continuity-console"><div className="p2-subtitle"><strong>Continuity Guardian</strong><small>Read-only checking against approved canon</small></div>
        <p>Scan for known entities, or specify an explicit proposed fact to compare with established world truth. This does not infer contradictions from ordinary prose.</p>
        <details><summary>Test an explicit scene claim (optional)</summary><div className="p2-claim-fields">
          <label>Who or what?<select value={claim.subject_id} onChange={e=>setClaim(c=>({...c,subject_id:e.target.value}))}><option value="">Choose entity</option>{entities.map(e=><option key={e.id} value={e.id}>{e.name}</option>)}</select></label>
          <label>Predicate<input placeholder="located_in" value={claim.predicate} onChange={e=>setClaim(c=>({...c,predicate:e.target.value}))}/></label>
          <label>New fact<input placeholder="Forest of mirrors" value={claim.object_text} onChange={e=>setClaim(c=>({...c,object_text:e.target.value}))}/></label></div></details>
        <button type="button" disabled={saving} onClick={()=>void inspectContinuity()}>◈ Check this scene</button>
        {preflight&&<div className="p2-preflight-results">
          <div className="p2-subtitle"><strong>{preflight.total_checks} story-context checks</strong>
            <small>{preflight.staging_flags} staging reminders · author review</small></div>
          <p>{preflight.limitations}</p>
          <div className="p2-preflight-list">{preflight.checks.map((item,i)=><article key={i}>
            <span>{item.category.toUpperCase()} · {item.level}</span><h4>{item.title}</h4>
            <p>{item.reason}</p><blockquote>“{item.quote}”</blockquote>
            {item.reference.source_id&&<button type="button" onClick={()=>onSource(item.reference.source_id!)}>Inspect {item.reference.volume} ↗</button>}
          </article>)}</div>
          {!preflight.checks.length&&<p>No staging, relationship or condition reminders were found in approved facts for this cast and story point. This is not a comprehensive continuity guarantee.</p>}
        </div>}
        {check&&<div className="p2-continuity-results"><strong>{check.findings.length?check.findings.length+' potential contradictions':'No explicit contradictions detected'}</strong>
          <p>{check.mentions.length} known entity mentions · {check.limitations}</p>
          {check.findings.map((finding,i)=><article key={i}>{finding.reason} · Existing values: {(finding.existing_values||[]).join(', ')}</article>)}</div>}
      </section>
      </>:<div className="p2-empty p2-scene-empty"><span>✧</span><h3>Every unforgettable chapter begins with a choice.</h3><p>Create a scene board to lay out dramatic turns, sculpt tension, record aftermath and check what the story already knows.</p>
        <button type="button" onClick={()=>{const draft=initialBoard(book);setBoard(draft);setBeatId(draft.beats[0].id);setDirty(true)}}>Create your first scene →</button></div>}
    </div>}
  </section>
}
