import { useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import type { CSSProperties } from 'react'
import './story-observatory.css'
import StoryConstellation from './StoryConstellation'
import StoryModelLab from './StoryModelLab'
import StoryDiscovery from './StoryDiscovery'
import StoryEvidenceOnboarding from './StoryEvidenceOnboarding'

export type ObservatoryEntity = { id: string; name: string; kind: string; aliases: string[]; description: string }
export type ObservatoryFact = {
  id: string; subject_id: string; subject_name: string; predicate: string;
  object_text: string; object_name: string | null; scope: string;
  knower_name: string | null; status: string; start_book: number; end_book: number | null;
  quote: string; reference: { volume: string; book: number; title: string; source_path: string; source_id?: string; start: number; end: number }
}
export type ObservatoryVolume = { id: string; ordinal: number; title: string }
type Props = {
  seriesId: string
  entities: ObservatoryEntity[]
  facts: ObservatoryFact[]
  volumes: ObservatoryVolume[]
  onReview: (factId: string, decision: 'approved' | 'rejected') => void
  busy: boolean
  onOpenCanon: () => void
  onInspectSource: (sourceId: string) => void
  onOpenVault: () => void
  onDiscoverySaved: () => void
}

type StoryState = {
  book: number; sequence: number; sequence_points: number[]
  facts: ObservatoryFact[]
  proposals: ObservatoryFact[]
  conflicts: { subject: string; predicate: string; scope: string; assertion_ids: string[] }[]
  stale_sources: {source_id:string;source_path:string;book:number;volume:string;reason:string}[]
  profiles: Record<string, { entity_id: string; name: string; kind: string; facets: Record<string, ObservatoryFact[]>; missing_facets: string[] }>
  links: { from: string; to: string; predicate: string; fact_id: string; relationship: boolean; scope: string; reference: ObservatoryFact['reference'] }[]
  threads: { entity_id: string; name: string; status: string; unearned_payoff: boolean; unanchored_reveal: boolean; events: ObservatoryFact[] }[]
}
const kinds: Record<string, { icon: string; color: string }> = {
  character: { icon: '♙', color: '#c6a8ff' },
  place: { icon: '⌖', color: '#78c5ba' },
  artifact: { icon: '◇', color: '#efb97a' },
  faction: { icon: '⚑', color: '#8db9ef' },
  rule: { icon: '✧', color: '#f0a8b3' },
  event: { icon: '◈', color: '#ead889' },
}
const kindInfo = (kind: string) => kinds[kind] || { icon: '✦', color: '#a9bbcf' }
const scopeLabels: Record<string, string> = {
  world: 'World truth', character_belief: 'Character belief', reader_reveal: 'Reader knowledge',
}
const readable = (value: string) => value.replace(/_/g, ' ').replace(/\s+/g, ' ').trim()
const unique = <T,>(values: T[]) => Array.from(new Set(values))

export default function StoryObservatory({ seriesId, entities, facts, volumes, onReview, busy, onOpenCanon, onInspectSource, onOpenVault, onDiscoverySaved }: Props) {
  const books = useMemo(() => [...volumes].sort((a, b) => a.ordinal - b.ordinal), [volumes])
  const [bookOverride, setBookOverride] = useState<number | null>(null)
  const [sequenceOverride, setSequenceOverride] = useState<number | null>(null)
  const book = books.some(item => item.ordinal === bookOverride) ? bookOverride! : (books[books.length - 1]?.ordinal ?? 1)
  const sequence = sequenceOverride ?? 999999
  const [scope, setScope] = useState<'all' | 'world' | 'character_belief' | 'reader_reveal'>('all')
  const [status, setStatus] = useState<'approved' | 'proposed' | 'all'>('approved')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [showEvidence, setShowEvidence] = useState<string | null>(null)
  const [showAll, setShowAll] = useState(false)
  const [lens, setLens] = useState<'universe' | 'psychology' | 'threads' | 'timeline' | 'models' | 'discovery'>('universe')
  const [snapshot, setSnapshot] = useState<StoryState | null>(null)
  const [loading, setLoading] = useState(true)
  const [immersive, setImmersive] = useState(false)
  const immersiveButtonRef = useRef<HTMLButtonElement>(null)
  const [loadError, setLoadError] = useState('')
  const [refresh, setRefresh] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setSnapshot(null); setLoading(true); setLoadError('')
    void fetch(`http://127.0.0.1:8000/api/series/${encodeURIComponent(seriesId)}/story-state?book=${book}&sequence=${sequence}`, {
      signal: controller.signal,
    }).then(async response => {
      if (!response.ok) throw new Error(`Story intelligence unavailable (${response.status})`)
      return response.json() as Promise<StoryState>
    }).then(data => { if (!controller.signal.aborted) setSnapshot(data) })
      .catch(error => { if (!controller.signal.aborted) setLoadError(String(error)) })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [seriesId, book, sequence, refresh, facts])

  useEffect(() => {
    if (!immersive) return
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setImmersive(false)
        immersiveButtonRef.current?.focus()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => {
      document.body.style.overflow = previous
      window.removeEventListener('keydown', onKey)
    }
  }, [immersive])

  const visibleFacts = useMemo(() => {
    if (!snapshot) return []
    const eligible = status === 'approved' ? snapshot.facts : status === 'proposed'
      ? snapshot.proposals : [...snapshot.facts, ...snapshot.proposals]
    return eligible.filter(fact => scope === 'all' || fact.scope === scope)
  }, [snapshot, status, scope])
  const matching = useMemo(() => entities.filter(entity =>
    (entity.name + ' ' + entity.kind + ' ' + (entity.aliases || []).join(' '))
      .toLocaleLowerCase().includes(search.toLocaleLowerCase().trim())
  ), [entities, search])
  const selected = matching.find(entity => entity.id === selectedId) || matching[0] || null
  const selectedFacts = visibleFacts.filter(fact =>
    fact.subject_id === selected?.id ||
    (selected && fact.object_name?.toLocaleLowerCase() === selected.name.toLocaleLowerCase())
  )
  const connectedNames = unique(selectedFacts.map(fact =>
    fact.subject_id === selected?.id ? (fact.object_name || fact.object_text) : fact.subject_name
  )).filter(Boolean)
  const pending = snapshot?.proposals || []
  const highlighted = new Set([selected?.name, ...connectedNames].filter(Boolean))
  const nodes = showAll ? matching : matching.slice(0, 32)

  const surface = <section className={`story-observatory ${immersive ? "is-immersive" : ""}`} aria-label="Interactive story observatory">
    <div className="observatory-utility-bar"><span>THE AUTHOR’S UNIVERSE <em>/ PRIVATE STORY SYSTEM</em></span>
      <button type="button" ref={immersiveButtonRef} aria-pressed={immersive}
        onClick={() => setImmersive(value => !value)}>
        {immersive ? "↙ Return to Series Desk" : "⛶ Enter immersive view"}
      </button>
    </div>
    <header className="observatory-hero">
      <div>
        <span className="observatory-kicker">PART I · LIVING STORY INTELLIGENCE</span>
        <h2>Your universe, in motion.</h2>
        <p>Explore what is established, what someone believes, and what remains unapproved—at any point in your series.</p>
      </div>
      <div className="observatory-hero-stats" aria-label="Story state summary">
        <div><strong>{entities.length}</strong><span>Story entities</span></div>
        <div><strong>{snapshot?.facts.length ?? '—'}</strong><span>Facts at this book</span></div>
        <div><strong>{pending.length}</strong><span>Awaiting review</span></div>
      </div>
    </header>

    <nav className="observatory-lenses" aria-label="Story intelligence lenses">
      {([['universe','✧','Universe'],['psychology','♙','Character minds'],['threads','◇','Plot threads'],['timeline','◷','Story history'],['models','⚗','Model Lab'],['discovery','◉','Discover']] as const)
        .map(([key,icon,label]) => <button key={key} type="button" aria-pressed={lens===key}
          onClick={() => setLens(key)}><span aria-hidden="true">{icon}</span>{label}</button>)}
    </nav>
    {loadError && <div role="alert" className="observatory-alert">{loadError} <button onClick={() => setRefresh(v => v + 1)}>Retry</button></div>}
    {snapshot?.conflicts.length ? <div role="status" className="observatory-alert">{snapshot.conflicts.length} conflicting approved claims need author review. <button onClick={onOpenCanon}>Inspect canon</button></div> : null}
    {snapshot?.stale_sources?.length ? <div role="status" className="observatory-alert">
      {snapshot.stale_sources.length} linked manuscript sources changed since their evidence snapshots. <button type="button" onClick={onOpenVault}>Review sources</button>
    </div> : null}
    <div className="observatory-stage">
      {!loading && !loadError && snapshot && snapshot.facts.length === 0 && snapshot.proposals.length === 0 && lens !== "models" && lens !== "discovery" && <StoryEvidenceOnboarding seriesId={seriesId} onDiscover={() => setLens("discovery")} onReview={onOpenCanon} />}
      {lens === "universe" && <div className="observatory-toolbar">
        <label className="observatory-search"><span className="sr-only">Find story entity</span>
          <span aria-hidden="true">⌕</span>
          <input value={search} onChange={event => setSearch(event.target.value)}
            placeholder="Find a person, place or artifact…" />
        </label>
        <div className="observatory-segments" role="group" aria-label="Knowledge perspective">
          {([['all','All'],['world','World'],['character_belief','Beliefs'],['reader_reveal','Reader']] as const).map(([value,label]) =>
            <button key={value} type="button" aria-pressed={scope === value} onClick={() => setScope(value)}>{label}</button>)}
        </div>
        <label className="observatory-select">Show
          <select value={status} onChange={event => setStatus(event.target.value as typeof status)}>
            <option value="approved">Approved canon</option><option value="proposed">Proposed facts</option>
            <option value="all">Both (clearly labeled)</option>
          </select>
        </label>
      </div>}

      {loading && <div role="status" className="observatory-loading">Reading approved story evidence…</div>}
      {lens === 'models' && <StoryModelLab seriesId={seriesId} />}
      {lens === 'discovery' && <StoryDiscovery seriesId={seriesId} book={book} entities={entities}
        onSaved={() => { setRefresh(n=>n+1);onDiscoverySaved() }} onOpenCanon={onOpenCanon} />}
      {!loading && lens !== 'universe' && lens !== 'models' && lens !== 'discovery' && <StoryLens lens={lens} snapshot={snapshot} selectedId={selected?.id || null}
        onFocus={id => setSelectedId(id)} onExplore={id => { setSelectedId(id); setLens('universe') }} onOpenCanon={onOpenCanon} />}
      <div className="observatory-main" hidden={lens !== 'universe'}>
        <div className="observatory-constellation" aria-label="Selectable story entities">
          <div className="observatory-constellation-title"><span>STORY CONSTELLATION</span><small>Select any node to inspect its history</small></div>
          {nodes.length ? <StoryConstellation entities={nodes}
            selectedId={selected?.id || null}
            links={(snapshot?.links || []).filter(link => scope === 'all' || link.scope === scope)}
            factCounts={Object.fromEntries(nodes.map(entity => [entity.id,visibleFacts.filter(fact =>
              fact.subject_id === entity.id || fact.object_name?.toLocaleLowerCase() === entity.name.toLocaleLowerCase()).length]))}
            onSelect={id => { setSelectedId(id); setShowEvidence(null) }} /> : <div className="observatory-empty">
            <span aria-hidden="true">✧</span><strong>{search ? 'No matching story elements' : 'Your constellation starts here'}</strong>
            <p>{search ? 'Try another name or clear your search.' : 'Create story entities and link them to quoted manuscript evidence in the Canon Graph.'}</p>
            <button type="button" onClick={onOpenCanon}>Open Canon Graph →</button>
          </div>}
          {matching.length > 32 && <button className="observatory-expand" type="button" onClick={() => setShowAll(!showAll)}>
            {showAll ? 'Show fewer entities' : `Explore all ${matching.length} entities`}
          </button>}
          <div className="observatory-legend">{Object.entries(kinds).map(([kind,info]) =>
            <span key={kind}><i style={{ background:info.color }} />{kind}</span>)}</div>
        </div>

        <aside className="observatory-inspector" aria-live="polite">
          {selected ? <>
            <div className="observatory-inspector-heading">
              <div className="observatory-avatar" style={{ '--node-accent':kindInfo(selected.kind).color } as CSSProperties}>{kindInfo(selected.kind).icon}</div>
              <div><small>{readable(selected.kind).toUpperCase()}</small><h3>{selected.name}</h3></div>
            </div>
            {selected.description && <p className="observatory-bio">{selected.description}</p>}
            {selected.aliases?.length > 0 && <p className="observatory-aliases">Also known as: {selected.aliases.join(', ')}</p>}
            <div className="observatory-inspector-count"><strong>{selectedFacts.length}</strong><span>relevant facts at this story point</span></div>
            {selectedFacts.length ? <div className="observatory-facts">
              {selectedFacts.map(fact => <article key={fact.id} className="observatory-fact">
                <div className="observatory-fact-head">
                  <span className={`observatory-status ${fact.status}`}>{fact.status === 'approved' ? '◆ Canon' : '◌ Proposal'}</span>
                  <small>{scopeLabels[fact.scope] || readable(fact.scope)}</small>
                </div>
                <p><strong>{fact.subject_name}</strong> {readable(fact.predicate)} <strong>{fact.object_name || fact.object_text}</strong></p>
                {fact.knower_name && <small>Believed by {fact.knower_name}</small>}
                <button className="observatory-evidence-toggle" type="button"
                  aria-expanded={showEvidence === fact.id}
                  onClick={() => setShowEvidence(showEvidence === fact.id ? null : fact.id)}>
                  {showEvidence === fact.id ? 'Hide evidence ↑' : 'Inspect source evidence ↗'}
                </button>
                {showEvidence === fact.id && <div className="observatory-evidence">
                  <blockquote>“{fact.quote}”</blockquote>
                  <small>{fact.reference.volume} · {fact.reference.source_path} · characters {fact.reference.start}–{fact.reference.end}</small>
                  <small>Applies from Book {fact.start_book}{fact.end_book ? ` through Book ${fact.end_book}` : ' onward'}</small>
                  {fact.reference.source_id && <button type="button" className="observatory-evidence-toggle"
                    onClick={() => onInspectSource(fact.reference.source_id!)}>Open cited source in Canon Graph ↗</button>}
                </div>}
                {fact.status === 'proposed' && <div className="observatory-review">
                  <button type="button" disabled={busy} onClick={() => onReview(fact.id, 'approved')}>Approve canon</button>
                  <button type="button" disabled={busy} onClick={() => onReview(fact.id, 'rejected')}>Reject</button>
                </div>}
              </article>)}
            </div> : <p className="observatory-muted">No matching facts at this book and perspective. The absence of a fact is not evidence that it is false.</p>}
            {connectedNames.length > 0 && <div className="observatory-connections">
              <h4>Connected story elements</h4><div>{connectedNames.slice(0,12).map(name => {
                const match = entities.find(entity => entity.name.toLocaleLowerCase() === name.toLocaleLowerCase())
                return match ? <button key={name} type="button" onClick={() => setSelectedId(match.id)}>{name} ↗</button> : <span key={name}>{name}</span>
              })}</div>
            </div>}
          </> : <p className="observatory-muted">Choose an entity to see what the manuscript establishes.</p>}
        </aside>
      </div>
    </div>

    <footer className="observatory-time">
      <div className="observatory-time-heading">
        <div><span>STORY TIME MACHINE</span><strong>{books.find(item => item.ordinal === book)?.title || `Book ${book}`}</strong></div>
        <small>Only facts valid at the selected book appear. Within-book sequence remains available in Time &amp; Knowledge.</small>
      </div>
      <div className="observatory-book-track" role="group" aria-label="Select book in story chronology">
        {books.length ? books.map(volume => <button type="button" key={volume.id}
          className={book === volume.ordinal ? 'active' : ''}
          aria-pressed={book === volume.ordinal}
          onClick={() => { setBookOverride(volume.ordinal); setSequenceOverride(null); setShowEvidence(null) }}>
          <span>BOOK {volume.ordinal}</span><strong>{volume.title}</strong>
        </button>) : <span className="observatory-muted">Add books to activate the story time machine.</span>}
      </div>
      {snapshot && snapshot.sequence_points.length > 2 && <div className="observatory-scene-scrubber">
        <div><strong>Explore within Book {book}</strong><span>{sequence === 999999 ? "End of book" : sequence === 0 ? "Book opening" : `Scene point ${sequence}`}</span></div>
        <input type="range" min={0} max={snapshot.sequence_points.length-1} step={1}
          aria-label="Story position within selected book"
          value={Math.max(0,snapshot.sequence_points.indexOf(sequence))}
          onChange={event => { setSequenceOverride(snapshot.sequence_points[Number(event.target.value)]);setShowEvidence(null) }}/>
        <div className="observatory-scene-labels"><span>Opening</span><span>Book end</span></div>
      </div>}
      <p className="observatory-provenance">Read-only exploration, except explicit Approve/Reject actions. All knowledge comes from your local Series Vault; no model request is made by this view.</p>
    </footer>
  </section>
  return immersive ? createPortal(surface, document.body) : surface
}

function StoryLens({ lens, snapshot, selectedId, onFocus, onExplore, onOpenCanon }: {
  lens: 'psychology' | 'threads' | 'timeline'
  snapshot: StoryState | null
  selectedId: string | null
  onFocus: (id: string) => void
  onExplore: (id: string) => void
  onOpenCanon: () => void
}) {
  const [expanded, setExpanded] = useState(false)
  if (!snapshot) return <div className="observatory-lens-empty">No story intelligence is available for this book.</div>
  if (lens === 'psychology') {
    const characters = Object.values(snapshot.profiles).filter(profile => profile.kind === 'character')
    const evidenceCount = (character: typeof characters[number]) => Object.values(character.facets)
      .reduce((total, items) => total + items.length, 0)
    const selected = characters.find(character => character.entity_id === selectedId)
      || [...characters].sort((a,b) => evidenceCount(b)-evidenceCount(a))[0]
    return <div className="observatory-lens-body observatory-psychology">
      <div className="observatory-lens-intro"><span>CHARACTER PSYCHOLOGY</span><h3>What makes them move?</h3>
        <p>Goals, fears, secrets and voice are shown only when an approved, cited assertion establishes them. Empty facets invite the author to develop the character; they are never filled with invented traits.</p></div>
      {!characters.length ? <div className="observatory-lens-empty">Add character entities in Canon Graph to build your cast. <button onClick={onOpenCanon}>Open Canon Graph</button></div> : <>
        <div className="observatory-character-strip">{characters.slice(0,24).map((character,index) =>
          <button type="button" key={character.entity_id} aria-pressed={character.entity_id === selected?.entity_id}
            onClick={() => onFocus(character.entity_id)}>
            <span className="observatory-character-seal" style={{ '--node-accent': index % 2 ? '#8ec7bb' : '#c6a8ff' } as CSSProperties}>{character.name.slice(0,1)}</span>
            <strong>{character.name}</strong>
          </button>)}</div>
        {selected && <div className="observatory-psychology-body">
          <div className="observatory-psychology-portrait">
            <div className="observatory-portrait-ornament"><span>{selected.name.slice(0,1).toUpperCase()}</span></div>
            <strong>{selected.name}</strong><small>Knowledge as of Book {snapshot.book}</small>
            <button onClick={() => onExplore(selected.entity_id)}>Explore complete history ↗</button>
          </div>
          <div className="observatory-psychology-facets">
            {(['goals','fears','secrets','voice','identity'] as const).map((facet,index) =>
              <article key={facet} className="observatory-facet">
                <header><span className="observatory-facet-symbol">{['✦','◈','◇','❝','✧'][index]}</span><h4>{facet === 'identity' ? 'Identity & values' : facet}</h4>
                  <small>{selected.facets[facet]?.length || 0} citations</small></header>
                {(selected.facets[facet] || []).length ? selected.facets[facet].slice(0,4).map(fact =>
                  <div className="observatory-facet-claim" key={fact.id}>
                    <strong>{readable(fact.predicate)} {fact.object_name || fact.object_text}</strong>
                    <span>{fact.reference.volume} · “{fact.quote.slice(0,150)}”</span>
                  </div>) : <p className="observatory-facet-empty">Not established in approved canon.</p>}
              </article>)}
          </div>
        </div>}
      </>}
    </div>
  }
  if (lens === 'threads') {
    const threads = snapshot.threads
    return <div className="observatory-lens-body observatory-thread-lens">
      <div className="observatory-lens-intro"><span>PROMISES & PAYOFFS</span><h3>The threads holding your story together.</h3>
        <p>Follow explicitly approved setup and payoff assertions. A thread remains open until a cited resolution is established.</p></div>
      <div className="observatory-thread-summary">
        <div><strong>{threads.filter(thread => thread.status === 'open').length}</strong><span>Still open</span></div>
        <div><strong>{threads.filter(thread => thread.status === 'resolved').length}</strong><span>Paid off</span></div>
        <div><strong>{threads.filter(thread => thread.unearned_payoff || thread.unanchored_reveal).length}</strong><span>Needs setup context</span></div>
      </div>
      {threads.length ? <div className="observatory-thread-list">{threads.slice(0,expanded?100:12).map(thread =>
        <article key={thread.entity_id} className="observatory-thread-card">
          <div className="observatory-thread-head"><button onClick={() => onExplore(thread.entity_id)}>{thread.name} ↗</button>
            <span className={thread.status === 'resolved' ? 'done' : 'open'}>{thread.status === 'resolved' ? '✓ Resolved' : thread.status === 'unanchored' ? '? Reveal only' : '◌ Open'}</span></div>
          <div className="observatory-thread-rail" aria-label={'Thread ' + thread.name}>
            {thread.events.map(event => <div key={event.id} className="observatory-thread-moment">
              <span className="observatory-thread-dot"/>
              <small>Book {event.start_book}</small>
              <strong>{readable(event.predicate)}</strong>
              <p>{event.object_name || event.object_text}</p>
              <blockquote>“{event.quote}”</blockquote>
            </div>)}
          </div>
          {thread.unearned_payoff && <small className="observatory-thread-warning">Payoff has no approved setup in the accessible series evidence.</small>}
          {thread.unanchored_reveal && <small className="observatory-thread-warning">Revealed information has no explicit sourced setup. It is not counted as a payoff.</small>}
        </article>)}</div> : <div className="observatory-lens-empty">No source-backed plot threads yet. Establish a setup or payoff as a cited canon assertion to bring it into this view. <button onClick={onOpenCanon}>Open Canon Graph</button></div>}
      {threads.length > 12 && <button className="observatory-expand" onClick={() => setExpanded(!expanded)}>{expanded ? 'Show fewer threads' : 'Explore more threads'}</button>}
    </div>
  }
  const grouped = Object.entries(snapshot.facts.reduce<Record<string, ObservatoryFact[]>>((acc,fact) => {
    const key = String(fact.start_book)
    ;(acc[key] ||= []).push(fact)
    return acc
  },{})).sort((a,b)=>Number(a[0])-Number(b[0]))
  return <div className="observatory-lens-body observatory-chronicle">
    <div className="observatory-lens-intro"><span>EVIDENCE CHRONICLE</span><h3>The evolving truth of your universe.</h3>
      <p>Approved claims appear where their validity begins. This records authored book chronology, not guessed in-world dates.</p></div>
    {grouped.length ? <div className="observatory-chronicle-track">
      {grouped.map(([book,events]) => <section key={book}>
        <div className="observatory-chronicle-book"><span>BOOK {book}</span><strong>{events.length} established facts</strong></div>
        <div className="observatory-chronicle-events">{events.slice(0,expanded?200:8).map(event =>
          <article key={event.id}><small>{scopeLabels[event.scope] || readable(event.scope)}</small>
            <button onClick={() => onExplore(event.subject_id)}>{event.subject_name} ↗</button>
            <p>{readable(event.predicate)} <strong>{event.object_name || event.object_text}</strong></p>
            <blockquote>“{event.quote}”</blockquote>
          </article>)}</div>
        {!expanded && events.length > 8 && <small className="observatory-muted">+{events.length-8} more citations in this book</small>}
      </section>)}
    </div> : <div className="observatory-lens-empty">No approved facts at this story point. <button onClick={onOpenCanon}>Review sources</button></div>}
    {grouped.some(([,events])=>events.length>8) && <button className="observatory-expand" onClick={() => setExpanded(!expanded)}>{expanded?'Show highlights':'Show more cited events'}</button>}
  </div>
}

