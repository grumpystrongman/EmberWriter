import { useEffect, useRef, useState } from 'react'
import './project-recovery-status.css'

const API = 'http://127.0.0.1:8000/api'

type RecoveryItem = {
  name: string
  path?: string
  source_path?: string
  reason?: string
  signature?: string
  discovery?: string
  history_restored_count?: number
}

type RecoveryReport = {
  attempted: boolean
  found: number
  recovered_count: number
  history_restored_count?: number
  recovered: RecoveryItem[]
  skipped: RecoveryItem[]
  active_projects_root: string
  searched_roots: string[]
  historical_launch_roots?: string[]
  drive_wide_scan: boolean
  projects_count?: number
  error?: string | null
}

type ProjectDetail = {
  slug: string
  name: string
}

export default function ProjectRecoveryStatus() {
  const [report, setReport] = useState<RecoveryReport | null>(null)
  const [busy, setBusy] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const [actionMessage, setActionMessage] = useState('')
  const folderRef = useRef<HTMLInputElement>(null)
  const manuscriptRef = useRef<HTMLInputElement>(null)

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
    setActionMessage('Searching historical EmberWriter storage locations and version history…')
    try {
      const response = await fetch(`${API}/projects/recover`, { method: 'POST' })
      if (!response.ok) throw new Error(`${response.status} ${response.statusText}`)
      const result = await response.json() as RecoveryReport
      setReport(result)
      setActionMessage(
        result.recovered_count > 0
          ? `Recovered ${result.recovered_count} project${result.recovered_count === 1 ? '' : 's'}.`
          : 'No recoverable project was found in the historical storage locations scanned.',
      )
      if (result.recovered_count > 0) {
        window.setTimeout(() => window.location.reload(), 900)
      }
    } catch (error) {
      setActionMessage(`Recovery failed: ${(error as Error).message}`)
      setReport((current) => ({
        attempted: true,
        found: current?.found || 0,
        recovered_count: current?.recovered_count || 0,
        recovered: current?.recovered || [],
        skipped: current?.skipped || [],
        active_projects_root: current?.active_projects_root || '',
        searched_roots: current?.searched_roots || [],
        historical_launch_roots: current?.historical_launch_roots || [],
        drive_wide_scan: current?.drive_wide_scan || false,
        error: (error as Error).message,
      }))
    } finally {
      setBusy(false)
    }
  }

  async function restoreFolder(files: File[]) {
    if (!files.length || busy) return
    setBusy(true)
    setExpanded(true)
    setActionMessage(`Restoring ${files.length} file${files.length === 1 ? '' : 's'} from the selected EmberWriter folder…`)
    try {
      const form = new FormData()
      for (const file of files) {
        form.append('files', file, file.name)
        form.append('paths', file.webkitRelativePath || file.name)
      }
      const response = await fetch(`${API}/projects/restore-upload`, { method: 'POST', body: form })
      const body = await response.json().catch(() => ({})) as {
        detail?: string
        project?: ProjectDetail
        history_restored_count?: number
      }
      if (!response.ok) throw new Error(body.detail || `${response.status} ${response.statusText}`)
      setActionMessage(
        `Restored ${body.project?.name || 'EmberWriter project'}` +
        `${body.history_restored_count ? ` · reconstructed ${body.history_restored_count} manuscript file${body.history_restored_count === 1 ? '' : 's'} from history` : ''}.`,
      )
      window.setTimeout(() => window.location.reload(), 900)
    } catch (error) {
      setActionMessage(`Folder restore failed: ${(error as Error).message}`)
    } finally {
      setBusy(false)
    }
  }

  async function importManuscript(files: File[]) {
    if (!files.length || busy) return
    setBusy(true)
    setExpanded(true)
    setActionMessage(`Creating a project and importing ${files.length} manuscript file${files.length === 1 ? '' : 's'}…`)
    try {
      const firstName = files[0].name.replace(/\.[^.]+$/, '').trim() || 'Imported Manuscript'
      const createResponse = await fetch(`${API}/projects`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: firstName, description: 'Imported manuscript' }),
      })
      const project = await createResponse.json().catch(() => ({})) as ProjectDetail & { detail?: string }
      if (!createResponse.ok || !project.slug) {
        throw new Error(project.detail || `${createResponse.status} ${createResponse.statusText}`)
      }

      const form = new FormData()
      files.forEach((file) => form.append('files', file, file.name))
      form.append('mode', 'novel')
      const importResponse = await fetch(`${API}/projects/${project.slug}/import/files`, {
        method: 'POST',
        body: form,
      })
      const imported = await importResponse.json().catch(() => ({})) as { detail?: string; documents?: number; words?: number }
      if (!importResponse.ok) {
        throw new Error(imported.detail || `${importResponse.status} ${importResponse.statusText}`)
      }
      setActionMessage(
        `Imported ${imported.documents || 0} document${imported.documents === 1 ? '' : 's'} · ${(imported.words || 0).toLocaleString()} words.`,
      )
      window.setTimeout(() => window.location.reload(), 900)
    } catch (error) {
      setActionMessage(`Manuscript import failed: ${(error as Error).message}`)
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    folderRef.current?.setAttribute('webkitdirectory', '')
    folderRef.current?.setAttribute('directory', '')
    const timer = window.setTimeout(() => void loadStatus(), 1200)
    return () => window.clearTimeout(timer)
  }, [])

  if (!report) return null

  const label = busy
    ? 'Recovery / import working…'
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
          <strong>Recovery & import</strong>
          <p>
            EmberWriter now checks the storage locations used by its older Windows launchers, including inherited PowerShell working directories and available version-history data.
          </p>
          <dl>
            <div><dt>Found</dt><dd>{report.found}</dd></div>
            <div><dt>Recovered</dt><dd>{report.recovered_count}</dd></div>
            <div><dt>From history</dt><dd>{report.history_restored_count ?? 0}</dd></div>
            <div><dt>Library</dt><dd>{report.projects_count ?? '—'}</dd></div>
          </dl>
          {actionMessage && <p className="project-recovery-message">{actionMessage}</p>}
          {report.error && <p className="project-recovery-error">{report.error}</p>}
          {report.recovered.length > 0 && (
            <details open>
              <summary>Recovered projects</summary>
              {report.recovered.map((item, index) => (
                <div key={`${item.source_path || item.path || item.name}-${index}`} className="recovery-path">
                  <strong>{item.name}</strong>
                  <span>{item.source_path || item.path}</span>
                  {item.history_restored_count ? <span>{item.history_restored_count} manuscript file(s) reconstructed from EmberWriter history</span> : null}
                </div>
              ))}
            </details>
          )}

          <input
            ref={folderRef}
            className="hidden-file-input"
            type="file"
            multiple
            onChange={(event) => {
              const files = Array.from(event.target.files || [])
              if (files.length) void restoreFolder(files)
              event.target.value = ''
            }}
          />
          <input
            ref={manuscriptRef}
            className="hidden-file-input"
            type="file"
            multiple
            accept=".docx,.pdf,.epub,.rtf,.md,.txt,.html,.htm"
            onChange={(event) => {
              const files = Array.from(event.target.files || [])
              if (files.length) void importManuscript(files)
              event.target.value = ''
            }}
          />

          <div className="project-recovery-actions project-recovery-actions-stacked">
            <button type="button" onClick={() => void recover()} disabled={busy}>
              {busy ? 'Working…' : 'Forensic recovery scan'}
            </button>
            <button type="button" onClick={() => folderRef.current?.click()} disabled={busy}>
              Restore EmberWriter folder…
            </button>
            <button type="button" onClick={() => manuscriptRef.current?.click()} disabled={busy}>
              Import manuscript into new project…
            </button>
            <button type="button" onClick={() => setExpanded(false)}>Close</button>
          </div>

          {(report.historical_launch_roots?.length || 0) > 0 && (
            <details>
              <summary>Historical launcher locations ({report.historical_launch_roots?.length || 0})</summary>
              {report.historical_launch_roots?.map((root) => <div className="recovery-path" key={`history-${root}`}>{root}</div>)}
            </details>
          )}
          <details>
            <summary>All searched locations ({report.searched_roots.length})</summary>
            {report.searched_roots.map((root) => <div className="recovery-path" key={root}>{root}</div>)}
          </details>
        </div>
      )}
    </div>
  )
}