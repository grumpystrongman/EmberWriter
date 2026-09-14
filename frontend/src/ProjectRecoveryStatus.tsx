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

type ProjectLoadResult = {
  detail?: string
  project?: ProjectDetail
  projects?: ProjectDetail[]
  loaded_count?: number
  reused_count?: number
  copied_count?: number
  history_restored_count?: number
}

const EMPTY_REPORT: RecoveryReport = {
  attempted: false,
  found: 0,
  recovered_count: 0,
  history_restored_count: 0,
  recovered: [],
  skipped: [],
  active_projects_root: '',
  searched_roots: [],
  historical_launch_roots: [],
  drive_wide_scan: false,
}

function projectLoadMessage(body: ProjectLoadResult, source: 'folder' | 'path') {
  const loadedCount = body.loaded_count ?? body.projects?.length ?? (body.project ? 1 : 0)
  const reusedCount = body.reused_count ?? 0
  const copiedCount = body.copied_count ?? 0
  const historyCount = body.history_restored_count ?? 0

  if (loadedCount > 1) {
    return `Loaded ${loadedCount} EmberWriter projects` +
      `${source === 'path' ? ' directly from disk' : ' from the selected library folder'}` +
      `${copiedCount ? ` · copied ${copiedCount} into this library` : ''}` +
      `${reusedCount ? ` · ${reusedCount} already in this library` : ''}` +
      `${historyCount ? ` · reconstructed ${historyCount} manuscript files from history` : ''}.`
  }

  return `Loaded ${body.project?.name || 'EmberWriter project'}` +
    `${source === 'path' ? ' directly from disk' : ''}` +
    `${copiedCount ? ' into this library' : ''}` +
    `${reusedCount ? ' from the existing library' : ''}` +
    `${historyCount ? ` · reconstructed ${historyCount} manuscript file${historyCount === 1 ? '' : 's'} from history` : ''}.`
}

export default function ProjectRecoveryStatus() {
  const [report, setReport] = useState<RecoveryReport | null>(null)
  const [busy, setBusy] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const [actionMessage, setActionMessage] = useState('')
  const [localPath, setLocalPath] = useState('')
  const folderRef = useRef<HTMLInputElement>(null)
  const manuscriptRef = useRef<HTMLInputElement>(null)

  async function loadStatus() {
    try {
      const response = await fetch(`${API}/projects/recovery-status`)
      if (!response.ok) return
      setReport(await response.json() as RecoveryReport)
    } catch {
      // Loading/importing must remain available even if recovery status fails.
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
        ...(current || EMPTY_REPORT),
        attempted: true,
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
    setActionMessage(`Loading ${files.length} file${files.length === 1 ? '' : 's'} from the selected EmberWriter project or library…`)
    try {
      const form = new FormData()
      for (const file of files) {
        form.append('files', file, file.name)
        form.append('paths', file.webkitRelativePath || file.name)
      }
      const response = await fetch(`${API}/projects/restore-upload`, { method: 'POST', body: form })
      const body = await response.json().catch(() => ({})) as ProjectLoadResult
      if (!response.ok) throw new Error(body.detail || `${response.status} ${response.statusText}`)

      setActionMessage(projectLoadMessage(body, 'folder'))
      window.setTimeout(() => window.location.reload(), 900)
    } catch (error) {
      const message = (error as Error).message
      setActionMessage(
        message === 'Failed to fetch'
          ? 'The folder was selected, but the browser could not reach EmberWriter while uploading it. Paste the Windows folder path below and use Load path directly.'
          : `Project load failed: ${message}`,
      )
    } finally {
      setBusy(false)
    }
  }

  async function loadLocalPath() {
    const sourcePath = localPath.trim()
    if (!sourcePath || busy) return
    setBusy(true)
    setExpanded(true)
    setActionMessage('Loading EmberWriter project data directly from the local folder…')
    try {
      const response = await fetch(`${API}/projects/load-path`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_path: sourcePath }),
      })
      const body = await response.json().catch(() => ({})) as ProjectLoadResult
      if (!response.ok) throw new Error(body.detail || `${response.status} ${response.statusText}`)
      setActionMessage(projectLoadMessage(body, 'path'))
      window.setTimeout(() => window.location.reload(), 900)
    } catch (error) {
      setActionMessage(`Direct path load failed: ${(error as Error).message}`)
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
    const timer = window.setTimeout(() => void loadStatus(), 300)

    function onKeyDown(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'o') {
        event.preventDefault()
        setExpanded(true)
      }
    }

    window.addEventListener('keydown', onKeyDown)
    return () => {
      window.clearTimeout(timer)
      window.removeEventListener('keydown', onKeyDown)
    }
  }, [])

  const current = report || EMPTY_REPORT

  return (
    <div className={`project-recovery-status${expanded ? ' expanded' : ''}`}>
      <div className="load-import-launch-row">
        <button
          className="load-import-launcher"
          type="button"
          onClick={() => setExpanded(true)}
          aria-expanded={expanded}
          title="Load an EmberWriter project/library or import a manuscript · Ctrl/Cmd+O"
        >
          <span className="load-import-icon">↥</span>
          <span><strong>LOAD / IMPORT</strong><small>Project, library, or manuscript</small></span>
        </button>
        {current.attempted && (
          <button
            className="project-recovery-chip"
            type="button"
            onClick={() => setExpanded((value) => !value)}
            title="Recovery status"
          >
            <span className={current.recovered_count > 0 ? 'recovery-dot found' : current.error ? 'recovery-dot error' : 'recovery-dot'} />
            {current.recovered_count > 0 ? `${current.recovered_count} recovered` : `${current.found} found`}
          </button>
        )}
      </div>

      {expanded && (
        <div className="project-recovery-card load-import-card">
          <div className="load-import-heading">
            <div><strong>Load / Import</strong><p>Open existing EmberWriter work or bring a manuscript into a new project.</p></div>
            <button type="button" className="load-import-close" onClick={() => setExpanded(false)} aria-label="Close Load / Import">×</button>
          </div>

          {actionMessage && <p className="project-recovery-message">{actionMessage}</p>}
          {current.error && <p className="project-recovery-error">{current.error}</p>}

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

          <div className="load-import-primary-actions">
            <button type="button" className="load-import-action primary-action" onClick={() => folderRef.current?.click()} disabled={busy}>
              <span>▣</span>
              <span>
                <strong>Load EmberWriter Project or Library Folder</strong>
                <small>Select one project folder such as nh-ghost-story, or select the parent data/projects folder to load every EmberWriter project inside it.</small>
              </span>
            </button>
            <button type="button" className="load-import-action" onClick={() => manuscriptRef.current?.click()} disabled={busy}>
              <span>＋</span>
              <span><strong>Import Manuscript</strong><small>DOCX, PDF, EPUB, RTF, Markdown, text, or HTML. Creates a new project automatically.</small></span>
            </button>
          </div>

          <div className="local-path-load">
            <div>
              <strong>Direct local folder path</strong>
              <small>Best for EmberWriter work already on this PC. The backend reads the folder directly instead of uploading it through the browser.</small>
            </div>
            <div className="local-path-load-row">
              <input
                type="text"
                value={localPath}
                onChange={(event) => setLocalPath(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') void loadLocalPath()
                }}
                placeholder={'C:\\Users\\...\\data\\projects'}
                aria-label="Local EmberWriter project or projects library path"
              />
              <button type="button" onClick={() => void loadLocalPath()} disabled={busy || !localPath.trim()}>
                Load path directly
              </button>
            </div>
          </div>

          <div className="recovery-separator"><span>Lost work?</span></div>
          <button type="button" className="forensic-recovery-button" onClick={() => void recover()} disabled={busy}>
            {busy ? 'Working…' : 'Search this computer for older EmberWriter projects'}
          </button>

          {current.recovered.length > 0 && (
            <details open>
              <summary>Recovered projects</summary>
              {current.recovered.map((item, index) => (
                <div key={`${item.source_path || item.path || item.name}-${index}`} className="recovery-path">
                  <strong>{item.name}</strong>
                  <span>{item.source_path || item.path}</span>
                  {item.history_restored_count ? <span>{item.history_restored_count} manuscript file(s) reconstructed from EmberWriter history</span> : null}
                </div>
              ))}
            </details>
          )}

          {current.attempted && (
            <details>
              <summary>Recovery scan details</summary>
              <dl>
                <div><dt>Found</dt><dd>{current.found}</dd></div>
                <div><dt>Recovered</dt><dd>{current.recovered_count}</dd></div>
                <div><dt>From history</dt><dd>{current.history_restored_count ?? 0}</dd></div>
                <div><dt>Library</dt><dd>{current.projects_count ?? '—'}</dd></div>
              </dl>
              {(current.historical_launch_roots?.length || 0) > 0 && (
                <details>
                  <summary>Historical launcher locations ({current.historical_launch_roots?.length || 0})</summary>
                  {current.historical_launch_roots?.map((root) => <div className="recovery-path" key={`history-${root}`}>{root}</div>)}
                </details>
              )}
              {current.searched_roots.length > 0 && (
                <details>
                  <summary>All searched locations ({current.searched_roots.length})</summary>
                  {current.searched_roots.map((root) => <div className="recovery-path" key={root}>{root}</div>)}
                </details>
              )}
            </details>
          )}
        </div>
      )}
    </div>
  )
}
