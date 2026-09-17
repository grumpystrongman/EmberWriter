import { useEffect, useMemo, useState } from 'react'

import CaptureComposer from './CaptureComposer'
import {
  loadInbox,
  saveInbox,
  type CaptureItem,
  type ProjectSummary,
} from './capture-store'
import type { WorkspaceProject } from './workspace-types'
import './tools-notes.css'

type Props = {
  project: WorkspaceProject
  onOpenSource: (path: string, anchor?: string) => void
}

export default function NotesWorkspace({ project, onOpenSource }: Props) {
  const [items, setItems] = useState<CaptureItem[]>([])
  const [query, setQuery] = useState('')
  const [showArchived, setShowArchived] = useState(false)
  const [status, setStatus] = useState('')
  const captureProject: ProjectSummary = project

  useEffect(() => {
    void refresh()
    function onChanged(event: Event) {
      const detail = (event as CustomEvent<{ slug?: string }>).detail
      if (!detail?.slug || detail.slug === project.slug) void refresh()
    }
    window.addEventListener('emberwriter:notes-changed', onChanged)
    return () => window.removeEventListener('emberwriter:notes-changed', onChanged)
  }, [project.slug])

  async function refresh() {
    setStatus('')
    try {
      setItems(await loadInbox(captureProject))
    } catch (cause) {
      setStatus((cause as Error).message)
    }
  }

  async function setArchived(id: string, archived: boolean) {
    const next = items.map((item) => item.id === id
      ? { ...item, status: archived ? 'archived' as const : 'open' as const, updated_at: new Date().toISOString() }
      : item)
    setItems(next)
    try {
      await saveInbox(captureProject, next)
      window.dispatchEvent(new CustomEvent('emberwriter:notes-changed', { detail: { slug: project.slug } }))
    } catch (cause) {
      setStatus((cause as Error).message)
      await refresh()
    }
  }

  const visible = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase()
    return items.filter((item) => {
      if (!showArchived && item.status === 'archived') return false
      if (showArchived && item.status !== 'archived') return false
      if (!needle) return true
      return `${item.text} ${item.kind} ${item.context_path}`.toLocaleLowerCase().includes(needle)
    })
  }, [items, query, showArchived])

  const activeCount = items.filter((item) => item.status !== 'archived').length
  const archivedCount = items.length - activeCount

  return (
    <section className="center-tool notes-workspace">
      <header className="center-tool-header">
        <div>
          <small>NOTES · {project.name}</small>
          <h1>Idea Notes</h1>
          <p>Drop a thought from anywhere with the sticky-note button, then come back here when you are ready to sort, route, or act on it.</p>
        </div>
        <div className="center-tool-actions">
          <button type="button" className="primary" onClick={() => window.dispatchEvent(new CustomEvent('emberwriter:new-sticky-note'))}>▰ New sticky</button>
          <button type="button" onClick={() => void refresh()}>↻ Refresh</button>
        </div>
      </header>

      <div className="notes-toolbar">
        <div className="notes-counts">
          <button type="button" className={!showArchived ? 'active' : ''} onClick={() => setShowArchived(false)}>Active <span>{activeCount}</span></button>
          <button type="button" className={showArchived ? 'active' : ''} onClick={() => setShowArchived(true)}>Archived <span>{archivedCount}</span></button>
        </div>
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search your notes…" />
      </div>

      <div className="notes-grid">
        {visible.length === 0 && (
          <div className="center-empty notes-empty">
            {showArchived ? 'No archived notes.' : 'No notes yet. Click ▰ Note in the top bar whenever an idea hits.'}
          </div>
        )}
        {visible.map((item) => (
          <article className="note-card" key={item.id}>
            <div className="note-card-meta">
              <span>{item.kind}</span>
              <small>{new Date(item.created_at).toLocaleString()}</small>
            </div>
            <p>{item.text}</p>
            <footer>
              <div>
                {item.context_path ? (
                  <button type="button" className="note-context" onClick={() => onOpenSource(item.context_path)} title={item.context_path}>↗ {item.context_path}</button>
                ) : <span className="note-context-label">Project-wide note</span>}
                {item.destination !== 'inbox' && <span className="note-routed">Routed: {item.destination.replace('_', ' ')}</span>}
              </div>
              <button type="button" onClick={() => void setArchived(item.id, !showArchived)}>{showArchived ? 'Restore' : 'Archive'}</button>
            </footer>
          </article>
        ))}
      </div>

      <details className="notes-capture-tools">
        <summary>More capture options · dictate, classify, or route an idea</summary>
        <CaptureComposer project={captureProject} items={items} onItems={(next) => { setItems(next); window.dispatchEvent(new CustomEvent('emberwriter:notes-changed', { detail: { slug: project.slug } })) }} />
      </details>

      {status && <div className="center-error">{status}</div>}
    </section>
  )
}
