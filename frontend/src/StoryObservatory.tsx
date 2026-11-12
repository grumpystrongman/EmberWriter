import { useMemo, useState } from 'react'
import './story-observatory.css'

export type ObservatoryEntity = { id: string; name: string; kind: string; aliases: string[]; description: string }
export type ObservatoryFact = {
  id: string; subject_id: string; subject_name: string; predicate: string;
  object_text: string; object_name: string | null; scope: string;
  knower_name: string | null; status: string; start_book: number; end_book: number | null;
  quote: string; reference: { volume: string; book: number; title: string; source_path: string; start: number; end: number }
}
export type ObservatoryVolume = { id: string; ordinal: number; title: string }
type Props = {
  entities: ObservatoryEntity[]
  facts: ObservatoryFact[]
  volumes: ObservatoryVolume[]
  onReview: (factId: string, decision: 'approved' | 'rejected') => void
  busy: boolean
  onOpenCanon: () => void
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

export default function StoryObservatory({ entities, facts, volumes, onReview, busy, onOpenCanon }: Props) {
  const books = useMemo(() => [...volumes].sort((a, b) => a.ordinal - b.ordinal), [volumes])
  const [bookOverride, setBookOverride] = useState<number | null>(null)
  const book = books.some(item => item.ordinal === bookOverride) ? bookOverride! : (books[books.length - 1]?.ordinal ?? 1)
  const [scope, setScope] = useState<'all' | 'world' | 'character_belief' | 'reader_reveal'>('all')
  const [status, setStatus] = useState<'approved' | 'proposed' | 'all'>('approved')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [showEvidence, setShowEvidence] = useState<string | null>(null)
  const [showAll, setShowAll] = useState(false)

  const visibleFacts = useMemo(() => facts.filter(fact =>
    (status === 'all' ? fact.status !== 'rejected' : fact.status === status) &&
    (scope === 'all' || fact.scope === scope) &&
    fact.start_book <= book && (fact.end_book == null || fact.end_book >= book)
  ), [facts, status, scope, book])
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
  const pending = facts.filter(fact => fact.status === 'proposed')
  const highlighted = new Set([selected?.name, ...connectedNames].filter(Boolean))
  const nodes = showAll ? matching : matching.slice(0, 32)

  return <section className="story-observatory" aria-label="Interactive story observatory">
    <header className="observatory-hero">
      <div>
        <span className="observatory-kicker">PART I · LIVING STORY INTELLIGENCE</span>
        <h2>Your universe, in motion.</h2>
        <p>Explore what is established, what someone believes, and what remains unapproved—at any point in your series.</p>
      </div>
      <div className="observatory-hero-stats" aria-label="Story state summary">
        <div><strong>{entities.length}</strong><span>Story entities</span></div>
        <div><strong>{facts.filter(f => f.status === 'approved').length}</strong><span>Approved facts</span></div>
        <div><strong>{pending.length}</strong><span>Awaiting review</span></div>
      </div>
    </header>

    <div className="observatory-stage">
      <div className="observatory-toolbar">
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
      </div>

      <div className="observatory-main">
        <div className="observatory-constellation" aria-label="Selectable story entities">
          <div className="observatory-constellation-title"><span>STORY CONSTELLATION</span><small>Select any node to inspect its history</small></div>
          {nodes.length ? <div className="observatory-node-grid">
            {nodes.map(entity => {
              const color = kindInfo(entity.kind).color
              const relevant = visibleFacts.filter(fact => fact.subject_id === entity.id ||
                fact.object_name?.toLocaleLowerCase() === entity.name.toLocaleLowerCase())
              return <button key={entity.id} type="button"
                className={['observatory-node',selected?.id === entity.id ? 'selected' : '',
                  selected?.id !== entity.id && highlighted.has(entity.name) ? 'related' : ''].join(' ')}
                style={{ '--node-accent': color } as React.CSSProperties}
                aria-pressed={selected?.id === entity.id}
                onClick={() => { setSelectedId(entity.id); setShowEvidence(null) }}>
                <span className="observatory-node-icon" aria-hidden="true">{kindInfo(entity.kind).icon}</span>
                <strong title={entity.name}>{entity.name}</strong>
                <small>{readable(entity.kind)} · {relevant.length} {relevant.length === 1 ? 'fact' : 'facts'}</small>
              </button>
            })}
          </div> : <div className="observatory-empty">
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
              <div className="observatory-avatar" style={{ '--node-accent':kindInfo(selected.kind).color } as React.CSSProperties}>{kindInfo(selected.kind).icon}</div>
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
          onClick={() => { setBookOverride(volume.ordinal); setShowEvidence(null) }}>
          <span>BOOK {volume.ordinal}</span><strong>{volume.title}</strong>
        </button>) : <span className="observatory-muted">Add books to activate the story time machine.</span>}
      </div>
      <p className="observatory-provenance">Read-only exploration, except explicit Approve/Reject actions. All knowledge comes from your local Series Vault; no model request is made by this view.</p>
    </footer>
  </section>
