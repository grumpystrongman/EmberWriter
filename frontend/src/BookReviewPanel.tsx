import { useEffect, useState } from 'react'
import './book-review.css'

type Finding = {
  id: string; category: string; quote: string; issue: string; suggestion: string
  decision: string; author_note: string
}
type Review = {
  id: string; persona: string; persona_name: string; scores: Record<string, number>
  verdict: string; strengths: string[]; findings: Finding[]
  stale: boolean; unverified_findings_rejected: number; created_at: string
}
type History = { number: number; reviews: Review[] }
type Props = {
  apiBase: string; projectSlug: string; chapter: number; model: string
}

export default function BookReviewPanel({ apiBase, projectSlug, chapter, model }: Props) {
  const endpoint = `${apiBase}/projects/${encodeURIComponent(projectSlug)}/book-reviews/${chapter}`
  const [history, setHistory] = useState<History | null>(null)
  const [persona, setPersona] = useState('developmental_editor')
  const [focus, setFocus] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [brief, setBrief] = useState<{ accepted: { persona: string; category: string; quote: string; issue: string; suggestion: string; author_note: string }[]; guidance: string } | null>(null)

  async function call<T>(path = '', method = 'GET', payload?: unknown): Promise<T> {
    const response = await fetch(endpoint + path, {
      method, headers: { 'Content-Type': 'application/json' },
      ...(payload !== undefined ? { body: JSON.stringify(payload) } : {}),
    })
    if (!response.ok) {
      const body = await response.json().catch(() => ({}))
      throw new Error(body.detail || `HTTP ${response.status}`)
    }
    return response.json() as Promise<T>
  }
  async function load() {
    setHistory(await call<History>())
  }
  useEffect(() => {
    setHistory(null); setError(''); setBrief(null)
    void load().catch(e => setError(String(e)))
  }, [endpoint])

  async function evaluate() {
    setBusy(true); setError('')
    try {
      if (!model.trim()) throw new Error('Select a local Ollama model in Book Studio first.')
      await call('/evaluate', 'POST', {
        persona, focus,
        provider: { provider: 'ollama', base_url: 'http://127.0.0.1:11434', model },
      })
      await load()
    } catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }

  async function decide(review: Review, finding: Finding, action: 'accept' | 'dismiss' | 'reopen') {
    setBusy(true); setError('')
    try {
      await call(`/${review.id}/findings/${finding.id}`, 'POST', { action })
      await load()
      setBrief(null)
    } catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }

  async function buildBrief() {
    setBusy(true); setError('')
    try { setBrief(await call('/revision-brief')) }
    catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }

  const fresh = history?.reviews.filter(r => !r.stale) ?? []
  const accepted = fresh.flatMap(r => r.findings).filter(f => f.decision === 'accepted').length

  return <div className="book-review">
    <header>
      <div><small>THE EDITORIAL CHAMBER</small><h4>Independent Reader Panel</h4>
        <p>Invite distinct local AI readers to critique this specific draft. Each reviewer works independently. Only evidence verified against the actual chapter becomes a finding.</p>
      </div>
    </header>
    <div className="book-review-controls">
      <label>Reader perspective
        <select value={persona} onChange={e => setPersona(e.target.value)}>
          <option value="developmental_editor">Developmental Editor</option>
          <option value="genre_fan">Genre Fan</option>
          <option value="line_editor">Line Editor</option>
        </select>
      </label>
      <label>What should this reader pay attention to?
        <input value={focus} maxLength={1000} onChange={e => setFocus(e.target.value)}
          placeholder="Optional: Is the protagonist's choice earned?" />
      </label>
      <button disabled={busy || !model.trim()} onClick={() => void evaluate()}>{busy ? 'Reader is evaluating…' : 'Run local reader'}</button>
    </div>
    {error && <p role="alert" className="book-review-error">{error}</p>}
    {!history && !error && <p role="status">Loading reader history…</p>}
    {!!history && history.reviews.length === 0 && <p>No reader verdicts yet. This chapter remains yours until you choose to request a critique.</p>}
    <div className="book-review-results">
      {history?.reviews.map(review => <article key={review.id} className={`book-review-verdict ${review.stale ? 'book-review-stale' : ''}`}>
        <div className="book-review-resulthead"><strong>{review.persona_name}</strong><span>{review.stale ? 'OLDER DRAFT · READ ONLY' : 'CURRENT DRAFT'}</span></div>
        <p>{review.verdict}</p>
        <div className="book-review-scores">{Object.entries(review.scores).map(([dimension, value]) =>
          <span key={dimension}>{dimension} <strong>{value}/5</strong></span>)}</div>
        {review.strengths.length > 0 && <div className="book-review-strengths"><strong>What works</strong><p>{review.strengths.join(' · ')}</p></div>}
        {review.findings.length > 0 && <div className="book-review-findings"><strong>Evidence-backed observations</strong>
          {review.findings.map(f => <div key={f.id} className="book-review-finding">
            <small>{f.category.toUpperCase()} · {f.decision}</small>
            <blockquote>“{f.quote}”</blockquote>
            <p>{f.issue}</p><p><strong>Possible direction:</strong> {f.suggestion}</p>
            {!review.stale && <div className="book-review-decisions">
              <button disabled={busy} onClick={() => void decide(review, f, 'accept')}>Accept direction</button>
              <button disabled={busy} onClick={() => void decide(review, f, 'dismiss')}>Dismiss</button>
              {f.decision !== 'pending' && <button disabled={busy} onClick={() => void decide(review, f, 'reopen')}>Reopen</button>}
            </div>}
          </div>)}
        </div>}
        {!!review.unverified_findings_rejected && <p className="book-review-warning">{review.unverified_findings_rejected} unsupported or malformed finding(s) withheld because the model could not substantiate them.</p>}
      </article>)}
    </div>
    {fresh.length > 0 && <div className="book-review-brief">
      <button disabled={busy} onClick={() => void buildBrief()}>Build author-approved revision brief ({accepted})</button>
      {brief && <div><h4>Revision directions you accepted</h4>
        {brief.accepted.length === 0 ? <p>No recommendations accepted. Your draft remains unchanged.</p> :
          <ol>{brief.accepted.map((item, index) => <li key={index}><strong>{item.persona} / {item.category}:</strong> {item.suggestion}<br /><small>Evidence: “{item.quote}”</small></li>)}</ol>}
        <p>{brief.guidance}</p>
      </div>}
    </div>}
    <p className="book-review-caveat">Scores are subjective model opinions, not literary quality certification. Evaluations don't rewrite chapters, create canon, or approve publication. Editing the draft makes earlier reviews visibly stale.</p>
  </div>
}
