import { useEffect, useState } from 'react'
import './canon-ripple.css'

type Impact = { path: string; occurrences: number; review_status: string }
type Ripple = {
  id: string; title: string; old_fact: string; proposed_fact: string
  rationale: string; status: string; source_path: string
  created_at: string; matches: Impact[]; scanned_files: number; truncated: boolean
}
type Props = {
  apiBase: string
  projectSlug: string
  onOpenSource: (path: string) => void
}

export default function CanonRipplePanel({ apiBase, projectSlug, onOpenSource }: Props) {
  const [items, setItems] = useState<Ripple[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [formOpen, setFormOpen] = useState(false)
  const [title, setTitle] = useState('')
  const [oldFact, setOldFact] = useState('')
  const [newFact, setNewFact] = useState('')
  const [sourcePath, setSourcePath] = useState('')
  const [rationale, setRationale] = useState('')
  const endpoint = `${apiBase}/projects/${encodeURIComponent(projectSlug)}/canon-ripples`

  async function query<T>(route = '', options?: RequestInit): Promise<T> {
    const response = await fetch(endpoint + route, {
      ...options,
      headers: { 'Content-Type': 'application/json', ...options?.headers },
    })
    if (!response.ok) {
      const body = await response.json().catch(() => ({}))
      throw new Error(body.detail || `Request failed: ${response.status}`)
    }
    return response.json() as Promise<T>
  }
  useEffect(() => {
    let active = true
    setLoading(true)
    setItems([])
    setError('')
    query<Ripple[]>().then(data => { if (active) setItems(data) })
      .catch(e => { if (active) setError(String(e)) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [endpoint])

  async function create(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setBusy(true); setError('')
    try {
      await query<Ripple>('', {
        method: 'POST',
        body: JSON.stringify({
          title: title.trim(), old_fact: oldFact.trim(), proposed_fact: newFact.trim(),
          source_path: sourcePath.trim(), rationale: rationale.trim(),
        }),
      })
      setItems(await query<Ripple[]>())
      setTitle(''); setOldFact(''); setNewFact(''); setSourcePath(''); setRationale('')
      setFormOpen(false)
    } catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }

  async function change(id: string, action: string, path = '') {
    setBusy(true); setError('')
    try {
      await query<Ripple>(`/${encodeURIComponent(id)}/actions`, {
        method: 'POST',
        body: JSON.stringify({ action, path }),
      })
      setItems(await query<Ripple[]>())
    } catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }

  const pending = items.filter(item => item.status === 'approved').reduce(
    (total, item) => total + item.matches.filter(m => m.review_status !== 'reviewed').length, 0)
  return (
    <section className="canon-ripple" aria-labelledby="canon-ripple-heading">
      <div className="canon-ripple-heading">
        <div>
          <small>CONTINUITY COMMAND</small>
          <h3 id="canon-ripple-heading">Canon Ripple <span className="canon-ripple-tag">LOCAL ONLY</span></h3>
          <p>Change a fact? See where its echoes may appear. Review each affected scene before closing the loop.</p>
        </div>
        <div className="canon-ripple-actions">
          <span className="canon-ripple-counter">{pending} pending reviews</span>
          <button type="button" onClick={() => setFormOpen(v => !v)} aria-expanded={formOpen}>
            {formOpen ? 'Close proposal' : '+ Propose a canon change'}
          </button>
        </div>
      </div>
      <p className="canon-ripple-disclaimer">Exact-text matches are leads, not proof of contradiction. Nothing is rewritten automatically. Approval records your editorial decision; it does not modify canon files.</p>
      {error && <p role="alert" className="canon-ripple-error">{error}</p>}
      {formOpen && <form className="canon-ripple-form" onSubmit={e => void create(e)}>
        <label>What is changing? <input required maxLength={200} value={title} onChange={e => setTitle(e.target.value)} placeholder="The captain's birthplace" /></label>
        <label>Previous wording <textarea required minLength={3} maxLength={500} value={oldFact} onChange={e => setOldFact(e.target.value)} placeholder="Mira was born on Observatory Island" /></label>
        <label>Proposed wording <textarea required maxLength={500} value={newFact} onChange={e => setNewFact(e.target.value)} placeholder="Mira was born in Glass Harbor" /></label>
        <label>Source path (optional, exact project-relative file path) <input maxLength={500} value={sourcePath} onChange={e => setSourcePath(e.target.value)} placeholder="characters/mira.md" /></label>
        <label>Why change it? (optional) <textarea maxLength={2000} value={rationale} onChange={e => setRationale(e.target.value)} /></label>
        <button type="submit" disabled={busy}>{busy ? 'Scanning locally…' : 'Find affected documents'}</button>
      </form>}
      {loading && <p role="status">Loading continuity ledger…</p>}
      {!loading && !items.length && <p className="canon-ripple-empty">No canon changes logged. Your continuity ledger is clear.</p>}
      <div className="canon-ripple-list">
        {items.map(item => {
          const unresolved = item.matches.filter(m => m.review_status !== 'reviewed').length
          return <article key={item.id} className="canon-ripple-card">
            <div className="canon-ripple-cardtop">
              <div><strong>{item.title}</strong><span>{item.status.toUpperCase()} · {item.matches.length} reference(s) · {item.scanned_files} files scanned</span></div>
              <span className={`canon-ripple-state canon-ripple-state--${item.status}`}>{item.status}</span>
            </div>
            <div className="canon-ripple-fact"><span>FROM</span><p>{item.old_fact}</p><span>TO</span><p>{item.proposed_fact}</p></div>
            {item.rationale && <p className="canon-ripple-reason">{item.rationale}</p>}
            {item.truncated && <p className="canon-ripple-warning">Scan limit reached. More references may exist.</p>}
            {item.status !== 'rejected' && item.matches.length > 0 && <div className="canon-ripple-impact">
              <h4>Impact review <span>{unresolved} remaining</span></h4>
              {item.matches.map(match => <div className="canon-ripple-impact-row" key={match.path}>
                <button type="button" className="canon-ripple-source" onClick={() => onOpenSource(match.path)} title="Open affected file">{match.path}</button>
                <span>{match.occurrences} hit(s)</span>
                <button type="button" disabled={busy || item.status !== 'approved'}
                  onClick={() => void change(item.id, match.review_status === 'reviewed' ? 'reopen_impact' : 'mark_reviewed', match.path)}>
                  {match.review_status === 'reviewed' ? 'Reopen' : 'Mark reviewed'}
                </button>
              </div>)}
            </div>}
            <div className="canon-ripple-buttons">
              {item.status === 'proposed' && <>
                <button type="button" disabled={busy} onClick={() => void change(item.id, 'approve')}>Approve proposal</button>
                <button type="button" disabled={busy} onClick={() => void change(item.id, 'reject')}>Reject proposal</button>
              </>}
              {item.status === 'approved' && <>
                <button type="button" disabled={busy} onClick={() => void change(item.id, 'rescan')}>Rescan references</button>
                <button type="button" disabled={busy || unresolved > 0} onClick={() => void change(item.id, 'resolve')}>Resolve canon debt</button>
              </>}
              {item.status === 'resolved' && <span>All known references reviewed</span>}
            </div>
          </article>
        })}
      </div>
    </section>
  )
}
