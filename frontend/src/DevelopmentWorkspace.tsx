import { useEffect, useMemo, useState } from 'react'

import type { ProviderConfig, WorkspaceProject } from './workspace-types'
import './development.css'

type PlotBeat = {
  id: string
  title: string
  act: string
  chapter: number
  scene: number
  status: string
  pov: string
  summary: string
  purpose: string
  characters: string[]
  thread_ids: string[]
  source_path: string
  notes: string
}

type CharacterArc = {
  character: string
  want: string
  need: string
  wound: string
  lie: string
  starting_state: string
  midpoint_shift: string
  climax_choice: string
  ending_state: string
  beat_ids: string[]
  notes: string
}

type RelationshipState = {
  id: string
  participants: string[]
  label: string
  status: string
  trust: number
  closeness: number
  conflict: number
  chapter: number
  boundaries: string[]
  milestones: string[]
  unresolved_tension: string[]
  notes: string
}

type StoryThread = {
  id: string
  title: string
  kind: string
  status: string
  introduced_chapter: number
  target_payoff_chapter: number
  setup: string
  payoff: string
  participants: string[]
  beat_ids: string[]
  source_paths: string[]
  notes: string
}

type DevelopmentState = {
  schema_version: number
  beats: PlotBeat[]
  character_arcs: CharacterArc[]
  relationships: RelationshipState[]
  threads: StoryThread[]
  updated_at: string
}

type Tab = 'beats' | 'character_arcs' | 'relationships' | 'threads'

type Props = {
  apiBase: string
  project: WorkspaceProject
  onOpenSource: (path: string, anchor?: string) => void
}

const emptyState: DevelopmentState = {
  schema_version: 1,
  beats: [],
  character_arcs: [],
  relationships: [],
  threads: [],
  updated_at: '',
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || `${response.status} ${response.statusText}`)
  }
  return response.json() as Promise<T>
}

function currentProvider(): ProviderConfig | null {
  try {
    const parsed = JSON.parse(localStorage.getItem('emberwriter.provider') || 'null') as ProviderConfig | null
    return parsed?.model?.trim() && parsed.base_url?.trim() ? parsed : null
  } catch {
    return null
  }
}

function id(prefix: string) {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`
}

function csv(value: string) {
  return value.split(',').map((item) => item.trim()).filter(Boolean)
}

function csvText(values: string[]) {
  return values.join(', ')
}

function move<T>(items: T[], index: number, direction: -1 | 1) {
  const target = index + direction
  if (target < 0 || target >= items.length) return items
  const next = [...items]
  ;[next[index], next[target]] = [next[target], next[index]]
  return next
}

function Metric({ label, value, onChange }: { label: string; value: number; onChange: (value: number) => void }) {
  return (
    <label className="relationship-metric">
      <span>{label}<b>{value}/5</b></span>
      <input type="range" min="0" max="5" step="1" value={value} onChange={(event) => onChange(Number(event.target.value))} />
    </label>
  )
}

function RelationshipGraph({ relationships }: { relationships: RelationshipState[] }) {
  const names = useMemo(() => {
    const unique = new Set<string>()
    for (const relationship of relationships) relationship.participants.forEach((name) => unique.add(name))
    return [...unique].sort()
  }, [relationships])

  const points = useMemo(() => {
    const center = 240
    const radius = names.length <= 4 ? 145 : 175
    return new Map(names.map((name, index) => {
      const angle = (Math.PI * 2 * index) / Math.max(1, names.length) - Math.PI / 2
      return [name, { x: center + Math.cos(angle) * radius, y: center + Math.sin(angle) * radius }]
    }))
  }, [names])

  if (names.length < 2) return <div className="development-empty">Add a relationship with at least two characters to build the network.</div>

  return (
    <div className="relationship-graph-wrap">
      <svg className="relationship-graph" viewBox="0 0 480 480" role="img" aria-label="Relationship network">
        {relationships.map((relationship) => {
          const first = points.get(relationship.participants[0])
          if (!first) return null
          return relationship.participants.slice(1).map((name) => {
            const target = points.get(name)
            if (!target) return null
            const intensity = Math.max(1, relationship.trust + relationship.closeness + relationship.conflict)
            return (
              <g key={`${relationship.id}-${name}`}>
                <line x1={first.x} y1={first.y} x2={target.x} y2={target.y} className="relationship-line" style={{ strokeWidth: Math.min(8, 1 + intensity / 3) }} />
                <text x={(first.x + target.x) / 2} y={(first.y + target.y) / 2 - 7} className="relationship-edge-label">{relationship.label || relationship.status || 'relationship'}</text>
              </g>
            )
          })
        })}
        {names.map((name) => {
          const point = points.get(name)!
          return (
            <g className="relationship-node" key={name} transform={`translate(${point.x}, ${point.y})`}>
              <circle r="36" />
              <text textAnchor="middle" dominantBaseline="middle">{name.length > 12 ? `${name.slice(0, 11)}…` : name}</text>
            </g>
          )
        })}
      </svg>
    </div>
  )
}

export default function DevelopmentWorkspace({ apiBase, project, onOpenSource }: Props) {
  const [state, setState] = useState<DevelopmentState>(emptyState)
  const [tab, setTab] = useState<Tab>('beats')
  const [dirty, setDirty] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [aiInstruction, setAiInstruction] = useState('')

  useEffect(() => { void load() }, [project.slug])

  async function load() {
    setError('')
    try {
      setState(await request<DevelopmentState>(`${apiBase}/projects/${project.slug}/development`))
      setDirty(false)
    } catch (cause) {
      setError((cause as Error).message)
    }
  }

  async function save(next = state) {
    setBusy(true)
    setError('')
    try {
      const saved = await request<DevelopmentState>(`${apiBase}/projects/${project.slug}/development`, {
        method: 'PUT',
        body: JSON.stringify(next),
      })
      setState(saved)
      setDirty(false)
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function aiDevelop() {
    const provider = currentProvider()
    if (!provider) {
      setError('Choose a model in Ember model settings before asking AI to develop the Story Map.')
      return
    }
    if (dirty) await save()
    setBusy(true)
    setError('')
    try {
      const response = await request<{ state: DevelopmentState }>(`${apiBase}/projects/${project.slug}/development/generate`, {
        method: 'POST',
        body: JSON.stringify({ area: tab, instruction: aiInstruction.trim(), provider, replace_area: false }),
      })
      setState(response.state)
      setDirty(false)
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  function change(next: DevelopmentState) {
    setState(next)
    setDirty(true)
  }

  function addBeat() {
    change({ ...state, beats: [...state.beats, { id: id('beat'), title: 'New beat', act: '', chapter: 0, scene: 0, status: 'planned', pov: '', summary: '', purpose: '', characters: [], thread_ids: [], source_path: '', notes: '' }] })
  }

  function addArc() {
    change({ ...state, character_arcs: [...state.character_arcs, { character: 'New character', want: '', need: '', wound: '', lie: '', starting_state: '', midpoint_shift: '', climax_choice: '', ending_state: '', beat_ids: [], notes: '' }] })
  }

  function addRelationship() {
    change({ ...state, relationships: [...state.relationships, { id: id('rel'), participants: ['Character A', 'Character B'], label: '', status: '', trust: 0, closeness: 0, conflict: 0, chapter: 0, boundaries: [], milestones: [], unresolved_tension: [], notes: '' }] })
  }

  function addThread() {
    change({ ...state, threads: [...state.threads, { id: id('thread'), title: 'New thread', kind: 'setup_payoff', status: 'open', introduced_chapter: 0, target_payoff_chapter: 0, setup: '', payoff: '', participants: [], beat_ids: [], source_paths: [], notes: '' }] })
  }

  const counts = { beats: state.beats.length, character_arcs: state.character_arcs.length, relationships: state.relationships.length, threads: state.threads.length }

  return (
    <section className="development-workspace">
      <div className="development-header">
        <div>
          <small>AUTHOR-OWNED STRUCTURE</small>
          <h2>Story Map</h2>
          <p>Plan the book as connected state, not scattered notes. Everything here is editable by you and becomes context Ember uses when writing.</p>
        </div>
        <div className="development-save-actions">
          <button type="button" onClick={() => void load()} disabled={busy}>Reload</button>
          <button type="button" className="primary" onClick={() => void save()} disabled={busy || !dirty}>{dirty ? 'Save Story Map' : 'Saved'}</button>
        </div>
      </div>

      <nav className="development-tabs">
        {([
          ['beats', 'Plot Beats'], ['character_arcs', 'Character Arcs'], ['relationships', 'Relationships'], ['threads', 'Threads & Payoffs'],
        ] as [Tab, string][]).map(([value, label]) => (
          <button type="button" key={value} className={tab === value ? 'active' : ''} onClick={() => setTab(value)}>{label}<span>{counts[value]}</span></button>
        ))}
      </nav>

      <div className="development-ai-bar">
        <div><strong>Ember development pass</strong><small>AI edits the active section from manuscript evidence and your existing Story Map. You remain free to change every field afterward.</small></div>
        <input value={aiInstruction} onChange={(event) => setAiInstruction(event.target.value)} placeholder={`Optional direction for ${tab.replace('_', ' ')}…`} />
        <button type="button" onClick={() => void aiDevelop()} disabled={busy}>{busy ? 'Working…' : 'AI build / deepen'}</button>
      </div>

      {tab === 'beats' && (
        <div className="development-list">
          <div className="development-section-bar"><div><h3>Plot beats</h3><p>Order the causal spine of the story. Link beats to open threads so setups and payoffs stay visible.</p></div><button type="button" onClick={addBeat}>+ Beat</button></div>
          {state.beats.length === 0 && <div className="development-empty">No structured beats yet. Add one yourself or ask Ember to build a manuscript-grounded first pass.</div>}
          {state.beats.map((beat, index) => (
            <article className="development-card beat-card" key={beat.id}>
              <div className="development-card-head"><span className="beat-number">{index + 1}</span><input className="development-title-input" value={beat.title} onChange={(event) => { const beats = [...state.beats]; beats[index] = { ...beat, title: event.target.value }; change({ ...state, beats }) }} /><div className="card-order-actions"><button onClick={() => change({ ...state, beats: move(state.beats, index, -1) })} disabled={index === 0}>↑</button><button onClick={() => change({ ...state, beats: move(state.beats, index, 1) })} disabled={index === state.beats.length - 1}>↓</button><button onClick={() => change({ ...state, beats: state.beats.filter((item) => item.id !== beat.id) })}>Delete</button></div></div>
              <div className="development-fields four">
                <label>Act<input value={beat.act} onChange={(event) => { const beats = [...state.beats]; beats[index] = { ...beat, act: event.target.value }; change({ ...state, beats }) }} /></label>
                <label>Chapter<input type="number" min="0" value={beat.chapter} onChange={(event) => { const beats = [...state.beats]; beats[index] = { ...beat, chapter: Number(event.target.value) }; change({ ...state, beats }) }} /></label>
                <label>Scene<input type="number" min="0" value={beat.scene} onChange={(event) => { const beats = [...state.beats]; beats[index] = { ...beat, scene: Number(event.target.value) }; change({ ...state, beats }) }} /></label>
                <label>Status<select value={beat.status} onChange={(event) => { const beats = [...state.beats]; beats[index] = { ...beat, status: event.target.value }; change({ ...state, beats }) }}><option>planned</option><option>drafted</option><option>revised</option><option>cut</option></select></label>
                <label>POV<input value={beat.pov} onChange={(event) => { const beats = [...state.beats]; beats[index] = { ...beat, pov: event.target.value }; change({ ...state, beats }) }} /></label>
                <label className="span-three">Characters<input value={csvText(beat.characters)} onChange={(event) => { const beats = [...state.beats]; beats[index] = { ...beat, characters: csv(event.target.value) }; change({ ...state, beats }) }} placeholder="Comma separated" /></label>
                <label className="span-two">Summary<textarea rows={3} value={beat.summary} onChange={(event) => { const beats = [...state.beats]; beats[index] = { ...beat, summary: event.target.value }; change({ ...state, beats }) }} /></label>
                <label className="span-two">Story purpose<textarea rows={3} value={beat.purpose} onChange={(event) => { const beats = [...state.beats]; beats[index] = { ...beat, purpose: event.target.value }; change({ ...state, beats }) }} /></label>
                <label className="span-two">Linked thread IDs<input value={csvText(beat.thread_ids)} onChange={(event) => { const beats = [...state.beats]; beats[index] = { ...beat, thread_ids: csv(event.target.value) }; change({ ...state, beats }) }} /></label>
                <label className="span-two">Source path<input value={beat.source_path} onChange={(event) => { const beats = [...state.beats]; beats[index] = { ...beat, source_path: event.target.value }; change({ ...state, beats }) }} />{beat.source_path && <button type="button" className="inline-source" onClick={() => onOpenSource(beat.source_path, beat.summary)}>Open source</button>}</label>
              </div>
            </article>
          ))}
        </div>
      )}

      {tab === 'character_arcs' && (
        <div className="development-list">
          <div className="development-section-bar"><div><h3>Character arcs</h3><p>Separate what a character wants from what they need, then make the midpoint and climax force real choices.</p></div><button type="button" onClick={addArc}>+ Arc</button></div>
          {state.character_arcs.map((arc, index) => (
            <article className="development-card arc-card" key={`${arc.character}-${index}`}>
              <div className="development-card-head"><input className="development-title-input" value={arc.character} onChange={(event) => { const character_arcs = [...state.character_arcs]; character_arcs[index] = { ...arc, character: event.target.value }; change({ ...state, character_arcs }) }} /><button onClick={() => change({ ...state, character_arcs: state.character_arcs.filter((_, itemIndex) => itemIndex !== index) })}>Delete</button></div>
              <div className="development-fields two">
                {([['want', 'External want'], ['need', 'Internal need'], ['wound', 'Wound / pressure'], ['lie', 'Lie / false belief'], ['starting_state', 'Starting state'], ['midpoint_shift', 'Midpoint shift'], ['climax_choice', 'Climax choice'], ['ending_state', 'Ending state']] as [keyof CharacterArc, string][]).map(([key, label]) => (
                  <label key={key}>{label}<textarea rows={3} value={String(arc[key] || '')} onChange={(event) => { const character_arcs = [...state.character_arcs]; character_arcs[index] = { ...arc, [key]: event.target.value }; change({ ...state, character_arcs }) }} /></label>
                ))}
                <label className="span-two">Linked beat IDs<input value={csvText(arc.beat_ids)} onChange={(event) => { const character_arcs = [...state.character_arcs]; character_arcs[index] = { ...arc, beat_ids: csv(event.target.value) }; change({ ...state, character_arcs }) }} /></label>
                <label className="span-two">Author notes<textarea rows={3} value={arc.notes} onChange={(event) => { const character_arcs = [...state.character_arcs]; character_arcs[index] = { ...arc, notes: event.target.value }; change({ ...state, character_arcs }) }} /></label>
              </div>
            </article>
          ))}
          {state.character_arcs.length === 0 && <div className="development-empty">No arcs yet. Create one manually or let Ember draft them from the character dossiers and manuscript.</div>}
        </div>
      )}

      {tab === 'relationships' && (
        <div className="development-list relationship-development">
          <div className="development-section-bar"><div><h3>Relationship network</h3><p>The graph summarizes the network; the cards below are the source of truth you control.</p></div><button type="button" onClick={addRelationship}>+ Relationship</button></div>
          <RelationshipGraph relationships={state.relationships} />
          <div className="relationship-card-grid">
            {state.relationships.map((relationship, index) => (
              <article className="development-card relationship-card" key={relationship.id}>
                <div className="development-card-head"><input className="development-title-input" value={csvText(relationship.participants)} onChange={(event) => { const relationships = [...state.relationships]; relationships[index] = { ...relationship, participants: csv(event.target.value) }; change({ ...state, relationships }) }} /><button onClick={() => change({ ...state, relationships: state.relationships.filter((item) => item.id !== relationship.id) })}>Delete</button></div>
                <div className="development-fields two">
                  <label>Relationship label<input value={relationship.label} onChange={(event) => { const relationships = [...state.relationships]; relationships[index] = { ...relationship, label: event.target.value }; change({ ...state, relationships }) }} /></label>
                  <label>Current chapter<input type="number" min="0" value={relationship.chapter} onChange={(event) => { const relationships = [...state.relationships]; relationships[index] = { ...relationship, chapter: Number(event.target.value) }; change({ ...state, relationships }) }} /></label>
                  <label className="span-two">Current state<textarea rows={3} value={relationship.status} onChange={(event) => { const relationships = [...state.relationships]; relationships[index] = { ...relationship, status: event.target.value }; change({ ...state, relationships }) }} /></label>
                </div>
                <div className="relationship-metrics">
                  <Metric label="Trust" value={relationship.trust} onChange={(value) => { const relationships = [...state.relationships]; relationships[index] = { ...relationship, trust: value }; change({ ...state, relationships }) }} />
                  <Metric label="Closeness" value={relationship.closeness} onChange={(value) => { const relationships = [...state.relationships]; relationships[index] = { ...relationship, closeness: value }; change({ ...state, relationships }) }} />
                  <Metric label="Conflict" value={relationship.conflict} onChange={(value) => { const relationships = [...state.relationships]; relationships[index] = { ...relationship, conflict: value }; change({ ...state, relationships }) }} />
                </div>
                <div className="development-fields one">
                  <label>Boundaries<input value={csvText(relationship.boundaries)} onChange={(event) => { const relationships = [...state.relationships]; relationships[index] = { ...relationship, boundaries: csv(event.target.value) }; change({ ...state, relationships }) }} /></label>
                  <label>Milestones<textarea rows={3} value={relationship.milestones.join('\n')} onChange={(event) => { const relationships = [...state.relationships]; relationships[index] = { ...relationship, milestones: event.target.value.split('\n').map((item) => item.trim()).filter(Boolean) }; change({ ...state, relationships }) }} /></label>
                  <label>Unresolved tension<textarea rows={3} value={relationship.unresolved_tension.join('\n')} onChange={(event) => { const relationships = [...state.relationships]; relationships[index] = { ...relationship, unresolved_tension: event.target.value.split('\n').map((item) => item.trim()).filter(Boolean) }; change({ ...state, relationships }) }} /></label>
                </div>
              </article>
            ))}
          </div>
        </div>
      )}

      {tab === 'threads' && (
        <div className="development-list">
          <div className="development-section-bar"><div><h3>Threads, setups & payoffs</h3><p>Track promises the manuscript makes so they resolve intentionally instead of disappearing between drafts.</p></div><button type="button" onClick={addThread}>+ Thread</button></div>
          <div className="thread-grid">
            {state.threads.map((thread, index) => (
              <article className={`development-card thread-card thread-${thread.status}`} key={thread.id}>
                <div className="development-card-head"><input className="development-title-input" value={thread.title} onChange={(event) => { const threads = [...state.threads]; threads[index] = { ...thread, title: event.target.value }; change({ ...state, threads }) }} /><button onClick={() => change({ ...state, threads: state.threads.filter((item) => item.id !== thread.id) })}>Delete</button></div>
                <div className="development-fields two">
                  <label>Kind<select value={thread.kind} onChange={(event) => { const threads = [...state.threads]; threads[index] = { ...thread, kind: event.target.value }; change({ ...state, threads }) }}><option value="setup_payoff">Setup / payoff</option><option value="mystery">Mystery</option><option value="subplot">Subplot</option><option value="promise">Promise</option><option value="threat">Threat</option><option value="goal">Goal</option><option value="relationship">Relationship</option><option value="other">Other</option></select></label>
                  <label>Status<select value={thread.status} onChange={(event) => { const threads = [...state.threads]; threads[index] = { ...thread, status: event.target.value }; change({ ...state, threads }) }}><option value="open">Open</option><option value="resolved">Resolved</option><option value="parked">Parked</option></select></label>
                  <label>Introduced chapter<input type="number" min="0" value={thread.introduced_chapter} onChange={(event) => { const threads = [...state.threads]; threads[index] = { ...thread, introduced_chapter: Number(event.target.value) }; change({ ...state, threads }) }} /></label>
                  <label>Target payoff chapter<input type="number" min="0" value={thread.target_payoff_chapter} onChange={(event) => { const threads = [...state.threads]; threads[index] = { ...thread, target_payoff_chapter: Number(event.target.value) }; change({ ...state, threads }) }} /></label>
                  <label className="span-two">Setup<textarea rows={4} value={thread.setup} onChange={(event) => { const threads = [...state.threads]; threads[index] = { ...thread, setup: event.target.value }; change({ ...state, threads }) }} /></label>
                  <label className="span-two">Payoff / intended resolution<textarea rows={4} value={thread.payoff} onChange={(event) => { const threads = [...state.threads]; threads[index] = { ...thread, payoff: event.target.value }; change({ ...state, threads }) }} /></label>
                  <label>Participants<input value={csvText(thread.participants)} onChange={(event) => { const threads = [...state.threads]; threads[index] = { ...thread, participants: csv(event.target.value) }; change({ ...state, threads }) }} /></label>
                  <label>Linked beat IDs<input value={csvText(thread.beat_ids)} onChange={(event) => { const threads = [...state.threads]; threads[index] = { ...thread, beat_ids: csv(event.target.value) }; change({ ...state, threads }) }} /></label>
                  <label className="span-two">Source paths<input value={csvText(thread.source_paths)} onChange={(event) => { const threads = [...state.threads]; threads[index] = { ...thread, source_paths: csv(event.target.value) }; change({ ...state, threads }) }} /></label>
                </div>
                <div className="thread-source-actions">{thread.source_paths.slice(0, 4).map((path) => <button type="button" key={path} onClick={() => onOpenSource(path, thread.setup)}>Open {path.split('/').at(-1)}</button>)}</div>
              </article>
            ))}
          </div>
          {state.threads.length === 0 && <div className="development-empty">No tracked threads yet. This is where mysteries, foreshadowing, promises, threats, and setup/payoff chains become explicit.</div>}
        </div>
      )}

      {error && <div className="center-error">{error}</div>}
    </section>
  )
}
