import { useEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'

import EditorialReviewPane from './EditorialReviewPane'
import KnowledgePanel from './KnowledgePanel'
import ReaderPanel from './ReaderPanel'
import './editorial-triage.css'

export type EditorialFinding = {
  id: string
  run_id: string
  report_id: string
  report_name: string
  category: string
  severity: 'info' | 'warning' | 'strong'
  status: 'open' | 'resolved' | 'ignored'
  path: string
  binder_node_id: string | null
  start_offset: number
  end_offset: number
  line: number
  excerpt: string
  anchor_text: string
  message: string
  suggestion: string
  source_hash: string
  stale: boolean
}

type ReportDefinition = {
  id: string
  name: string
  category: string
  description: string
  default_enabled: boolean
}

type EditorialProfile = {
  enabled_reports: string[]
  long_sentence_words: number
  short_sentence_words: number
  long_paragraph_words: number
  sticky_sentence_percent: number
  repeated_phrase_minimum: number
  dialogue_low_percent: number
  dialogue_high_percent: number
}

type RunSummary = {
  id: string
  created_at: string
  scope: 'draft' | 'document'
  path: string | null
  reports: string[]
  project_hash: string
  documents: number
  words: number
  findings: number
  by_report: Record<string, number>
  by_severity: Record<string, number>
  metrics: Record<string, number>
}

type RunResult = RunSummary & { items: EditorialFinding[] }

type Provider = {
  provider: 'ollama' | 'openai_compatible'
  base_url: string
  model: string
  api_key?: string
}

export type EditorialFixProposal = {
  finding_id: string
  path: string
  report_id: string
  report_name: string
  original: string
  replacement: string
  rationale: string
  source_hash: string
  target_start: number
  target_end: number
  changed: boolean
}

type EditorialFixApplyResult = {
  path: string
  content: string
  finding: EditorialFinding
  revision: Record<string, unknown>
}

type Props = {
  apiBase: string
  slug: string
  activePath: string
  disabled: boolean
  refreshToken: number
  onOpenFinding: (finding: EditorialFinding) => Promise<void>
}

type TriageMode = 'smart' | 'top20' | 'all'

type FindingGroup = {
  key: string
  label: string
  findings: EditorialFinding[]
  representative: EditorialFinding
  score: number
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

function runLabel(run: RunSummary) {
  const when = new Date(run.created_at)
  const date = Number.isNaN(when.getTime()) ? run.created_at : when.toLocaleString()
  return `${date} · ${run.scope === 'draft' ? 'Draft' : 'Document'} · ${run.findings} findings`
}

function configuredProvider(): Provider | null {
  try {
    const stored = localStorage.getItem('emberwriter.provider')
    if (!stored) return null
    const provider = JSON.parse(stored) as Provider
    if (!provider?.provider || !provider?.base_url) return null
    return provider
  } catch {
    return null
  }
}

function severityWeight(finding: EditorialFinding) {
  if (finding.severity === 'strong') return 300
  if (finding.severity === 'warning') return 200
  return 100
}

function findingImpact(finding: EditorialFinding) {
  let score = severityWeight(finding)
  if (finding.category.toLowerCase().includes('grammar')) score += 55
  if (/repeat|phrase/i.test(finding.report_id)) score += 35
  if (/passive|sticky|readability/i.test(finding.report_id)) score += 20
  if (/adverb|filler/i.test(finding.report_id)) score += 10
  if (finding.stale) score -= 1000
  return score
}

function normalizedAnchor(finding: EditorialFinding) {
  return finding.anchor_text.trim().replace(/\s+/g, ' ').toLocaleLowerCase()
}

function findingGroupKey(finding: EditorialFinding) {
  const anchor = normalizedAnchor(finding)
  const anchorSensitive = /(repeat|phrase|adverb|filler|cliche|crutch)/i.test(finding.report_id)
  if (anchorSensitive && anchor && anchor !== '\u0000' && anchor.length <= 100) {
    return `${finding.report_id}|${anchor}`
  }
  return `${finding.report_id}|${finding.severity}`
}

function buildGroups(findings: EditorialFinding[]): FindingGroup[] {
  const grouped = new Map<string, EditorialFinding[]>()
  for (const finding of findings) {
    const key = findingGroupKey(finding)
    const items = grouped.get(key) || []
    items.push(finding)
    grouped.set(key, items)
  }
  return Array.from(grouped.entries())
    .map(([key, items]) => {
      const ranked = [...items].sort((a, b) => findingImpact(b) - findingImpact(a) || a.line - b.line)
      const representative = ranked[0]
      const anchor = normalizedAnchor(representative)
      const label = items.length > 1 && anchor && /(repeat|phrase|adverb|filler|cliche|crutch)/i.test(representative.report_id)
        ? `${representative.report_name}: “${representative.anchor_text.trim()}”`
        : representative.report_name
      return {
        key,
        label,
        findings: ranked,
        representative,
        score: findingImpact(representative) + Math.min(80, items.length * 4),
      }
    })
    .sort((a, b) => b.score - a.score || b.findings.length - a.findings.length)
}

function scopeLabel(result: RunResult) {
  if (result.scope === 'draft') return 'Whole Draft'
  return result.path?.split('/').at(-1) || 'Current document'
}

export default function EditorialPanel({ apiBase, slug, activePath, disabled, refreshToken, onOpenFinding }: Props) {
  const [catalog, setCatalog] = useState<ReportDefinition[]>([])
  const [profile, setProfile] = useState<EditorialProfile | null>(null)
  const [runs, setRuns] = useState<RunSummary[]>([])
  const [result, setResult] = useState<RunResult | null>(null)
  const [scope, setScope] = useState<'draft' | 'document'>('document')
  const [reportFilter, setReportFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState<'open' | 'resolved' | 'ignored' | 'all'>('open')
  const [triageMode, setTriageMode] = useState<TriageMode>('smart')
  const [groupFocus, setGroupFocus] = useState<string | null>(null)
  const [showReports, setShowReports] = useState(false)
  const [showThresholds, setShowThresholds] = useState(false)
  const [busy, setBusy] = useState(false)
  const [fixingId, setFixingId] = useState('')
  const [applyingId, setApplyingId] = useState('')
  const [fixes, setFixes] = useState<Record<string, EditorialFixProposal>>({})
  const [review, setReview] = useState<{ finding: EditorialFinding; proposal: EditorialFixProposal } | null>(null)
  const [error, setError] = useState('')

  async function loadBase() {
    if (!slug) return
    try {
      const [reports, settings, history] = await Promise.all([
        request<ReportDefinition[]>(`${apiBase}/projects/${slug}/editorial/reports`),
        request<EditorialProfile>(`${apiBase}/projects/${slug}/editorial/profile`),
        request<RunSummary[]>(`${apiBase}/projects/${slug}/editorial/runs`),
      ])
      setCatalog(reports)
      setProfile(settings)
      setRuns(history)
      if (!result && history[0]) {
        setResult(await request<RunResult>(`${apiBase}/projects/${slug}/editorial/runs/${history[0].id}`))
      }
    } catch (cause) {
      setError((cause as Error).message)
    }
  }

  useEffect(() => {
    void loadBase()
  }, [apiBase, slug])

  useEffect(() => {
    if (!result || refreshToken === 0) return
    void request<RunResult>(`${apiBase}/projects/${slug}/editorial/runs/${result.id}`)
      .then(setResult)
      .catch(() => undefined)
  }, [apiBase, slug, refreshToken])

  const enabled = new Set(profile?.enabled_reports || [])
  const filtered = useMemo(() => {
    if (!result) return []
    return result.items.filter((finding) => {
      if (reportFilter !== 'all' && finding.report_id !== reportFilter) return false
      if (statusFilter !== 'all' && finding.status !== statusFilter) return false
      return true
    })
  }, [result, reportFilter, statusFilter])

  const ranked = useMemo(
    () => [...filtered].sort((a, b) => findingImpact(b) - findingImpact(a) || a.path.localeCompare(b.path) || a.line - b.line),
    [filtered],
  )
  const groups = useMemo(() => buildGroups(filtered), [filtered])
  const focusedGroup = useMemo(() => groups.find((group) => group.key === groupFocus) || null, [groups, groupFocus])
  const openFreshCount = result?.items.filter((item) => item.status === 'open' && !item.stale).length || 0
  const openStaleCount = result?.items.filter((item) => item.status === 'open' && item.stale).length || 0

  const groupedCatalog = useMemo(() => {
    const groups = new Map<string, ReportDefinition[]>()
    for (const report of catalog) {
      const items = groups.get(report.category) || []
      items.push(report)
      groups.set(report.category, items)
    }
    return Array.from(groups.entries()).sort(([a], [b]) => a.localeCompare(b))
  }, [catalog])

  async function runEditorial() {
    if (!profile || busy || (scope === 'document' && !activePath)) return
    setBusy(true)
    setError('')
    try {
      const next = await request<RunResult>(`${apiBase}/projects/${slug}/editorial/runs`, {
        method: 'POST',
        body: JSON.stringify({
          scope,
          path: scope === 'document' ? activePath : null,
          reports: profile.enabled_reports,
        }),
      })
      setResult(next)
      setRuns(await request<RunSummary[]>(`${apiBase}/projects/${slug}/editorial/runs`))
      setFixes({})
      setReview(null)
      setStatusFilter('open')
      setReportFilter('all')
      setTriageMode('smart')
      setGroupFocus(null)
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function openRun(runId: string) {
    if (!runId || busy) return
    setBusy(true)
    setError('')
    try {
      const next = await request<RunResult>(`${apiBase}/projects/${slug}/editorial/runs/${runId}`)
      setResult(next)
      setScope(next.scope)
      setFixes({})
      setReview(null)
      setGroupFocus(null)
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function saveProfile() {
    if (!profile || busy) return
    setBusy(true)
    setError('')
    try {
      setProfile(await request<EditorialProfile>(`${apiBase}/projects/${slug}/editorial/profile`, {
        method: 'PUT',
        body: JSON.stringify(profile),
      }))
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function setFindingStatus(finding: EditorialFinding, status: EditorialFinding['status']) {
    if (!result || busy) return
    try {
      const updated = await request<EditorialFinding>(`${apiBase}/projects/${slug}/editorial/findings/${finding.id}`, {
        method: 'PUT',
        body: JSON.stringify({ status }),
      })
      setResult({ ...result, items: result.items.map((item) => item.id === updated.id ? updated : item) })
    } catch (cause) {
      setError((cause as Error).message)
    }
  }

  function removeProposal(findingId: string) {
    setFixes((current) => {
      const next = { ...current }
      delete next[findingId]
      return next
    })
  }

  async function applyProposal(finding: EditorialFinding, proposal: EditorialFixProposal) {
    if (applyingId) return false
    setApplyingId(finding.id)
    setError('')
    try {
      const applied = await request<EditorialFixApplyResult>(`${apiBase}/projects/${slug}/editorial/fix/apply`, {
        method: 'POST',
        body: JSON.stringify({
          finding_id: proposal.finding_id,
          path: proposal.path,
          original: proposal.original,
          replacement: proposal.replacement,
          source_hash: proposal.source_hash,
          target_start: proposal.target_start,
          target_end: proposal.target_end,
          rationale: proposal.rationale,
        }),
      })
      removeProposal(finding.id)
      setReview(null)
      setStatusFilter('open')
      setGroupFocus(null)
      if (result) {
        const refreshed = await request<RunResult>(`${apiBase}/projects/${slug}/editorial/runs/${result.id}`)
        setResult(refreshed)
      }
      await onOpenFinding({
        ...applied.finding,
        report_name: `Applied ${finding.report_name}`,
        anchor_text: proposal.replacement,
        line: finding.line,
      })
      return true
    } catch (cause) {
      setError((cause as Error).message)
      return false
    } finally {
      setApplyingId('')
    }
  }

  async function requestFix(finding: EditorialFinding) {
    if (finding.stale || fixingId) return
    const provider = configuredProvider()
    if (!provider?.model?.trim()) {
      setError('Choose an AI model in EmberWriter before asking AI to repair an editorial finding.')
      return
    }
    setFixingId(finding.id)
    setError('')
    try {
      const proposal = await request<EditorialFixProposal>(`${apiBase}/projects/${slug}/editorial/fix`, {
        method: 'POST',
        body: JSON.stringify({ finding_id: finding.id, provider, instruction: '' }),
      })
      setFixes((current) => ({ ...current, [finding.id]: proposal }))
      if (proposal.changed) setReview({ finding, proposal })
      else setError(`AI recommends keeping this passage: ${proposal.rationale}`)
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setFixingId('')
    }
  }

  function toggleReport(reportId: string) {
    if (!profile) return
    const current = new Set(profile.enabled_reports)
    if (current.has(reportId)) current.delete(reportId)
    else current.add(reportId)
    setProfile({ ...profile, enabled_reports: catalog.map((item) => item.id).filter((id) => current.has(id)) })
  }

  function openReaderSource(path: string) {
    return onOpenFinding({
      id: '', run_id: '', report_id: 'reader', report_name: 'AI Reader', category: 'reader', severity: 'info', status: 'open',
      path, binder_node_id: null, start_offset: 0, end_offset: 0, line: 1, excerpt: '', anchor_text: '\u0000', message: '', suggestion: '', source_hash: '', stale: false,
    })
  }

  function renderFinding(finding: EditorialFinding) {
    const proposal = fixes[finding.id]
    return (
      <article key={finding.id} className={`editorial-finding severity-${finding.severity} ${finding.stale ? 'stale' : ''}`}>
        <button type="button" className="editorial-source" onClick={() => void onOpenFinding(finding)} title="Open this document and highlight the flagged prose">
          <span>{finding.report_name} · {finding.path.split('/').at(-1)}:{finding.line}</span>
          <small>{finding.stale ? 'STALE — rerun after edit' : `${finding.severity.toUpperCase()} · JUMP + HIGHLIGHT`}</small>
        </button>
        <p>{finding.message}</p>
        <blockquote>{finding.excerpt}</blockquote>
        <small className="editorial-suggestion">{finding.suggestion}</small>
        <div className="editorial-finding-actions">
          {!finding.stale && finding.status === 'open' && (
            <button type="button" className="editorial-ai-fix" disabled={disabled || Boolean(fixingId) || Boolean(applyingId)} onClick={() => void requestFix(finding)}>
              {fixingId === finding.id ? 'AI preparing review…' : 'AI Fix · Side-by-side'}
            </button>
          )}
          {finding.status !== 'resolved' && <button type="button" onClick={() => void setFindingStatus(finding, 'resolved')}>Resolve</button>}
          {finding.status !== 'ignored' && <button type="button" onClick={() => void setFindingStatus(finding, 'ignored')}>Ignore</button>}
          {finding.status !== 'open' && <button type="button" onClick={() => void setFindingStatus(finding, 'open')}>Reopen</button>}
        </div>
        {proposal && (
          <div className={`editorial-fix-preview ${proposal.changed ? '' : 'no-change'}`}>
            <strong>{proposal.changed ? 'AI proposal ready for side-by-side review' : 'AI recommends keeping the passage'}</strong>
            <small>{proposal.rationale}</small>
            <div className="editorial-fix-actions">
              {proposal.changed && <button type="button" className="primary" onClick={() => setReview({ finding, proposal })}>Open side-by-side review</button>}
              <button type="button" onClick={() => removeProposal(finding.id)}>Dismiss</button>
            </div>
          </div>
        )}
      </article>
    )
  }

  if (!profile) {
    return <details className="authoring-panel"><summary>Editorial Studio</summary><small>Loading editorial profile…</small></details>
  }

  const smartGroups = groups.slice(0, 18)
  const topFindings = ranked.slice(0, 20)

  return (
    <>
      <details className="authoring-panel editorial-panel" open>
        <summary>
          Editorial Studio
          <small>{result ? `${openFreshCount} open · ${result.findings} logged` : `${profile.enabled_reports.length} reports enabled`}</small>
        </summary>
        <div className="authoring-panel-body">
          <div className="editorial-scope">
            <button type="button" className={scope === 'document' ? 'active' : ''} onClick={() => setScope('document')} disabled={disabled || busy || !activePath}>Current document</button>
            <button type="button" className={scope === 'draft' ? 'active' : ''} onClick={() => setScope('draft')} disabled={disabled || busy}>Whole Draft</button>
          </div>
          <button type="button" className="primary" onClick={() => void runEditorial()} disabled={disabled || busy || profile.enabled_reports.length === 0 || (scope === 'document' && !activePath)}>
            {busy ? 'Analyzing…' : `Run ${profile.enabled_reports.length} editorial reports`}
          </button>

          <div className="editorial-config-actions">
            <button type="button" onClick={() => setShowReports((value) => !value)}>{showReports ? 'Hide reports' : 'Choose reports'}</button>
            <button type="button" onClick={() => setShowThresholds((value) => !value)}>{showThresholds ? 'Hide thresholds' : 'Thresholds'}</button>
            <button type="button" onClick={() => void saveProfile()} disabled={busy}>Save profile</button>
          </div>

          {showReports && (
            <div className="editorial-report-picker">
              {groupedCatalog.map(([category, reports]) => (
                <div key={category} className="editorial-report-group">
                  <strong>{category.replaceAll('_', ' ')}</strong>
                  {reports.map((report) => (
                    <label key={report.id} title={report.description}>
                      <input type="checkbox" checked={enabled.has(report.id)} onChange={() => toggleReport(report.id)} />
                      <span><b>{report.name}</b><small>{report.description}</small></span>
                    </label>
                  ))}
                </div>
              ))}
            </div>
          )}

          {showThresholds && (
            <div className="editorial-thresholds">
              <label>Long sentence <input type="number" min="15" max="100" value={profile.long_sentence_words} onChange={(event) => setProfile({ ...profile, long_sentence_words: Number(event.target.value) })} /> words</label>
              <label>Short sentence ≤ <input type="number" min="1" max="12" value={profile.short_sentence_words} onChange={(event) => setProfile({ ...profile, short_sentence_words: Number(event.target.value) })} /> words</label>
              <label>Long paragraph <input type="number" min="60" max="600" value={profile.long_paragraph_words} onChange={(event) => setProfile({ ...profile, long_paragraph_words: Number(event.target.value) })} /> words</label>
              <label>Sticky sentence <input type="number" min="20" max="80" step="1" value={profile.sticky_sentence_percent} onChange={(event) => setProfile({ ...profile, sticky_sentence_percent: Number(event.target.value) })} />%</label>
              <label>Repeated phrase <input type="number" min="2" max="12" value={profile.repeated_phrase_minimum} onChange={(event) => setProfile({ ...profile, repeated_phrase_minimum: Number(event.target.value) })} /> occurrences</label>
              <label>Dialogue low <input type="number" min="0" max="40" value={profile.dialogue_low_percent} onChange={(event) => setProfile({ ...profile, dialogue_low_percent: Number(event.target.value) })} />%</label>
              <label>Dialogue high <input type="number" min="30" max="95" value={profile.dialogue_high_percent} onChange={(event) => setProfile({ ...profile, dialogue_high_percent: Number(event.target.value) })} />%</label>
            </div>
          )}

          {runs.length > 0 && (
            <label className="editorial-history-label">
              Saved analysis
              <select value={result?.id || ''} onChange={(event) => void openRun(event.target.value)} disabled={busy}>
                {runs.map((run) => <option key={run.id} value={run.id}>{runLabel(run)}</option>)}
              </select>
            </label>
          )}

          {result && (
            <>
              <div className="editorial-run-scope">
                <div>
                  <small>ANALYSIS SCOPE</small>
                  <strong>{result.scope === 'draft' ? 'Whole Draft' : 'Current document'}</strong>
                  <span>{scopeLabel(result)}</span>
                </div>
                <div className="editorial-run-counts">
                  <b>{openFreshCount.toLocaleString()}</b><span>open now</span>
                  {openStaleCount > 0 && <><b>{openStaleCount.toLocaleString()}</b><span>stale</span></>}
                </div>
              </div>

              <div className="editorial-metrics">
                <span><b>{result.documents}</b> docs</span>
                <span><b>{result.words.toLocaleString()}</b> words</span>
                <span><b>{result.findings}</b> logged findings</span>
                {typeof result.metrics.readability === 'number' && <span><b>{result.metrics.readability.toFixed(1)}</b> readability</span>}
                {typeof result.metrics.dialogue_percent === 'number' && <span><b>{result.metrics.dialogue_percent.toFixed(1)}%</b> dialogue</span>}
              </div>

              <div className="editorial-triage-intro">
                <div>
                  <strong>Editorial Triage</strong>
                  <small>Condense hundreds of flags into patterns, or review the highest-impact issues first. AI rewrites always open side-by-side before they can be applied.</small>
                </div>
                <button type="button" className="primary" disabled={disabled || Boolean(fixingId) || topFindings.length === 0} onClick={() => topFindings[0] && void requestFix(topFindings[0])}>
                  {fixingId ? 'Preparing review…' : 'AI review next best'}
                </button>
              </div>

              <div className="editorial-triage-modes" role="tablist" aria-label="Editorial triage mode">
                <button type="button" className={triageMode === 'smart' ? 'active' : ''} onClick={() => { setTriageMode('smart'); setGroupFocus(null) }}>Smart groups</button>
                <button type="button" className={triageMode === 'top20' ? 'active' : ''} onClick={() => { setTriageMode('top20'); setGroupFocus(null) }}>Top 20</button>
                <button type="button" className={triageMode === 'all' ? 'active' : ''} onClick={() => { setTriageMode('all'); setGroupFocus(null) }}>All findings</button>
              </div>

              <small className="editorial-navigation-help">Click a finding to jump to the exact prose. Any AI rewrite opens the full Revision Review first; only the Apply &amp; Resolve button inside that side-by-side view can change the manuscript.</small>
              <div className="editorial-filters">
                <select value={reportFilter} onChange={(event) => { setReportFilter(event.target.value); setGroupFocus(null) }}>
                  <option value="all">All reports</option>
                  {catalog.filter((item) => result.by_report[item.id]).map((item) => (
                    <option key={item.id} value={item.id}>{item.name} ({result.by_report[item.id]})</option>
                  ))}
                </select>
                <select value={statusFilter} onChange={(event) => { setStatusFilter(event.target.value as typeof statusFilter); setGroupFocus(null) }}>
                  <option value="open">Open</option><option value="resolved">Resolved</option><option value="ignored">Ignored</option><option value="all">All states</option>
                </select>
              </div>

              <div className="editorial-findings">
                {filtered.length === 0 && <small className="panel-help">No findings match these filters.</small>}

                {triageMode === 'smart' && focusedGroup && (
                  <div className="editorial-group-focus">
                    <button type="button" onClick={() => setGroupFocus(null)}>← Back to smart groups</button>
                    <div><strong>{focusedGroup.label}</strong><small>{focusedGroup.findings.length} remaining in this pattern</small></div>
                  </div>
                )}

                {triageMode === 'smart' && !focusedGroup && smartGroups.map((group) => (
                  <article key={group.key} className={`editorial-triage-group severity-${group.representative.severity}`}>
                    <div className="editorial-triage-group-heading">
                      <div>
                        <small>{group.representative.severity.toUpperCase()} · {group.representative.category.replaceAll('_', ' ')}</small>
                        <strong>{group.label}</strong>
                        <span>{group.findings.length === 1 ? '1 finding' : `${group.findings.length} similar findings`}</span>
                      </div>
                      <b>{group.findings.length}</b>
                    </div>
                    <p>{group.representative.message}</p>
                    <blockquote>{group.representative.excerpt}</blockquote>
                    <div className="editorial-triage-group-actions">
                      <button type="button" className="primary" disabled={disabled || Boolean(fixingId) || group.representative.stale} onClick={() => void requestFix(group.representative)}>
                        {fixingId === group.representative.id ? 'Preparing…' : 'Review best example'}
                      </button>
                      {group.findings.length > 1 && <button type="button" onClick={() => setGroupFocus(group.key)}>Review all {group.findings.length}</button>}
                      <button type="button" onClick={() => void onOpenFinding(group.representative)}>Jump to example</button>
                    </div>
                  </article>
                ))}

                {triageMode === 'smart' && focusedGroup && focusedGroup.findings.map(renderFinding)}
                {triageMode === 'top20' && topFindings.map(renderFinding)}
                {triageMode === 'all' && filtered.map(renderFinding)}
              </div>
            </>
          )}

          <ReaderPanel apiBase={apiBase} slug={slug} disabled={disabled || busy} onOpenSource={(path) => void openReaderSource(path)} />
          <KnowledgePanel apiBase={apiBase} slug={slug} activePath={activePath} disabled={disabled || busy} />
          {error && <small className="panel-error">{error}</small>}
        </div>
      </details>

      {review && createPortal(
        <div className="editorial-review-overlay" role="dialog" aria-modal="true" aria-label="Revision Review">
          <div className="editorial-review-tabs">
            <button type="button" onClick={() => setReview(null)}>Manuscript</button>
            <button type="button" className="active">Revision Review</button>
          </div>
          <EditorialReviewPane
            finding={review.finding}
            proposal={review.proposal}
            busy={applyingId === review.finding.id}
            onClose={() => setReview(null)}
            onApply={() => applyProposal(review.finding, review.proposal)}
          />
        </div>,
        document.body,
      )}
    </>
  )
}
