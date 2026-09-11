import { useEffect, useMemo, useState } from 'react'

import type { MemoryFact } from './MemoryPanel'
import type { ProviderConfig, WorkspaceProject } from './workspace-types'

type Props = {
  apiBase: string
  project: WorkspaceProject
  onOpenSource: (path: string, anchor?: string) => void
}

type TimelineEvent = {
  id: string
  title: string
  chapter: number
  detail: string
  characters: string[]
  source_path: string
  author_owned: boolean
}

type ProjectDetail = {
  files: string[]
}

type GenerationResponse = {
  text: string
  context_files: string[]
}

type Depth = 'focused' | 'detailed' | 'exhaustive'
type PlanTab = 'timeline' | 'beats' | 'scenes'

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
    const raw = localStorage.getItem('emberwriter.provider')
    if (!raw) return null
    const parsed = JSON.parse(raw) as ProviderConfig
    if (!parsed?.model?.trim() || !parsed.base_url?.trim()) return null
    return parsed
  } catch {
    return null
  }
}

function newId() {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 9)}`
}

function timelineFromFacts(facts: MemoryFact[]): TimelineEvent[] {
  return facts
    .filter((fact) => fact.kind === 'timeline')
    .map((fact) => ({
      id: fact.id,
      title: fact.subject || fact.predicate || 'Story event',
      chapter: fact.chapter_order || 0,
      detail: [fact.predicate, fact.object].filter(Boolean).join(' '),
      characters: fact.subject ? [fact.subject] : [],
      source_path: fact.source_path,
      author_owned: false,
    }))
}

function chapterLabel(chapter: number) {
  return chapter > 0 ? `Chapter ${chapter}` : 'Unplaced'
}

function depthInstruction(depth: Depth) {
  if (depth === 'focused') return 'Keep it compact: 12–18 high-value beats and only essential notes.'
  if (depth === 'exhaustive') return 'Be exhaustive. Produce a deep professional beat sheet with 35–60 beats where the manuscript supports it, act/sequence structure, setups/payoffs, character turns, reversals, midpoint, climax, aftermath, unresolved threads, pacing risks, and proposed missing connective beats clearly labeled as suggestions.'
  return 'Produce a detailed professional beat sheet with roughly 20–35 beats, act structure, character turns, setups/payoffs, reversals, climax, aftermath, and unresolved threads.'
}

export default function PlanWorkspace({ apiBase, project, onOpenSource }: Props) {
  const [tab, setTab] = useState<PlanTab>('timeline')
  const [facts, setFacts] = useState<MemoryFact[]>([])
  const [manualEvents, setManualEvents] = useState<TimelineEvent[]>([])
  const [files, setFiles] = useState<string[]>([])
  const [beatSheet, setBeatSheet] = useState('')
  const [beatDirty, setBeatDirty] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [depth, setDepth] = useState<Depth>('detailed')
  const [eventTitle, setEventTitle] = useState('')
  const [eventChapter, setEventChapter] = useState(1)
  const [eventDetail, setEventDetail] = useState('')
  const [eventCharacters, setEventCharacters] = useState('')

  const derivedEvents = useMemo(() => timelineFromFacts(facts), [facts])
  const events = useMemo(
    () => [...derivedEvents, ...manualEvents].sort((a, b) => a.chapter - b.chapter || a.title.localeCompare(b.title)),
    [derivedEvents, manualEvents],
  )
  const chapters = useMemo(() => {
    const grouped = new Map<number, TimelineEvent[]>()
    for (const event of events) {
      const list = grouped.get(event.chapter) || []
      list.push(event)
      grouped.set(event.chapter, list)
    }
    return [...grouped.entries()].sort(([a], [b]) => a - b)
  }, [events])
  const sceneFiles = useMemo(() => files.filter((path) => path.startsWith('scenes/')), [files])

  useEffect(() => {
    void load()
  }, [project.slug])

  async function load() {
    setError('')
    try {
      const [memory, detail] = await Promise.all([
        request<MemoryFact[]>(`${apiBase}/projects/${project.slug}/memory?limit=200`),
        request<ProjectDetail>(`${apiBase}/projects/${project.slug}`),
      ])
      setFacts(memory)
      setFiles(detail.files)
      try {
        const saved = await request<{ content: string }>(
          `${apiBase}/projects/${project.slug}/file?path=${encodeURIComponent('planning/beat-sheet.md')}`,
        )
        setBeatSheet(saved.content)
      } catch {
        setBeatSheet('')
      }
      try {
        const saved = await request<{ content: string }>(
          `${apiBase}/projects/${project.slug}/file?path=${encodeURIComponent('timeline/author-timeline.json')}`,
        )
        const parsed = JSON.parse(saved.content) as { events?: TimelineEvent[] }
        setManualEvents(Array.isArray(parsed.events) ? parsed.events : [])
      } catch {
        setManualEvents([])
      }
      setBeatDirty(false)
    } catch (cause) {
      setError((cause as Error).message)
    }
  }

  async function saveBeatSheet() {
    setBusy(true)
    setError('')
    try {
      await request(`${apiBase}/projects/${project.slug}/file?path=${encodeURIComponent('planning/beat-sheet.md')}`, {
        method: 'PUT',
        body: JSON.stringify({ content: beatSheet }),
      })
      setBeatDirty(false)
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function generateBeatSheet(expand: boolean) {
    const provider = currentProvider()
    if (!provider) {
      setError('Choose an AI model in Ember model settings before generating planning material.')
      return
    }
    setBusy(true)
    setError('')
    try {
      const existing = beatSheet.trim()
      const prompt = [
        `Create a professional beat sheet for the novel project “${project.name}”.`,
        depthInstruction(depth),
        'Ground every statement in the manuscript, Story Memory, character state, and saved story files available in context.',
        'Separate established story facts from proposed improvements. Never silently convert a suggestion into canon.',
        'Use clear Markdown headings and a numbered beat table or structured beat list. Include chapter/scene placement where known.',
        expand && existing
          ? `Expand and improve the author’s existing beat sheet below without discarding useful author decisions:\n\n${existing}`
          : 'Build the beat sheet from the current manuscript and story state.',
      ].join('\n\n')
      const response = await request<GenerationResponse>(`${apiBase}/projects/${project.slug}/generate`, {
        method: 'POST',
        body: JSON.stringify({
          prompt,
          mode: 'brainstorm',
          active_file: project.activePath || null,
          selected_text: null,
          provider,
          craft: { voice_lock: false, quality_pass: false },
        }),
      })
      setBeatSheet(response.text.trim() + '\n')
      setBeatDirty(true)
      setTab('beats')
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function saveTimeline(next: TimelineEvent[]) {
    setManualEvents(next)
    try {
      await request(`${apiBase}/projects/${project.slug}/file?path=${encodeURIComponent('timeline/author-timeline.json')}`, {
        method: 'PUT',
        body: JSON.stringify({ content: JSON.stringify({ schema_version: 1, events: next }, null, 2) }),
      })
    } catch (cause) {
      setError((cause as Error).message)
    }
  }

  async function addEvent() {
    if (!eventTitle.trim()) return
    const next = [
      ...manualEvents,
      {
        id: newId(),
        title: eventTitle.trim(),
        chapter: Math.max(0, Math.floor(eventChapter || 0)),
        detail: eventDetail.trim(),
        characters: eventCharacters.split(',').map((value) => value.trim()).filter(Boolean),
        source_path: '',
        author_owned: true,
      },
    ]
    await saveTimeline(next)
    setEventTitle('')
    setEventDetail('')
    setEventCharacters('')
  }

  async function removeManualEvent(id: string) {
    await saveTimeline(manualEvents.filter((event) => event.id !== id))
  }

  return (
    <section className="center-tool plan-workspace">
      <header className="center-tool-header">
        <div>
          <small>PLAN · {project.name}</small>
          <h1>Story Planning</h1>
          <p>See the story as a system. Ember can build deeply from the manuscript, or you can plan every beat and event yourself.</p>
        </div>
        <div className="center-tool-actions">
          <button type="button" onClick={() => void load()} disabled={busy}>↻ Refresh story state</button>
          <select value={depth} onChange={(event) => setDepth(event.target.value as Depth)} aria-label="AI planning depth">
            <option value="focused">AI depth: Focused</option>
            <option value="detailed">AI depth: Detailed</option>
            <option value="exhaustive">AI depth: Exhaustive</option>
          </select>
        </div>
      </header>

      <nav className="center-subtabs" aria-label="Planning tools">
        <button type="button" className={tab === 'timeline' ? 'active' : ''} onClick={() => setTab('timeline')}>Timeline <span>{events.length}</span></button>
        <button type="button" className={tab === 'beats' ? 'active' : ''} onClick={() => setTab('beats')}>Beat Sheet</button>
        <button type="button" className={tab === 'scenes' ? 'active' : ''} onClick={() => setTab('scenes')}>Scene Plans <span>{sceneFiles.length}</span></button>
      </nav>

      {tab === 'timeline' && (
        <div className="timeline-workspace">
          <div className="timeline-summary-row">
            <div><b>{derivedEvents.length}</b><span>AI-derived events</span></div>
            <div><b>{manualEvents.length}</b><span>author events</span></div>
            <div><b>{chapters.filter(([chapter]) => chapter > 0).length}</b><span>chapters represented</span></div>
          </div>

          <div className="story-timeline" aria-label="Story event timeline">
            {chapters.length === 0 && <div className="center-empty">Build Story Memory or add an event below to start the timeline.</div>}
            {chapters.map(([chapter, chapterEvents]) => (
              <section className="timeline-chapter" key={chapter}>
                <div className="timeline-marker"><span>{chapter > 0 ? chapter : '?'}</span></div>
                <div className="timeline-chapter-content">
                  <h3>{chapterLabel(chapter)}</h3>
                  <div className="timeline-event-grid">
                    {chapterEvents.map((event) => (
                      <article className={`timeline-event ${event.author_owned ? 'author-event' : 'memory-event'}`} key={event.id}>
                        <div className="timeline-event-head">
                          <strong>{event.title}</strong>
                          <small>{event.author_owned ? 'AUTHOR' : 'STORY MEMORY'}</small>
                        </div>
                        <p>{event.detail}</p>
                        {event.characters.length > 0 && <div className="tag-row">{event.characters.map((name) => <span key={name}>{name}</span>)}</div>}
                        <div className="timeline-event-actions">
                          {event.source_path && <button type="button" onClick={() => onOpenSource(event.source_path, event.detail)}>Open source</button>}
                          {event.author_owned && <button type="button" onClick={() => void removeManualEvent(event.id)}>Delete</button>}
                        </div>
                      </article>
                    ))}
                  </div>
                </div>
              </section>
            ))}
          </div>

          <section className="author-entry-card">
            <div><strong>Add an event yourself</strong><small>Author events are stored separately from AI-derived Story Memory and are always treated as intentional planning data.</small></div>
            <div className="author-entry-grid">
              <label>Event title<input value={eventTitle} onChange={(event) => setEventTitle(event.target.value)} placeholder="The bargain is broken" /></label>
              <label>Chapter<input type="number" min="0" value={eventChapter} onChange={(event) => setEventChapter(Number(event.target.value))} /></label>
              <label className="wide">What happens<textarea rows={3} value={eventDetail} onChange={(event) => setEventDetail(event.target.value)} /></label>
              <label className="wide">Characters, comma separated<input value={eventCharacters} onChange={(event) => setEventCharacters(event.target.value)} placeholder="Mara, Elias" /></label>
            </div>
            <button type="button" className="primary" onClick={() => void addEvent()} disabled={!eventTitle.trim()}>Add event to timeline</button>
          </section>
        </div>
      )}

      {tab === 'beats' && (
        <div className="beat-workspace">
          <div className="beat-toolbar">
            <button type="button" className="primary" onClick={() => void generateBeatSheet(false)} disabled={busy}>{busy ? 'Generating…' : 'AI generate full beat sheet'}</button>
            <button type="button" onClick={() => void generateBeatSheet(true)} disabled={busy || !beatSheet.trim()}>AI expand / deepen</button>
            <button type="button" onClick={() => void saveBeatSheet()} disabled={busy || !beatDirty}>{beatDirty ? 'Save beat sheet' : 'Saved'}</button>
          </div>
          <textarea
            className="planning-document"
            value={beatSheet}
            onChange={(event) => { setBeatSheet(event.target.value); setBeatDirty(true) }}
            placeholder="# Beat Sheet\n\nWrite your own structure here, or ask Ember to generate a grounded first draft from the manuscript…"
            spellCheck
          />
          <small className="center-help">This is your document. AI generation never locks it: edit, delete, rewrite, or replace any section yourself and save it with the project.</small>
        </div>
      )}

      {tab === 'scenes' && (
        <div className="scene-plan-browser">
          <div className="center-section-heading"><div><h2>Saved Scene Plans</h2><p>Scene Architect outputs remain ordinary project files. Open any one in Write to edit it directly.</p></div></div>
          {sceneFiles.length === 0 && <div className="center-empty">No saved scene plans yet. Use Scene Architect from Ember while writing, then they will appear here.</div>}
          <div className="artifact-grid">
            {sceneFiles.map((path) => (
              <button type="button" className="artifact-card" key={path} onClick={() => onOpenSource(path)}>
                <span>SCENE PLAN</span><strong>{path.split('/').at(-1)?.replace(/\.json$|\.md$/i, '')}</strong><small>{path}</small>
              </button>
            ))}
          </div>
        </div>
      )}

      {error && <div className="center-error">{error}</div>}
    </section>
  )
}
