import { useEffect, useMemo, useState } from 'react'

type Revision = {
  id: string
  path: string
  parent_revision_id: string | null
  created_at: string
  source: string
  note: string
  content_hash: string
  word_count: number
}

type DiffResult = {
  path: string
  diff: string
}

type Props = {
  apiBase: string
  slug: string
  path: string
  disabled: boolean
  refreshToken: number
  onRestored: () => Promise<void>
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

export default function VersionHistoryPanel({ apiBase, slug, path, disabled, refreshToken, onRestored }: Props) {
  const [revisions, setRevisions] = useState<Revision[]>([])
  const [selectedId, setSelectedId] = useState<string>('')
  const [diff, setDiff] = useState('')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!slug || !path) {
      setRevisions([])
      return
    }
    let cancelled = false
    void request<Revision[]>(`${apiBase}/projects/${slug}/revisions?path=${encodeURIComponent(path)}`)
      .then((items) => {
        if (cancelled) return
        setRevisions(items)
        setSelectedId((current) => current && items.some((item) => item.id === current) ? current : items[0]?.id || '')
      })
      .catch((cause) => { if (!cancelled) setError((cause as Error).message) })
    return () => { cancelled = true }
  }, [apiBase, slug, path, refreshToken])

  const selected = useMemo(
    () => revisions.find((item) => item.id === selectedId) || null,
    [revisions, selectedId],
  )

  async function createCheckpoint() {
    if (!path || busy) return
    setBusy(true)
    setError('')
    try {
      await request(`${apiBase}/projects/${slug}/revisions/checkpoint`, {
        method: 'POST',
        body: JSON.stringify({ path, note }),
      })
      const items = await request<Revision[]>(`${apiBase}/projects/${slug}/revisions?path=${encodeURIComponent(path)}`)
      setRevisions(items)
      setSelectedId(items[0]?.id || '')
      setNote('')
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function compareCurrent() {
    if (!selectedId || busy) return
    setBusy(true)
    setError('')
    try {
      const result = await request<DiffResult>(`${apiBase}/projects/${slug}/revisions/${selectedId}/diff`)
      setDiff(result.diff || 'No changes from this revision to the current document.')
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
      await request(`${apiBase}/projects/${slug}/revisions/${selectedId}/restore`, {
        method: 'POST',
        body: JSON.stringify({ note: `Restored from ${timeLabel(selected?.created_at || '')}` }),
      })
      await onRestored()
      const items = await request<Revision[]>(`${apiBase}/projects/${slug}/revisions?path=${encodeURIComponent(path)}`)
      setRevisions(items)
      setSelectedId(items[0]?.id || '')
      setDiff('')
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <details className="authoring-panel">
      <summary>Version History <small>{revisions.length} revisions</small></summary>
      <div className="authoring-panel-body">
        <div className="checkpoint-row">
          <input value={note} onChange={(event) => setNote(event.target.value)} placeholder="Checkpoint note (optional)" disabled={disabled || busy} />
          <button type="button" onClick={() => void createCheckpoint()} disabled={disabled || busy || !path}>Checkpoint</button>
        </div>
        {revisions.length === 0 ? (
          <small className="panel-help">No revisions yet. Saving this document or making a checkpoint creates durable history.</small>
        ) : (
          <>
            <select value={selectedId} onChange={(event) => { setSelectedId(event.target.value); setDiff('') }} disabled={busy}>
              {revisions.map((revision) => (
                <option key={revision.id} value={revision.id}>
                  {timeLabel(revision.created_at)} · {revision.source} · {revision.word_count} words{revision.note ? ` · ${revision.note}` : ''}
                </option>
              ))}
            </select>
            <div className="history-actions">
              <button type="button" onClick={() => void compareCurrent()} disabled={busy || !selectedId}>Diff vs current</button>
              <button type="button" onClick={() => void restore()} disabled={busy || !selectedId}>Restore this revision</button>
            </div>
            {diff && <pre className="revision-diff">{diff}</pre>}
          </>
        )}
        {error && <small className="panel-error">{error}</small>}
      </div>
    </details>
  )
}
