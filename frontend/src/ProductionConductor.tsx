import { useEffect, useState } from 'react'
import './production-conductor.css'

type Chapter = {
  number: number; title: string; status: string; candidate_words: number
  reviews: { persona: string; current: boolean }[]
}
type Pipeline = {
  exists: boolean; status: string; phase?: string; message?: string; active: boolean
  current?: { chapter: number; persona: string } | null
  total?: number; drafted?: number; approved?: number; candidates?: number
  chapters?: Chapter[]; personas?: string[]; model?: string
  events?: { at: string; status: string; phase: string; message: string }[]
  handoff_current?: boolean | null
  editorial_scan_id?: string | null
  preflight?: { blockers: number; warnings: number; waived: number; editorially_ready: boolean } | null
}
type Props = {
  apiBase: string; projectSlug: string
  onNavigate: (stage: 'book_studio' | 'editorial_board') => void
}

export default function ProductionConductor({ apiBase, projectSlug, onNavigate }: Props) {
  const endpoint = `${apiBase}/projects/${encodeURIComponent(projectSlug)}/production-conductor`
  const [job, setJob] = useState<Pipeline | null>(null)
  const [model, setModel] = useState('')
  const [installed, setInstalled] = useState<string[]>([])
  const [personas, setPersonas] = useState<string[]>([])
  const [contextChapter, setContextChapter] = useState(1)
  const [contextData, setContextData] = useState<{number: number; title: string; context: string; characters: number; budget: number; disclaimer: string} | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  async function request<T>(suffix = '', method = 'GET', body?: unknown): Promise<T> {
    const response = await fetch(endpoint + suffix, {
      method, headers: { 'Content-Type': 'application/json' },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    })
    if (!response.ok) {
      const detail = await response.json().catch(() => ({}))
      throw new Error(detail.detail || `HTTP ${response.status}`)
    }
    return response.json() as Promise<T>
  }

  useEffect(() => {
    let live = true
    setJob(null); setError(''); setNotice('')
    void request<Pipeline>().then(value => { if (live) setJob(value) })
      .catch(e => { if (live) setError(String(e)) })
    void fetch(`${apiBase}/models`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ provider: 'ollama', base_url: 'http://127.0.0.1:11434', model: '' }),
    }).then(async response => response.ok ? response.json() as Promise<{ models: string[] }> : { models: [] })
      .then(data => {
        if (!live) return
        const local = data.models.filter(name => !/(?:-cloud|:cloud)(?:$|[-:])/i.test(name))
        setInstalled(local)
        setModel(current => current || local[0] || '')
      }).catch(() => {})
    const timer = window.setInterval(() => {
      void request<Pipeline>().then(value => { if (live) setJob(value) }).catch(() => {})
    }, 2500)
    return () => { live = false; window.clearInterval(timer) }
  }, [endpoint])

  async function inspectContext() {
    setBusy(true); setError('')
    try { setContextData(await request('/context/' + contextChapter)) }
    catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }

  async function action(command: 'start' | 'pause' | 'continue') {
    setBusy(true); setError(''); setNotice('')
    try {
      if (command === 'start' && !model.trim()) throw new Error('Choose an installed local Ollama model.')
      const next = await request<Pipeline>('/' + command, 'POST', command === 'start' ? {
        provider: { provider: 'ollama', base_url: 'http://127.0.0.1:11434', model: model.trim() },
        personas,
      } : undefined)
      setJob(next)
      setNotice(next.message || 'Production workflow updated.')
    } catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }

  const stages = [
    { key: 'draft', label: '1. Book drafting', description: 'Local candidates are created using the durable Book Studio queue.' },
    { key: 'reader_review', label: '2. Reader critique', description: 'Opt-in independent readers examine current candidates with exact quotations.' },
    { key: 'author_approval', label: '3. Author decisions', description: 'Review, revise, reject or approve every chapter yourself.' },
    { key: 'editorial', label: '4. Whole-book editorial audit', description: 'Run the consolidated Prose Editor and Style Bible scan.' },
    { key: 'preflight', label: '5. Publishing handoff', description: 'Review release concerns; export remains your own action.' },
  ]
  const phaseIndex = job?.phase === 'publishing_handoff' ? 5 : Math.max(0, stages.findIndex(x => x.key === job?.phase))
  return <section className="production-conductor" aria-labelledby="production-conductor-title">
    <header className="conductor-hero">
      <small>AUTHOR-LED · FULL-BOOK PRODUCTION</small>
      <h2 id="production-conductor-title">Book Production Conductor</h2>
      <p>From chapter plan to reviewed manuscript, with local drafting and a mandatory author approval gate. Your writing stays yours.</p>
    </header>
    {error && <p role="alert" className="conductor-error">{error}</p>}
    {notice && <p role="status" className="conductor-success">{notice}</p>}
    {!job?.exists && <div className="conductor-launch">
      <h3>Start a production run</h3>
      <p>Use your Book Studio chapter plan. Every draft and final approval stays under your control. <button type="button" onClick={() => onNavigate('book_studio')}>Edit chapter plan</button></p>
      <div className="conductor-settings">
        <label>Local Ollama model<input list="conductor-models" value={model} onChange={e => setModel(e.target.value)} placeholder="Choose installed local model" />
          <datalist id="conductor-models">{installed.map(name => <option value={name} key={name} />)}</datalist>
        </label>
      </div>
      <button disabled={busy || !model} onClick={() => void action('start')}>Start author-led production</button>
      {!model && <p className="conductor-model-help">Choose an installed local Ollama model to enable production.</p>}
      <details className="conductor-options"><summary>Optional reader evaluations ({personas.length} selected)</summary>
        <fieldset><legend>Independent reader lenses</legend>
          {[
            { key: 'developmental_editor', label: 'Developmental editor' },
            { key: 'line_editor', label: 'Line editor' },
            { key: 'genre_fan', label: 'Genre reader' },
          ].map(p => <label key={p.key}><input type="checkbox" checked={personas.includes(p.key)}
            onChange={e => setPersonas(previous => e.target.checked ? [...previous, p.key] : previous.filter(v => v !== p.key))} /> {p.label}</label>)}
        </fieldset></details>
    </div>}
    {!!job?.exists && <div className="conductor-job">
      <div className="conductor-status">
        <strong>{job.status.replaceAll('_', ' ')} · {(job.phase || 'queued').replaceAll('_', ' ')}</strong>
        <p>{job.message}</p>
        <div><span>{job.drafted ?? 0} / {job.total ?? 0} chapters drafted</span><span>{job.approved ?? 0} explicitly approved</span>
          <span>{job.candidates ?? 0} awaiting your review</span></div>
        <progress aria-label="Author-approved chapters" max={Math.max(1, job.total ?? 1)} value={job.approved ?? 0} />
      </div>
      <div className="conductor-actions">
        {(job.status === 'running' || job.status === 'queued') && <button disabled={busy} onClick={() => void action('pause')}>Pause production</button>}
        {['paused', 'needs_attention', 'awaiting_author', 'interrupted', 'completed'].includes(job.status) &&
          <button disabled={busy || !!job.active} onClick={() => void action('continue')}>{job.status === 'awaiting_author' ? 'Continue after author decisions' : 'Continue production'}</button>}
        <button onClick={() => onNavigate('book_studio')}>Open Book Studio</button>
        <button onClick={() => onNavigate('editorial_board')}>Open Editorial Board</button>
      </div>
    </div>}
    <details className="conductor-stage-details"><summary>Show five production stages</summary>
    <div className="conductor-stages">
      {stages.map((stage, index) => <article key={stage.key} className={phaseIndex === index ? 'current' : ''}>
        <strong>{stage.label}</strong><p>{stage.description}</p>
        <small>{index < phaseIndex ? 'STAGE PASSED' : index === phaseIndex && job?.exists ? 'CURRENT STAGE' : 'UPCOMING'}</small>
      </article>)}
    </div>
    </details>
    {!!job?.chapters?.length && <details className="conductor-context"><summary>Advanced: inspect chapter prompt context</summary>
      <h3>Prompt Context Inspector</h3>
      <p>See the currently available narrative context before drafting or revising. This is a project-local read-only preview and does not invoke AI.</p>
      <div><select value={contextChapter} onChange={e => { setContextChapter(Number(e.target.value)); setContextData(null) }}>
        {job.chapters.map(ch => <option key={ch.number} value={ch.number}>Chapter {ch.number}: {ch.title}</option>)}
      </select><button disabled={busy} onClick={() => void inspectContext()}>Inspect chapter context</button></div>
      {contextData && <details open><summary>{contextData.title} · {contextData.characters} / {contextData.budget} characters</summary>
        <p>{contextData.disclaimer}</p><pre>{contextData.context || '(No prior context yet)'}</pre>
      </details>}
    </details>}
    {!!job?.chapters?.length && <details className="conductor-chapters"><summary>Chapter production ledger ({job.chapters.length})</summary>
      {job.chapters.map(chapter => <article key={chapter.number}>
        <strong>{chapter.number}. {chapter.title}</strong><span>{chapter.status} · {chapter.candidate_words.toLocaleString()} words</span>
        <small>{chapter.reviews.length ? chapter.reviews.map(review => `${review.persona.replaceAll('_', ' ')}: ${review.current ? 'current' : 'pending'}`).join(' · ') : 'Independent reader review not requested'}</small>
      </article>)}
    </details>}
    {!!job?.events?.length && <details className="conductor-events"><summary>Production checkpoint history ({job.events.length})</summary>
      {job.events.slice(0, 15).map((event, index) => <div key={index}><small>{new Date(event.at).toLocaleString()} · {event.phase} · {event.status}</small><p>{event.message}</p></div>)}
    </details>}
    {job?.status === 'completed' && job.handoff_current === false && <p className="conductor-error" role="alert">The approved manuscript changed after this handoff. Continue production to rebuild editorial and publication checks before exporting.</p>}
    {job?.preflight && <div className="conductor-handoff">
      <strong>Publishing handoff prepared</strong>
      <p>{job.preflight.blockers} blockers · {job.preflight.warnings} warnings · {job.preflight.waived} author waivers.</p>
      <p>These checks are advisory and not retailer certification. Review the complete issue list in Publish.</p>
    </div>}
  </section>
}
