import { useEffect, useMemo, useState } from 'react'
import type { WorkspaceProject } from './workspace-types'
import './autopilot.css'

type Chapter = { path: string; words: number; status: string; issue_count: number; issues: string[]; repeated_openings: number }
type Phase = { id: string; label: string; status: string; summary: string; tasks: string[] }
type Audit = {
  id?: string
  created_at?: string
  fingerprint: string
  project_name: string
  foundation: Record<string, boolean>
  foundation_complete: number
  foundation_total: number
  chapter_count: number
  drafted_count: number
  total_words: number
  issues_total: number
  open_threads: number
  unplanned_payoffs: string[]
  chapters: Chapter[]
  phases: Phase[]
  truncated: boolean
  local_only: boolean
  manuscript_modified: boolean
  method: string
}

type Props = {
  apiBase: string
  project: WorkspaceProject
  onOpenSource: (path: string) => void
}

function number(value: number) { return value.toLocaleString() }
function exportPlan(report: Audit) {
  const lines = [
    '# EmberWriter Autopilot — Local Manuscript Assessment',
    `Project: ${report.project_name}`,
    `Chapters drafted: ${report.drafted_count} of ${report.chapter_count}`,
    `Words: ${number(report.total_words)}`,
    `Mechanical findings: ${report.issues_total}`,
    `Open plot threads: ${report.open_threads}`,
    `Unplanned payoffs: ${report.unplanned_payoffs.length}`,
    '',
    ...report.phases.flatMap(phase => [
      `## ${phase.label} — ${phase.status.replace('_', ' ')}`,
      phase.summary,
      ...phase.tasks.map(task => `- [ ] ${task}`),
      '',
    ]),
    '## Chapter diagnostics',
    ...report.chapters.flatMap(ch => [
      `### ${ch.path} (${number(ch.words)} words)`,
      ...ch.issues.map(issue => `- ${issue}`),
    ]),
    '',
    'Mechanical observations are not a substitute for literary judgment.',
    'No manuscript was rewritten or uploaded by this assessment.',
  ]
  const link = document.createElement('a')
  const url = URL.createObjectURL(new Blob([lines.join('\n')], { type: 'text/markdown' }))
  link.href = url
  link.download = 'autopilot-assessment.md'
  link.click()
  window.setTimeout(() => URL.revokeObjectURL(url), 500)
}

export default function AutopilotWorkspace({ apiBase, project, onOpenSource }: Props) {
  const [report, setReport] = useState<Audit | null>(null)
  const [history, setHistory] = useState<Audit[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState<string | null>(null)
  const [showDetails, setShowDetails] = useState(true)
  const endpoint = `${apiBase}/projects/${encodeURIComponent(project.slug)}/autopilot`

  async function fetchJson<T>(path: string, options?: RequestInit): Promise<T> {
    const response = await fetch(endpoint + path, options)
    if (!response.ok) {
      const problem = await response.json().catch(() => ({}))
      throw new Error(problem.detail || `HTTP ${response.status}`)
    }
    return response.json() as Promise<T>
  }

  useEffect(() => {
    let cancelled = false
    setReport(null)
    setError('')
    Promise.all([fetchJson<Audit>('/readiness'), fetchJson<Audit[]>('/audits')])
      .then(([next, runs]) => { if (!cancelled) { setReport(next); setHistory(runs) } })
      .catch(e => { if (!cancelled) setError(String(e)) })
    return () => { cancelled = true }
  }, [project.slug, apiBase])

  async function assess() {
    setBusy(true)
    setError('')
    try {
      const next = await fetchJson<Audit>('/audits', { method: 'POST' })
      setReport(next)
      setHistory(await fetchJson<Audit[]>('/audits'))
    } catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }

  const topChapters = useMemo(() =>
    [...(report?.chapters || [])].sort((a, b) => b.issue_count - a.issue_count).slice(0, 12),
    [report],
  )
  const selectedChapter = report?.chapters.find(ch => ch.path === selected)

  return (
    <section className="autopilot">
      <header className="autopilot-hero">
        <div className="autopilot-orbit" aria-hidden="true">✧</div>
        <div className="autopilot-copy">
          <span className="autopilot-kicker">EMBERWRITER · AUTOPILOT</span>
          <h2>The Story Flight Deck</h2>
          <p>From first spark to finished book. See what’s ready, spot what needs attention,
            and choose the next move. Your story stays yours.</p>
          <div className="autopilot-privacy">◉ Local assessment · No cloud calls · No automatic rewrites</div>
        </div>
        <div className="autopilot-actions">
          <button type="button" className="autopilot-primary" onClick={() => void assess()} disabled={busy}>
            {busy ? 'Assessing…' : '✦ Run Fresh Assessment'}
          </button>
          <button type="button" onClick={() => report && exportPlan(report)} disabled={!report}>↓ Export Action Plan</button>
        </div>
      </header>

      {error && <p role="alert" className="autopilot-error">{error}</p>}
      {!report && !error && <p role="status">Reading the local project library…</p>}

      {report && (
        <>
          <div className="autopilot-metrics" aria-label="Manuscript metrics">
            <article><small>FOUNDATION</small><strong>{report.foundation_complete}/{report.foundation_total}</strong><span>building blocks ready</span></article>
            <article><small>DRAFTED</small><strong>{report.drafted_count}<em> / {report.chapter_count}</em></strong><span>manuscript chapters</span></article>
            <article><small>WORDS</small><strong>{number(report.total_words)}</strong><span>across draft and outlines</span></article>
            <article><small>OPEN PROMISES</small><strong>{report.open_threads}</strong><span>{report.unplanned_payoffs.length} without payoff plans</span></article>
            <article><small>REVIEW QUEUE</small><strong>{report.issues_total}</strong><span>mechanical observations</span></article>
          </div>

          <div className="autopilot-section-heading">
            <div><small>YOUR PRODUCTION PATH</small><h3>Four stages. One connected story.</h3></div>
            <span>Author approval required for future changes</span>
          </div>
          <div className="autopilot-phases">
            {report.phases.map((phase, i) => (
              <article key={phase.id} className="autopilot-phase">
                <div className="autopilot-phase-top">
                  <span className="autopilot-step">{String(i + 1).padStart(2, '0')}</span>
                  <span className={`autopilot-status ${phase.status}`}>{phase.status.replaceAll('_', ' ')}</span>
                </div>
                <h4>{phase.label}</h4>
                <p>{phase.summary}</p>
                <ul>{phase.tasks.map(task => <li key={task}>{task}</li>)}</ul>
              </article>
            ))}
          </div>

          <div className="autopilot-section-heading">
            <div><small>QUALITY RADAR</small><h3>Where to focus your next revision</h3></div>
            <button type="button" onClick={() => setShowDetails(v => !v)}>
              {showDetails ? 'Hide diagnostics' : 'Show diagnostics'}
            </button>
          </div>
          {showDetails && (
            <div className="autopilot-chapters">
              {topChapters.length === 0 && <p>No chapters yet. Start writing and return for an assessment.</p>}
              {topChapters.map(chapter => (
                <button key={chapter.path} type="button"
                  className={`autopilot-chapter ${selected === chapter.path ? 'active' : ''}`}
                  onClick={() => setSelected(current => current === chapter.path ? null : chapter.path)}>
                  <span>{chapter.path.split('/').pop()}</span>
                  <span>{number(chapter.words)} words</span>
                  <strong>{chapter.status === 'outline' ? 'Outline' : `${chapter.issue_count} findings`}</strong>
                </button>
              ))}
              {selectedChapter && <div className="autopilot-findings">
                <div className="autopilot-findings-title">
                  <strong>{selectedChapter.path}</strong>
                  <button type="button" onClick={() => onOpenSource(selectedChapter.path)}>Open in editor</button>
                </div>
                {selectedChapter.issues.length
                  ? <ul>{selectedChapter.issues.map(issue => <li key={issue}>{issue}</li>)}</ul>
                  : <p>No mechanical prose flags in this chapter. This is not a literary quality rating.</p>}
              </div>}
              {report.truncated && <p>Only the first 250 manuscript files were scanned.</p>}
            </div>
          )}

          <footer className="autopilot-footer">
            <div><strong>{history.length ? `${history.length} saved assessment(s)` : 'No saved assessments yet'}</strong>
              <span>{history[0]?.created_at ? ` · Latest: ${new Date(history[0].created_at).toLocaleString()}` : ' · Run an assessment to save a baseline.'}</span>
            </div>
            <p>Assessment results are deterministic heuristics, not an AI judge score. They are stored locally inside this project. The autonomous generation, multi-judge revision loop, audio narration and export enhancements are planned separately—not represented as completed here.</p>
          </footer>
        </>
      )}
    </section>
  )
}
