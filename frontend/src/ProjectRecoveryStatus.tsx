import { useEffect, useState } from 'react'
import './project-recovery-status.css'

const API = 'http://127.0.0.1:8000/api'

type RecoveryItem = {
  name: string
  path?: string
  source_path?: string
  reason?: string
  signature?: string
}

type RecoveryReport = {
  attempted: boolean
  found: number
  recovered_count: number
  recovered: RecoveryItem[]
  skipped: RecoveryItem[]
  active_projects_root: string
  searched_roots: string[]
  drive_wide_scan: boolean
  projects_count?: number
  error?: string | null
}

export default function ProjectRecoveryStatus() {
  const [report, setReport] = useState<RecoveryReport | null>(null)
  const [busy, setBusy] = useState(false)
  const [expanded, setExpanded] = useState(false)

  async function loadStatus() {
    try {
      const response = await fetch(`${API}/projects/recovery-status`)
      if (!response.ok) return
      setReport(await response.json() as RecoveryReport)
    } catch {
      // The main application already surfaces API connectivity problems.
    }
  }

  async function recover() {
    setBusy(true)
    setExpanded(true)
    try {
      const response = await fetch(`${API}/projects/recover`, { method: 'POST' })
      if (!response.ok) throw new Error(`${response.status} ${response.statusText}`)
      const result = await response.json() as RecoveryReport
      setReport(result)
      if (result.recovered_count > 0) {
        window.setTimeout(() => window.location.reload(), 700)
      }
    } catch (error) {
      setReport((current) => ({
        attempted: true,
        found: current?.found || 0,
        recovered_count: current?.recovered_count || 0,
        recovered: current?.recovered || [],
        skipped: current?.skipped || [],
        active_projects_root: current?.active_projects_root || '',
        searched_roots: current?.searched_roots || [],
        drive_wide_scan: current?.drive_wide_scan || false,
        error: (error as Error).message,
      }))
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    const timer = window.setTimeout(() => void loadStatus(), 1200)
    return () => window.clearTimeout(timer)
  }, [])

  if (!report) return null

  const label = busy
    ? 'Searching for old work…'
    : report.recovered_count > 0
      ? `Recovered ${report.recovered_count} project${report.recovered_count === 1 ? '' : 's'}`
      : report.error
        ? 'Project recovery error'
        : `Recovery scan: ${report.found} candidate${report.found === 1 ? '' : 's'}`

  return (
    <div className={`project-recovery-status${expanded ? ' expanded' : ''}`}>
      <button className="project-recovery-chip" type="button" onClick={() => setExpanded((value) => !value)}>
        <span className={report.recovered_count > 0 ? 'recovery-dot found' : report.error ? 'recovery-dot error' : 'recovery-dot'} />
        {label}
      </button>
      {expanded && (
        <div className="project-recovery-card">
          <strong>Old-work recovery</strong>
          <p>
            {report.drive_wide_scan
              ? 'EmberWriter searched mounted drives for prior project folders.'
              : 'EmberWriter searched the available project recovery locations.'}
          </p>
          <dl>
            <div><dt>Found</dt><dd>{report.found}</dd></div>
            <div><dt>Recovered</dt><dd>{report.recovered_count}</dd></div>
            <div><dt>Library</dt><dd>{report.projects_count ?? '—'}</dd></div>
          </dl>
          {report.error && <p className="project-recovery-error">{report.error}</p>}
          {report.recovered.length > 0 && (
            <details open>
              <summary>Recovered projects</summary>
              {report.recovered.map((item, index) => (
                <div key={`${item.source_path || item.path || item.name}-${index}`} className="recovery-path">
                  <strong>{item.name}</strong>
                  <span>{item.source_path || item.path}</span>
                </div>
              ))}
            </details>
          )}
          <details>
            <summary>Searched locations ({report.searched_roots.length})</summary>
            {report.searched_roots.map((root) => <div className="recovery-path" key={root}>{root}</div>)}
          </details>
          <div className="project-recovery-actions">
            <button type="button" onClick={() => void recover()} disabled={busy}>
              {busy ? 'Searching…' : 'Recover old work'}
            </button>
            <button type="button" onClick={() => setExpanded(false)}>Close</button>
          </div>
        </div>
      )}
    </div>
  )
}
