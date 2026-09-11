import { useEffect, useMemo, useState } from 'react'

import type { MemoryFact } from './MemoryPanel'
import type { ProviderConfig, WorkspaceProject } from './workspace-types'

type Props = {
  apiBase: string
  project: WorkspaceProject
  onOpenSource: (path: string, anchor?: string) => void
}

type ProjectDetail = { files: string[] }
type Depth = 'focused' | 'detailed' | 'exhaustive'

type GenerationResponse = { text: string }

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

function slugify(value: string) {
  return value.toLowerCase().trim().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'world-note'
}

function titleFromPath(path: string) {
  return (path.split('/').at(-1) || path).replace(/\.(md|txt)$/i, '').replace(/[-_]+/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function depthInstruction(depth: Depth) {
  if (depth === 'focused') return 'Keep it concise and reference-friendly, roughly 500–800 words.'
  if (depth === 'exhaustive') return 'Be exhaustive where evidence supports it: 2,000–3,500 words with history, current state, sensory detail, rules, exceptions, stakeholders, conflicts, scene-useful details, continuity constraints, known unknowns, and clearly labeled author decisions still open.'
  return 'Create a detailed reference article of roughly 1,000–1,800 words, emphasizing scene-useful facts, rules, history, sensory details, conflicts, and continuity constraints.'
}

export default function WorldWorkspace({ apiBase, project, onOpenSource }: Props) {
  const [facts, setFacts] = useState<MemoryFact[]>([])
  const [files, setFiles] = useState<string[]>([])
  const [selectedFile, setSelectedFile] = useState('')
  const [note, setNote] = useState('')
  const [dirty, setDirty] = useState(false)
  const [newTitle, setNewTitle] = useState('')
  const [newKind, setNewKind] = useState('Location')
  const [depth, setDepth] = useState<Depth>('detailed')
  const [filter, setFilter] = useState('all')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const worldFiles = useMemo(
    () => files.filter((path) => path.startsWith('world/') && /\.(md|txt)$/i.test(path) && !path.endsWith('/README.md')),
    [files],
  )
  const worldFacts = useMemo(
    () => facts.filter((fact) => ['canon', 'location', 'object', 'ability', 'thread'].includes(fact.kind)),
    [facts],
  )
  const filteredFacts = useMemo(
    () => filter === 'all' ? worldFacts : worldFacts.filter((fact) => fact.kind === filter),
    [worldFacts, filter],
  )
  const counts = useMemo(() => {
    const result: Record<string, number> = {}
    for (const fact of worldFacts) result[fact.kind] = (result[fact.kind] || 0) + 1
    return result
  }, [worldFacts])

  useEffect(() => { void load() }, [project.slug])
  useEffect(() => { if (selectedFile) void loadNote(selectedFile) }, [selectedFile, project.slug])

  async function load() {
    setError('')
    try {
      const [memory, detail] = await Promise.all([
        request<MemoryFact[]>(`${apiBase}/projects/${project.slug}/memory?limit=200`),
        request<ProjectDetail>(`${apiBase}/projects/${project.slug}`),
      ])
      setFacts(memory)
      setFiles(detail.files)
      const first = detail.files.find((path) => path.startsWith('world/') && /\.(md|txt)$/i.test(path) && !path.endsWith('/README.md')) || ''
      setSelectedFile((current) => current && detail.files.includes(current) ? current : first)
    } catch (cause) {
      setError((cause as Error).message)
    }
  }

  async function loadNote(path: string) {
    try {
      const response = await request<{ content: string }>(`${apiBase}/projects/${project.slug}/file?path=${encodeURIComponent(path)}`)
      setNote(response.content)
      setDirty(false)
    } catch (cause) {
      setError((cause as Error).message)
    }
  }

  async function createNote() {
    if (!newTitle.trim()) return
    const path = `world/${slugify(newTitle)}.md`
    const content = `# ${newTitle.trim()}\n\n**Type:** ${newKind}\n\n## Canon\n\n\n## History\n\n\n## Current state\n\n\n## Rules & constraints\n\n\n## Sensory / scene details\n\n\n## Related characters & conflicts\n\n`
    setBusy(true)
    try {
      await request(`${apiBase}/projects/${project.slug}/file?path=${encodeURIComponent(path)}`, {
        method: 'PUT',
        body: JSON.stringify({ content }),
      })
      const detail = await request<ProjectDetail>(`${apiBase}/projects/${project.slug}`)
      setFiles(detail.files)
      setSelectedFile(path)
      setNote(content)
      setDirty(false)
      setNewTitle('')
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function saveNote() {
    if (!selectedFile) return
    setBusy(true)
    try {
      await request(`${apiBase}/projects/${project.slug}/file?path=${encodeURIComponent(selectedFile)}`, {
        method: 'PUT',
        body: JSON.stringify({ content: note }),
      })
      setDirty(false)
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function generateNote(expand: boolean) {
    const provider = currentProvider()
    if (!provider) {
      setError('Choose an AI model before generating World Bible material.')
      return
    }
    const title = selectedFile ? titleFromPath(selectedFile) : newTitle.trim()
    if (!title) {
      setError('Create or select a World Bible article first.')
      return
    }
    setBusy(true)
    setError('')
    try {
      const response = await request<GenerationResponse>(`${apiBase}/projects/${project.slug}/generate`, {
        method: 'POST',
        body: JSON.stringify({
          prompt: [
            `Create a World Bible reference article for “${title}” in the novel “${project.name}”.`,
            depthInstruction(depth),
            'Ground established facts in the manuscript, Story Memory, and saved world files. Do not invent canon silently.',
            'Put plausible but unconfirmed additions under “Author decisions still open” so the author can accept, revise, or delete them.',
            'Use clean Markdown with useful headings. Keep contradictions and uncertainty visible instead of smoothing them away.',
            expand && note.trim() ? `Expand this author-edited article while preserving deliberate decisions:\n\n${note}` : 'Build the article from current story evidence.',
          ].join('\n\n'),
          mode: 'brainstorm',
          active_file: project.activePath || null,
          selected_text: null,
          provider,
          craft: { voice_lock: false, quality_pass: false },
        }),
      })
      setNote(response.text.trim() + '\n')
      setDirty(true)
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="center-tool world-workspace">
      <header className="center-tool-header">
        <div><small>WORLD · {project.name}</small><h1>World Bible</h1><p>Canon, locations, objects, abilities, factions, rules, and lore—derived from the book where possible and always editable by you.</p></div>
        <div className="center-tool-actions">
          <button type="button" onClick={() => void load()} disabled={busy}>↻ Refresh</button>
          <select value={depth} onChange={(event) => setDepth(event.target.value as Depth)}><option value="focused">AI depth: Focused</option><option value="detailed">AI depth: Detailed</option><option value="exhaustive">AI depth: Exhaustive</option></select>
        </div>
      </header>

      <div className="world-layout">
        <aside className="world-index">
          <div className="world-create-card">
            <strong>New World Bible article</strong>
            <input value={newTitle} onChange={(event) => setNewTitle(event.target.value)} placeholder="Location, faction, rule…" />
            <select value={newKind} onChange={(event) => setNewKind(event.target.value)}><option>Location</option><option>Faction</option><option>Magic / Ability</option><option>Technology</option><option>Object</option><option>History</option><option>Culture</option><option>Rule</option><option>General Canon</option></select>
            <button type="button" className="primary" onClick={() => void createNote()} disabled={busy || !newTitle.trim()}>Create article</button>
          </div>
          <div className="world-file-list">
            <strong>Author Bible</strong>
            {worldFiles.length === 0 && <small>No authored world articles yet.</small>}
            {worldFiles.map((path) => <button type="button" key={path} className={selectedFile === path ? 'active' : ''} onClick={() => setSelectedFile(path)}><span>◇</span><div><b>{titleFromPath(path)}</b><small>{path}</small></div></button>)}
          </div>
        </aside>

        <main className="world-main">
          <section className="world-canon-browser">
            <div className="center-section-heading"><div><h2>Story-derived canon</h2><p>These facts come from Story Memory. Click any fact to inspect the manuscript source.</p></div></div>
            <div className="world-fact-filters">
              <button type="button" className={filter === 'all' ? 'active' : ''} onClick={() => setFilter('all')}>All <span>{worldFacts.length}</span></button>
              {['canon', 'location', 'object', 'ability', 'thread'].map((kind) => <button type="button" key={kind} className={filter === kind ? 'active' : ''} onClick={() => setFilter(kind)}>{kind.replaceAll('_', ' ')} <span>{counts[kind] || 0}</span></button>)}
            </div>
            <div className="world-fact-grid">
              {filteredFacts.slice(0, 60).map((fact) => (
                <button type="button" className="world-fact-card" key={fact.id} onClick={() => onOpenSource(fact.source_path, fact.object)}>
                  <small>{fact.kind.toUpperCase()} · ch {fact.chapter_order || '?'}</small>
                  <strong>{fact.subject}</strong>
                  <span>{fact.predicate} {fact.object}</span>
                </button>
              ))}
              {filteredFacts.length === 0 && <div className="center-empty">No matching Story Memory facts yet.</div>}
            </div>
          </section>

          <section className="world-editor-card">
            <div className="center-section-heading"><div><h2>{selectedFile ? titleFromPath(selectedFile) : 'World article editor'}</h2><p>{selectedFile || 'Create an article to begin.'}</p></div><div className="center-tool-actions"><button type="button" className="primary" onClick={() => void generateNote(false)} disabled={busy || !selectedFile}>{busy ? 'Working…' : 'AI generate article'}</button><button type="button" onClick={() => void generateNote(true)} disabled={busy || !selectedFile || !note.trim()}>AI expand / deepen</button><button type="button" onClick={() => void saveNote()} disabled={busy || !dirty}>{dirty ? 'Save article' : 'Saved'}</button></div></div>
            <textarea className="planning-document world-note-editor" value={note} onChange={(event) => { setNote(event.target.value); setDirty(true) }} disabled={!selectedFile} spellCheck placeholder="Select or create a World Bible article…" />
          </section>
        </main>
      </div>

      {error && <div className="center-error">{error}</div>}
    </section>
  )
}
