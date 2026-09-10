import { useEffect, useState } from 'react'

type ProjectCheckpoint = {
  id: string
  created_at: string
  label: string
  note: string
  source: string
  file_count: number
  total_bytes: number
}

type ProjectCompare = {
  checkpoint: ProjectCheckpoint
  changes: { path: string; status: 'added' | 'deleted' | 'modified' }[]
  changed_files: number
}

type Props = {
  apiBase: string
  slug: string
  disabled: boolean
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

function timeLabel(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

export default function ProjectHistoryPanel({ apiBase, slug, disabled }: Props) {
  const [items, setItems] = useState<ProjectCheckpoint[]>([])
  const [selectedId, setSelectedId] = useState('')
  const [label, setLabel] = useState('')
  const [note, setNote] = useState('')
  const [comparison, setComparison] = useState<ProjectCompare | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function refresh() {
    if (!slug) return
    const checkpoints = await request<ProjectCheckpoint[]>(`${apiBase}/projects/${slug}/project-checkpoints`)
    setItems(checkpoints)
    setSelectedId((current) => current && checkpoints.some((item) => item.id === current) ? current : checkpoints[0]?.id || '')
  }

  useEffect(() => {
    let cancelled = false
    void request<ProjectCheckpoint[]>(`${apiBase}/projects/${slug}/project-checkpoints`)
      .then((checkpoints) => {
        if (cancelled) return
        setItems(checkpoints)
        setSelectedId((current) => current && checkpoints.some((item) => item.id === current) ? current : checkpoints[0]?.id || '')
      })
      .catch((cause) => { if (!cancelled) setError((cause as Error).message) })
    return () => { cancelled = true }
  }, [apiBase, slug])

  async function createCheckpoint() {
    if (!label.trim() || busy) return
    setBusy(true)
    setError('')
    try {
      await request(`${apiBase}/projects/${slug}/project-checkpoints`, {
        method: 'POST',
        body: JSON.stringify({ label: label.trim(), note: note.trim() }),
      })
      setLabel('')
      setNote('')
      setComparison(null)
      await refresh()
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function compare() {
    if (!selectedId || busy) return
    setBusy(true)
    setError('')
    try {
      setComparison(await request<ProjectCompare>(`${apiBase}/projects/${slug}/project-checkpoints/${selectedId}/compare`))
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function restore() {
    if (!selectedId || busy) return
    setBusy(true)
    setError('')
    try {
      await request(`${apiBase}/projects/${slug}/project-checkpoints/${selectedId}/restore`, { method: 'POST' })
      window.location.reload()
    } catch (cause) {
      setError((cause as Error).message)
      setBusy(false)
    }
  }

  return (
    <details className="authoring-panel">
      <summary>Project History <small>{items.length} checkpoints</small></summary>
      <div className="authoring-panel-body">
        <input value={label} onChange={(event) => setLabel(event.target.value)} placeholder="Checkpoint name — Before ending rewrite" disabled={disabled || busy} />
        <textarea value={note} onChange={(event) => setNote(event.target.value)} placeholder="Optional note about this whole-project state" disabled={disabled || busy} />
        <button type="button" onClick={() => void createCheckpoint()} disabled={disabled || busy || !label.trim()}>Save whole-project checkpoint</button>
        {items.length > 0 && (
          <>
            <select value={selectedId} onChange={(event) => { setSelectedId(event.target.value); setComparison(null) }} disabled={busy}>
              {items.map((item) => (
                <option key={item.id} value={item.id}>
                  {timeLabel(item.created_at)} · {item.label} · {item.file_count} files
                </option>
              ))}
            </select>
            <div className="history-actions">
              <button type="button" onClick={() => void compare()} disabled={busy || !selectedId}>Compare to now</button>
              <button type="button" onClick={() => void restore()} disabled={busy || !selectedId}>Restore project</button>
            </div>
          </>
        )}
        {comparison && (
          <div className="project-compare">
            <strong>{comparison.changed_files} changed file{comparison.changed_files === 1 ? '' : 's'}</strong>
            {comparison.changes.length === 0 ? <small>No differences from this checkpoint.</small> : comparison.changes.map((change) => (
              <div key={change.path}><span>{change.status}</span><code>{change.path}</code></div>
            ))}
          </div>
        )}
        <small className="panel-help">Restoring a project automatically saves the current project as a safety checkpoint first, so the restore itself can be undone.</small>
        {error && <small className="panel-error">{error}</small>}
      </div>
    </details>
  )
}
