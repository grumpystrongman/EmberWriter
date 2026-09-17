import { useEffect, useRef, useState } from 'react'

import {
  activeDocumentPath,
  createCapture,
  loadInbox,
  resolveActiveProject,
  saveInbox,
  type ProjectSummary,
} from './capture-store'
import './tools-notes.css'

export default function StickyNoteOverlay() {
  const [open, setOpen] = useState(false)
  const [project, setProject] = useState<ProjectSummary | null>(null)
  const [text, setText] = useState('')
  const [status, setStatus] = useState('')
  const [busy, setBusy] = useState(false)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    function show() {
      setOpen(true)
      setText('')
      setStatus('')
      void resolveActiveProject()
        .then((active) => {
          setProject(active)
          if (!active) setStatus('Open a story project first so this note has somewhere to live.')
          window.setTimeout(() => inputRef.current?.focus(), 30)
        })
        .catch((cause) => setStatus((cause as Error).message))
    }

    window.addEventListener('emberwriter:new-sticky-note', show)
    return () => window.removeEventListener('emberwriter:new-sticky-note', show)
  }, [])

  async function close() {
    if (busy) return
    const body = text.trim()
    if (!body) {
      setOpen(false)
      setText('')
      return
    }
    if (!project) {
      setStatus('Open a story project before closing this note, or clear the note to dismiss it.')
      return
    }

    setBusy(true)
    setStatus('Saving note…')
    try {
      const latest = await loadInbox(project)
      const item = createCapture(body, 'idea', 'inbox', 'typed')
      await saveInbox(project, [item, ...latest])
      window.dispatchEvent(new CustomEvent('emberwriter:notes-changed', { detail: { slug: project.slug } }))
      setText('')
      setStatus('')
      setOpen(false)
    } catch (cause) {
      setStatus(`Could not save note: ${(cause as Error).message}`)
    } finally {
      setBusy(false)
    }
  }

  if (!open) return null

  const context = activeDocumentPath()

  return (
    <section className="sticky-note" role="dialog" aria-modal="false" aria-label="Quick sticky note">
      <header className="sticky-note-head">
        <div>
          <strong>Quick note</strong>
          <small>{project?.name || 'No project open'}</small>
        </div>
        <button type="button" onClick={() => void close()} disabled={busy} aria-label="Save and close sticky note">×</button>
      </header>
      <textarea
        ref={inputRef}
        value={text}
        onChange={(event) => setText(event.target.value)}
        onKeyDown={(event) => {
          if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
            event.preventDefault()
            void close()
          }
        }}
        placeholder="Paste the thought before it disappears…"
      />
      <footer className="sticky-note-foot">
        <span>{context ? `Attached to ${context}` : 'Project note · no document context'}</span>
        <span>{busy ? 'Saving…' : 'X saves & closes · Ctrl/Cmd+Enter'}</span>
      </footer>
      {status && <div className="sticky-note-status">{status}</div>}
    </section>
  )
}
