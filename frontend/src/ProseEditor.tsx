import { useEffect, useState } from 'react'
import './prose-editor.css'

type Finding = {
  id: string; rule: string; title: string; start: number; end: number
  matched: string; suggested: string | null; why: string; line: number
  excerpt: string; decision: string; reason: string
}
type Report = {
  path: string; source_hash: string; findings: Finding[]; outstanding: number
  dismissed: number; truncated: boolean; method: string
}
type Chapter = { path: string; title: string; status: string }
type Props = { apiBase: string; projectSlug: string; initialPath?: string; onOpenSource: (path: string) => void }

export default function ProseEditor({ apiBase, projectSlug, initialPath, onOpenSource }: Props) {
  const endpoint = `${apiBase}/projects/${encodeURIComponent(projectSlug)}/prose-editor`
  const [chapters, setChapters] = useState<Chapter[]>([])
  const [path, setPath] = useState('')
  const [perspective, setPerspective] = useState('unspecified')
  const [tense, setTense] = useState('unspecified')
  const [report, setReport] = useState<Report | null>(null)
  const [reasons, setReasons] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  async function request<T>(suffix: string, method = 'GET', body?: unknown): Promise<T> {
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
    setReport(null); setChapters([]); setPath(''); setError(''); setMessage('')
    void request<Chapter[]>('/chapters').then(items => {
      if (live) { setChapters(items); setPath(items.some(item => item.path === initialPath) ? initialPath! : items[0]?.path || '') }
    }).catch(e => { if (live) setError(String(e)) })
    return () => { live = false }
  }, [endpoint])

  async function inspect() {
    if (!path) return
    setBusy(true); setError(''); setMessage('')
    try {
      setReport(await request<Report>('/inspect', 'POST', { path, perspective, tense }))
    } catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }
  async function decide(item: Finding, action: 'apply' | 'dismiss' | 'reopen') {
    if (!report) return
    setBusy(true); setError(''); setMessage('')
    try {
      const next = await request<Report>('/decision', 'POST', {
        path, perspective, tense, source_hash: report.source_hash,
        finding_id: item.id, action, reason: reasons[item.id] || '',
      })
      setReport(next)
      setMessage(action === 'apply'
        ? 'Correction applied to the current chapter. A restorable source snapshot was created. Other findings were refreshed.'
        : action === 'dismiss'
          ? 'Author exception recorded for this exact chapter version.'
          : 'Observation reopened.')
    } catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }
  return <section className="prose-editor" aria-labelledby="prose-editor-heading">
    <header className="prose-editor-hero">
      <small>EDITORIAL WORKBENCH · EVERY WORD IS YOURS</small>
      <h2 id="prose-editor-heading">Prose Editor</h2>
      <p>Inspect sentence-level grammar patterns, repeated words, wordiness and possible narrative drift. Approve individual mechanical corrections or retain the original language with an author note.</p>
    </header>
    <div className="prose-editor-controls">
      <label>Chapter<select value={path} onChange={e => { setPath(e.target.value); setReport(null) }}>
        {!chapters.length && <option value="">No manuscript chapters yet</option>}
        {chapters.map(ch => <option key={ch.path} value={ch.path}>{ch.title} · {ch.status}</option>)}
      </select></label>
      <label>Expected perspective<select value={perspective} onChange={e => { setPerspective(e.target.value); setReport(null) }}>
        <option value="unspecified">No POV check</option><option value="first">First person</option><option value="third">Third person</option>
      </select></label>
      <label>Expected tense<select value={tense} onChange={e => { setTense(e.target.value); setReport(null) }}>
        <option value="unspecified">No tense check</option><option value="past">Past tense</option><option value="present">Present tense</option>
      </select></label>
      <button disabled={busy || !path} onClick={() => void inspect()}>{busy ? 'Reviewing…' : 'Inspect prose locally'}</button>
    </div>
    {error && <p role="alert" className="prose-editor-error">{error}</p>}
    {message && <p role="status" className="prose-editor-success">{message}</p>}
    {report && <div className="prose-editor-results">
      <div className="prose-editor-summary"><strong>{report.outstanding} observations awaiting review</strong><span>{report.dismissed} author exceptions</span>
        {!path.startsWith('book-studio:candidate:') && <button onClick={() => onOpenSource(path)}>Open in editor</button>}</div>
      {report.truncated && <p className="prose-editor-error">Finding limit reached. Shorten the chapter or correct obvious issues and rescan.</p>}
      {!report.findings.length && <p>No patterns flagged by the currently supported rules. This is not a comprehensive grammar certification.</p>}
      {report.findings.map(item => <article key={item.id} className={item.decision === 'dismissed' ? 'prose-editor-dismissed' : ''}>
        <div className="prose-editor-heading"><strong>{item.title}</strong><span>{item.decision === 'dismissed' ? 'AUTHOR EXCEPTION' : `LINE ${item.line}`}</span></div>
        <blockquote>{item.excerpt}</blockquote>
        <p>{item.why}</p>
        {item.suggested !== null
          ? <p className="prose-editor-suggestion">Suggested: <strong>{item.suggested || '(remove spacing)'}</strong> <span>· Original: {item.matched}</span></p>
          : <p className="prose-editor-suggestion">Review-only observation. No automatic correction is offered.</p>}
        {item.decision === 'dismissed'
          ? <div><p>Author's reason: {item.reason}</p><button disabled={busy} onClick={() => void decide(item, 'reopen')}>Reopen</button></div>
          : <div className="prose-editor-actions">
              {item.suggested !== null && <button disabled={busy} onClick={() => void decide(item, 'apply')}>Apply this correction</button>}
              <label>Intentionally keep? <input maxLength={500} value={reasons[item.id] || ''} onChange={e => setReasons(old => ({ ...old, [item.id]: e.target.value }))} placeholder="Why this wording belongs here" /></label>
              <button disabled={busy || (reasons[item.id] || '').trim().length < 8} onClick={() => void decide(item, 'dismiss')}>Keep original</button>
            </div>}
      </article>)}
      <p className="prose-editor-caveat">{report.method} Narrative POV and tense warnings are deliberately cautious: free indirect thought, flashbacks, dialogue and stylistic shifts are often valid.</p>
    </div>}
  </section>
}
