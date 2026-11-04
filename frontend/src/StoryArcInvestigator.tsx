import { useEffect, useState } from 'react'
import './story-arc-investigator.css'

type Evidence = {
  id: string; kind: string; label: string; subject: string; meaning: string
  quote: string; line: number; decision: string; promoted_promise_id: string | null
}
type Analysis = {
  id: string; path: string; title: string; model: string; source_hash: string
  summary: string; tension: number; stale: boolean; created_at: string
  events: Evidence[]; unverified_events_rejected: number
}
type Chapter = { path: string; title: string; status: string; words: number; analysis: Analysis | null }
type Overview = {
  chapters: Chapter[]; analyzed: number; total: number; review_required: number
  historical_analyses: Analysis[]; limitations: string
}
type Dossier = { chapters: { index: number; title: string; path: string; analyzed: boolean; tension: number | null; summary: string; pending_count: number }[]; trajectories: { subject: string; events: { chapter: number; title: string; kind: string; label: string; quote: string; path: string }[] }[]; untracked_foreshadowing: { chapter: number; title: string; label: string; quote: string; decision: string }[]; analyzed: number; total: number; review_required: number; method: string }
type Props = { apiBase: string; projectSlug: string; onOpenSource: (path: string) => void }

export default function StoryArcInvestigator({ apiBase, projectSlug, onOpenSource }: Props) {
  const endpoint = `${apiBase}/projects/${encodeURIComponent(projectSlug)}/story-arcs`
  const [data, setData] = useState<Overview | null>(null)
  const [dossier, setDossier] = useState<Dossier | null>(null)
  const [path, setPath] = useState('')
  const [model, setModel] = useState('')
  const [models, setModels] = useState<string[]>([])
  const [focus, setFocus] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  async function request<T>(url = '', method = 'GET', body?: unknown): Promise<T> {
    const result = await fetch(endpoint + url, {
      method, headers: { 'Content-Type': 'application/json' },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    })
    if (!result.ok) {
      const value = await result.json().catch(() => ({}))
      throw new Error(value.detail || `HTTP ${result.status}`)
    }
    return result.json() as Promise<T>
  }

  async function refresh() {
    const result = await request<Overview>()
    setData(result)
    setPath(current => result.chapters.some(c => c.path === current) ? current : result.chapters[0]?.path || '')
    return result
  }

  useEffect(() => {
    let active = true
    setData(null); setDossier(null); setError(''); setMessage('')
    void refresh().catch(e => { if (active) setError(String(e)) })
    void fetch(`${apiBase}/models`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ provider: 'ollama', base_url: 'http://127.0.0.1:11434', model: '' }),
    }).then(async r => r.ok ? r.json() as Promise<{ models: string[] }> : { models: [] })
      .then(result => {
        if (!active) return
        const local = result.models.filter(name => !/(?:-cloud|:cloud)(?:$|[-:])/i.test(name))
        setModels(local)
        setModel(local[0] || '')
      }).catch(() => {})
    return () => { active = false }
  }, [endpoint])

  async function buildDossier() {
    setBusy(true); setError('')
    try { setDossier(await request<Dossier>('/dossier')) }
    catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }

  async function inspect() {
    setBusy(true); setError(''); setMessage('')
    try {
      if (!model.trim()) throw new Error('Choose an installed local Ollama model first.')
      await request('/inspect', 'POST', {
        path, focus, provider: { provider: 'ollama', base_url: 'http://127.0.0.1:11434', model },
      })
      await refresh()
      setDossier(null)
      setMessage('Chapter examined. Verify the interpretations and choose which ones to keep.')
    } catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }

  async function decide(analysis: Analysis, event: Evidence, action: string) {
    setBusy(true); setError('')
    try {
      await request(`/${encodeURIComponent(analysis.id)}/events/${encodeURIComponent(event.id)}`,
        'POST', { action })
      await refresh()
      setDossier(null)
      setMessage(action === 'track_promise'
        ? 'This possible foreshadowing thread is now in the Story Promise Ledger for author review.'
        : 'Your editorial decision has been saved locally.')
    } catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }

  const chosen = data?.chapters.find(ch => ch.path === path)
  const assessed = data?.chapters.filter(ch => ch.analysis) ?? []

  return <section className="story-arc-investigator" aria-labelledby="arc-investigator-title">
    <header className="arc-investigator-hero">
      <small>THE NARRATIVE OBSERVATORY · EVIDENCE BEFORE OPINION</small>
      <h2 id="arc-investigator-title">Story Arc Investigator</h2>
      <p>Understand what changes in the story: decisions, consequences, relationships, revelations and promises. Local AI proposes interpretations with exact quotations. You're the final authority.</p>
      {!!data && <div className="arc-investigator-progress"><strong>{data.analyzed}/{data.total} chapters assessed</strong><strong>{data.review_required} observations awaiting your judgment</strong></div>}
    </header>
    {error && <p className="arc-investigator-error" role="alert">{error}</p>}
    {message && <p className="arc-investigator-success" role="status">{message}</p>}
    <div className="arc-investigator-controls">
      <label>Chapter to examine
        <select value={path} onChange={e => setPath(e.target.value)}>
          {!data?.chapters.length && <option value="">No chapters yet</option>}
          {data?.chapters.map(ch => <option key={ch.path} value={ch.path}>{ch.title} · {ch.status} · {ch.words} words {ch.analysis ? '✓' : ''}</option>)}
        </select>
      </label>
      <label>Local writing model
        <input list="arc-investigator-models" value={model} onChange={e => setModel(e.target.value)} placeholder="Local Ollama model" />
        <datalist id="arc-investigator-models">{models.map(name => <option key={name} value={name} />)}</datalist>
      </label>
      <label className="arc-investigator-focus">Optional investigation focus
        <input maxLength={1000} value={focus} onChange={e => setFocus(e.target.value)}
          placeholder="Does the protagonist's sacrifice cause a meaningful shift?" />
      </label>
      <button disabled={busy || !path || !model.trim()} onClick={() => void inspect()}>
        {busy ? 'Investigating this chapter…' : chosen?.analysis ? 'Reinvestigate chapter' : 'Analyze chapter'}
      </button>
    </div>
    {!!assessed.length && <div className="arc-investigator-trajectory">
      <h3>Subjective tension trajectory <small>LOCAL MODEL OPINIONS · 1–5</small></h3>
      <div className="arc-investigator-tension">
        {data?.chapters.map((chapter, idx) => <button key={chapter.path} title={`${chapter.title}: ${chapter.analysis?.tension ?? 'not analyzed'}`}
          onClick={() => setPath(chapter.path)} className={chapter.path === path ? 'active' : ''}>
          <span className="arc-investigator-tension-bar" style={{ height: chapter.analysis ? `${20 * chapter.analysis.tension}%` : '3%' }} />
          <small>{idx + 1}</small>
        </button>)}
      </div>
    </div>}
    {chosen?.analysis && <div className="arc-investigator-results">
      <h3>{chosen.title}</h3>
      <p>{chosen.analysis.summary}</p>
      <div className="arc-investigator-meta"><span>Perceived tension: {chosen.analysis.tension}/5</span><span>{chosen.analysis.model}</span><span>{new Date(chosen.analysis.created_at).toLocaleString()}</span></div>
      {chosen.analysis.unverified_events_rejected > 0 && <p className="arc-investigator-warning">{chosen.analysis.unverified_events_rejected} interpretation(s) withheld: their exact supporting quote was absent or malformed.</p>}
      {chosen.analysis.events.map(event => <article key={event.id} className="arc-investigator-event">
        <div className="arc-investigator-event-head"><strong>{event.label}</strong><span>{event.kind.toUpperCase()} · {event.decision}</span></div>
        {event.subject && <p>Subject: {event.subject}</p>}
        <blockquote>Line {event.line}: “{event.quote}”</blockquote>
        <p>{event.meaning}</p>
        {event.promoted_promise_id && <p>Added to the author-owned Story Promise Ledger.</p>}
        <div className="arc-investigator-decisions">
          <button disabled={busy} onClick={() => void decide(chosen.analysis!, event, 'accept')}>Keep observation</button>
          <button disabled={busy} onClick={() => void decide(chosen.analysis!, event, 'dismiss')}>Dismiss</button>
          {event.decision !== 'pending' && <button disabled={busy} onClick={() => void decide(chosen.analysis!, event, 'reopen')}>Reopen</button>}
          {event.kind === 'foreshadowing' && !event.promoted_promise_id && <button disabled={busy} onClick={() => void decide(chosen.analysis!, event, 'track_promise')}>Add to Story Promise Ledger</button>}
        </div>
      </article>)}
      {!chosen.analysis.events.length && <p>No verifiable events returned. You can ask for another investigation focus.</p>}
      {!chosen.path.startsWith('book-studio:candidate:') && <button onClick={() => onOpenSource(chosen.path)}>Open source chapter</button>}
    </div>}
    {data && <div className="arc-investigator-dossier">
      <div><h3>Whole-Book Arc Dossier</h3><p>Collect all current assessments into an evidence-backed narrative report. Only author-accepted observations become character or subject trajectories.</p></div>
      <button disabled={busy} onClick={() => void buildDossier()}>Build narrative dossier</button>
      {dossier && <a href={endpoint + '/dossier.md'} download="story-arc-dossier.md">Export as Markdown</a>}
      {dossier && <div className="arc-investigator-dossier-body">
        <p>{dossier.analyzed} of {dossier.total} chapters examined · {dossier.review_required} pending author decisions.</p>
        <h4>Chapter-to-chapter arc</h4>
        {dossier.chapters.map(ch => <article key={ch.path}><strong>{ch.index}. {ch.title}</strong><span>{ch.analyzed ? `Tension ${ch.tension}/5 · ${ch.pending_count} pending` : 'Awaiting analysis'}</span>{ch.summary && <p>{ch.summary}</p>}</article>)}
        <h4>Character and subject trajectories</h4>
        {!dossier.trajectories.length && <p>No author-accepted narrative events yet.</p>}
        {dossier.trajectories.map(subject => <article key={subject.subject}><strong>{subject.subject}</strong>{subject.events.map((event, i) => <p key={i}>Ch. {event.chapter}: {event.kind} — {event.label} <q>{event.quote}</q></p>)}</article>)}
        <h4>Possible foreshadowing to consider</h4>
        {!dossier.untracked_foreshadowing.length && <p>No untracked hypotheses in current assessments.</p>}
        {dossier.untracked_foreshadowing.map((event, i) => <article key={i}><strong>Chapter {event.chapter}: {event.label}</strong><p>{event.quote} · {event.decision}</p></article>)}
        <p className="arc-investigator-limitations">{dossier.method}</p>
      </div>}
    </div>}
    {data && <p className="arc-investigator-limitations">{data.limitations} An assessment never edits prose or declares a promise resolved. Run another assessment after changing a chapter to refresh the evidence.</p>}
  </section>
}
