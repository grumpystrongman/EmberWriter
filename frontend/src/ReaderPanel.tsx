import { useEffect, useMemo, useState } from 'react'

type Provider = {
  provider: 'ollama' | 'openai_compatible'
  base_url: string
  model: string
  api_key?: string
}

type PersonaId = 'fan' | 'casual_reader' | 'strong_editor'

type Persona = {
  id: PersonaId
  name: string
  description: string
  lens: string[]
}

type ReaderChapterNote = {
  id: string
  path: string
  binder_node_id: string | null
  position: number
  chapter_title: string
  reaction: string
  engagement: number
  pacing: number
  clarity: number
  emotional_impact: number
  favorite_moment: string
  confusion: string[]
  predictions: string[]
  character_reactions: string[]
  keep_reading: string
  craft_notes: string[]
  source_hash: string
  stale: boolean
}

type ReaderVerdict = {
  overall_reaction: string
  score: number
  audience_fit: string
  genre_fit: string
  strongest_elements: string[]
  weakest_elements: string[]
  character_feedback: string[]
  pacing_feedback: string[]
  plot_feedback: string[]
  voice_feedback: string[]
  ending_feedback: string[]
  unresolved_confusion: string[]
  fulfilled_predictions: string[]
  broken_promises: string[]
  top_revisions: string[]
  would_recommend: string
}

type ReaderRun = {
  id: string
  created_at: string
  updated_at: string
  persona: PersonaId
  persona_name: string
  genre: string
  focus: string
  status: 'reading' | 'ready_to_synthesize' | 'completed'
  current_index: number
  total_documents: number
  notes: ReaderChapterNote[]
  verdict: ReaderVerdict | null
  stale_documents: number
}

type RunSummary = Omit<ReaderRun, 'notes' | 'verdict'> & { score: number | null; metadata: Record<string, unknown> }

type Props = {
  apiBase: string
  slug: string
  disabled: boolean
  onOpenSource: (path: string) => void
}

const fallbackProvider: Provider = {
  provider: 'ollama',
  base_url: 'http://localhost:11434',
  model: '',
  api_key: '',
}

function configuredProvider(): Provider {
  try {
    const stored = localStorage.getItem('emberwriter.provider')
    return stored ? { ...fallbackProvider, ...JSON.parse(stored) } : fallbackProvider
  } catch {
    return fallbackProvider
  }
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

function listBlock(title: string, items: string[]) {
  if (!items.length) return null
  return <div className="reader-list"><strong>{title}</strong>{items.map((item, index) => <div key={`${title}-${index}`}>• {item}</div>)}</div>
}

export default function ReaderPanel({ apiBase, slug, disabled, onOpenSource }: Props) {
  const [personas, setPersonas] = useState<Persona[]>([])
  const [history, setHistory] = useState<RunSummary[]>([])
  const [run, setRun] = useState<ReaderRun | null>(null)
  const [persona, setPersona] = useState<PersonaId>('fan')
  const [genre, setGenre] = useState('General fiction')
  const [focus, setFocus] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const activePersona = useMemo(() => personas.find((item) => item.id === persona), [personas, persona])

  async function refreshHistory() {
    const runs = await request<RunSummary[]>(`${apiBase}/projects/${slug}/readers/runs`)
    setHistory(runs)
    return runs
  }

  useEffect(() => {
    if (!slug) return
    let alive = true
    Promise.all([
      request<Persona[]>(`${apiBase}/projects/${slug}/readers/personas`),
      request<RunSummary[]>(`${apiBase}/projects/${slug}/readers/runs`),
    ]).then(async ([nextPersonas, runs]) => {
      if (!alive) return
      setPersonas(nextPersonas)
      setHistory(runs)
      if (!run && runs[0]) {
        setRun(await request<ReaderRun>(`${apiBase}/projects/${slug}/readers/runs/${runs[0].id}`))
      }
    }).catch((cause) => alive && setError((cause as Error).message))
    return () => { alive = false }
  }, [apiBase, slug])

  async function createRun() {
    const provider = configuredProvider()
    if (busy || disabled || !provider.model || !genre.trim()) {
      if (!provider.model) setError('Choose a local model before creating an AI reader.')
      return
    }
    setBusy(true)
    setError('')
    try {
      const created = await request<ReaderRun>(`${apiBase}/projects/${slug}/readers/runs`, {
        method: 'POST',
        body: JSON.stringify({ persona, genre: genre.trim(), focus: focus.trim() }),
      })
      setRun(created)
      await refreshHistory()
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function readToCompletion() {
    const provider = configuredProvider()
    if (!run || run.status === 'completed' || busy || disabled || !provider.model) {
      if (!provider.model) setError('Choose a local model before starting the reader.')
      return
    }
    setBusy(true)
    setError('')
    try {
      let current = run
      while (current.status !== 'completed') {
        const result = await request<{ run: ReaderRun }>(`${apiBase}/projects/${slug}/readers/runs/${current.id}/step`, {
          method: 'POST',
          body: JSON.stringify({ provider }),
        })
        current = result.run
        setRun(current)
      }
      await refreshHistory()
    } catch (cause) {
      setError((cause as Error).message)
      try {
        setRun(await request<ReaderRun>(`${apiBase}/projects/${slug}/readers/runs/${run.id}`))
      } catch {
        // Keep the last successfully persisted reader state.
      }
    } finally {
      setBusy(false)
    }
  }

  async function openHistorical(runId: string) {
    if (!runId || busy) return
    try {
      setRun(await request<ReaderRun>(`${apiBase}/projects/${slug}/readers/runs/${runId}`))
    } catch (cause) {
      setError((cause as Error).message)
    }
  }

  const progress = run?.total_documents ? Math.round((run.current_index / run.total_documents) * 100) : 0

  return (
    <div className="reader-panel-inner">
      <div className="reader-panel-heading"><strong>AI Readers</strong><small>genre fan · casual reader · strong editor</small></div>
      <label>Reader perspective</label>
      <div className="reader-personas">
        {personas.map((item) => (
          <button key={item.id} type="button" className={persona === item.id ? 'active' : ''} onClick={() => setPersona(item.id)} disabled={busy}>
            {item.name}
          </button>
        ))}
      </div>
      {activePersona && <small className="panel-help">{activePersona.description}</small>}

      <label>Genre</label>
      <input value={genre} onChange={(event) => setGenre(event.target.value)} placeholder="Dark fantasy romance, thriller, horror…" />
      <label>Reader focus <small>optional</small></label>
      <textarea value={focus} onChange={(event) => setFocus(event.target.value)} placeholder="e.g. Does the mystery stay compelling? Does the romance earn the payoff?" />
      <button type="button" onClick={() => void createRun()} disabled={busy || disabled || !genre.trim()}>Create fresh reader</button>

      {history.length > 0 && (
        <label>Saved reader runs
          <select value={run?.id || ''} onChange={(event) => void openHistorical(event.target.value)} disabled={busy}>
            {history.map((item) => (
              <option key={item.id} value={item.id}>{new Date(item.updated_at).toLocaleString()} · {item.persona_name} · {item.genre}{item.score ? ` · ${item.score}/10` : ''}</option>
            ))}
          </select>
        </label>
      )}

      {run && (
        <>
          <div className="reader-progress">
            <div><strong>{run.persona_name}</strong><small>{run.genre}</small></div>
            <span>{run.current_index}/{run.total_documents} chapters · {progress}%</span>
          </div>
          {run.stale_documents > 0 && <small className="panel-error">{run.stale_documents} reader note{run.stale_documents === 1 ? '' : 's'} are stale because the manuscript changed. Start a fresh read for a clean verdict.</small>}
          {run.status !== 'completed' && (
            <button type="button" className="primary" onClick={() => void readToCompletion()} disabled={busy || disabled}>
              {busy ? `Reading ${Math.min(run.current_index + 1, run.total_documents)}/${run.total_documents}…` : run.current_index ? 'Resume reading to verdict' : 'Read manuscript to verdict'}
            </button>
          )}

          {run.verdict && (
            <article className="reader-verdict">
              <div className="reader-score"><strong>{run.verdict.score}/10</strong><span>{run.verdict.would_recommend}</span></div>
              <p>{run.verdict.overall_reaction}</p>
              <small><b>Audience:</b> {run.verdict.audience_fit}</small>
              <small><b>Genre fit:</b> {run.verdict.genre_fit}</small>
              {listBlock('Strongest', run.verdict.strongest_elements)}
              {listBlock('Weakest', run.verdict.weakest_elements)}
              {listBlock('Characters', run.verdict.character_feedback)}
              {listBlock('Pacing', run.verdict.pacing_feedback)}
              {listBlock('Plot', run.verdict.plot_feedback)}
              {listBlock('Voice', run.verdict.voice_feedback)}
              {listBlock('Ending', run.verdict.ending_feedback)}
              {listBlock('Unresolved confusion', run.verdict.unresolved_confusion)}
              {listBlock('Promises/payoffs', run.verdict.fulfilled_predictions)}
              {listBlock('Broken promises', run.verdict.broken_promises)}
              {listBlock('Top revisions', run.verdict.top_revisions)}
            </article>
          )}

          <details className="reader-chapter-notes">
            <summary>Chapter reactions ({run.notes.length})</summary>
            {run.notes.map((note) => (
              <article key={note.id} className={note.stale ? 'stale' : ''}>
                <button type="button" className="editorial-source" onClick={() => onOpenSource(note.path)}>
                  <span>{note.chapter_title}</span><small>{note.stale ? 'STALE' : `${note.engagement}/10 engagement`}</small>
                </button>
                <p>{note.reaction}</p>
                <div className="reader-mini-scores"><span>Pacing {note.pacing}</span><span>Clarity {note.clarity}</span><span>Emotion {note.emotional_impact}</span></div>
                {note.favorite_moment && <small><b>Favorite:</b> {note.favorite_moment}</small>}
                {listBlock('Confusion', note.confusion)}
                {listBlock('Predictions', note.predictions)}
                {listBlock('Characters', note.character_reactions)}
                {listBlock('Craft', note.craft_notes)}
              </article>
            ))}
          </details>
        </>
      )}
      {error && <small className="panel-error">{error}</small>}
    </div>
  )
}
