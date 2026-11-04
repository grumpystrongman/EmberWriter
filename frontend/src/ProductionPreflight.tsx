import { useState } from 'react'
import './production-preflight.css'

type Issue = {
  id: string; level: 'blocker' | 'warning'; code: string; title: string; detail: string
  path: string; evidence: string; waivable: boolean; waived: boolean; waiver_reason: string
}
type Report = {
  words: number; chapter_count: number; issues: Issue[]; blockers: number
  warnings: number; waived: number; editorially_ready: boolean; disclaimer: string
}
type Props = { apiBase: string; slug: string; disabled: boolean }

export default function ProductionPreflight({ apiBase, slug, disabled }: Props) {
  const endpoint = `${apiBase}/projects/${encodeURIComponent(slug)}/production-preflight`
  const [report, setReport] = useState<Report | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [reasons, setReasons] = useState<Record<string, string>>({})

  async function request<T>(path = '', method = 'GET', body?: unknown): Promise<T> {
    const result = await fetch(endpoint + path, {
      method, headers: { 'Content-Type': 'application/json' },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    })
    if (!result.ok) {
      const data = await result.json().catch(() => ({}))
      throw new Error(data.detail || `HTTP ${result.status}`)
    }
    return result.json() as Promise<T>
  }
  async function check() {
    setBusy(true); setError(''); setNotice('')
    try { setReport(await request<Report>()) }
    catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }
  async function waive(issue: Issue) {
    setBusy(true); setError('')
    try {
      const reason = (reasons[issue.id] || '').trim()
      if (reason.length < 12) throw new Error('Please record a specific reason (at least 12 characters).')
      setReport(await request<Report>(`/waivers/${encodeURIComponent(issue.id)}`, 'POST', { reason }))
      setNotice(`Recorded your editorial decision: ${issue.title}.`)
    } catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }
  async function restore(issue: Issue) {
    setBusy(true); setError('')
    try {
      setReport(await request<Report>(`/waivers/${encodeURIComponent(issue.id)}`, 'DELETE'))
      setNotice(`Reopened ${issue.title} for review.`)
    } catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }

  return <details className="authoring-panel production-preflight" open>
    <summary>Production Readiness Gate <small>AUTHOR SIGN-OFF · CONTINUITY · MANUSCRIPT QA</small></summary>
    <div className="authoring-panel-body">
      <div className="preflight-intro">
        <h3>Before the book leaves your desk</h3>
        <p>Check unresolved drafting work, continuity decisions, plot promises, proofreading warnings, compile coverage and publication metadata. This checklist advises; it never blocks the author from exporting.</p>
        <button disabled={disabled || busy} onClick={() => void check()}>{busy ? 'Checking your manuscript…' : 'Run production preflight'}</button>
      </div>
      {error && <p className="preflight-error" role="alert">{error}</p>}
      {notice && <p className="preflight-success" role="status">{notice}</p>}
      {report && <div className="preflight-report">
        <div className="preflight-overview">
          <strong>{report.editorially_ready ? 'Editorial checklist reviewed' : 'Editorial decisions remain'}</strong>
          <span>{report.chapter_count} chapters · {report.words.toLocaleString()} words</span>
          <span>{report.blockers} blockers · {report.warnings} warnings · {report.waived} waived with reason</span>
          <a href={endpoint + '/report.md'} download="emberwriter-release-preflight.md">Export preflight report</a>
        </div>
        {!report.issues.length && <p>No concerns identified by these automated checks. This is not a guarantee of professional proofreading or retailer acceptance.</p>}
        <div className="preflight-issues">
          {report.issues.map(issue => <article key={issue.id} className={`preflight-issue preflight-issue--${issue.level}`}>
            <div className="preflight-issue-heading">
              <strong>{issue.title}</strong>
              <span>{issue.waived ? 'AUTHOR-WAIVED' : issue.level.toUpperCase()}</span>
            </div>
            <p>{issue.detail}</p>
            {issue.path && <small>Source: {issue.path}</small>}
            {issue.evidence && <blockquote>{issue.evidence}</blockquote>}
            {issue.waived && <p className="preflight-reason"><strong>Author's reason:</strong> {issue.waiver_reason}</p>}
            {issue.waivable && !issue.waived && <div className="preflight-waiver">
              <label>Accept this risk only with a written reason
                <textarea maxLength={1200} value={reasons[issue.id] || ''}
                  onChange={e => setReasons(current => ({ ...current, [issue.id]: e.target.value }))}
                  placeholder="Example: The 300-word chapter is an intentional interlude, and I verified the pacing in context." />
              </label>
              <button disabled={disabled || busy || (reasons[issue.id] || '').trim().length < 12} onClick={() => void waive(issue)}>Record author waiver</button>
            </div>}
            {issue.waived && <button disabled={disabled || busy} onClick={() => void restore(issue)}>Reopen this warning</button>}
            {!issue.waivable && <p className="preflight-blocker-note">Resolve in the manuscript or Binder; blockers cannot be waived.</p>}
          </article>)}
        </div>
        <p className="preflight-disclaimer">{report.disclaimer}</p>
      </div>}
    </div>
  </details>
}
