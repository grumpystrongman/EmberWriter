import { useState } from 'react'

import CaptureComposer from './CaptureComposer'
import CaptureInbox from './CaptureInbox'
import { loadInbox, resolveActiveProject, type CaptureItem, type ProjectSummary } from './capture-store'
import './author-capture.css'

export default function AuthorCaptureOverlay() {
  const [open, setOpen] = useState(false)
  const [project, setProject] = useState<ProjectSummary | null>(null)
  const [items, setItems] = useState<CaptureItem[]>([])
  const [status, setStatus] = useState('')

  async function show() {
    setOpen(true)
    setStatus('')
    try {
      const active = await resolveActiveProject()
      setProject(active)
      if (!active) return setStatus('Open a story project before capturing an idea.')
      setItems(await loadInbox(active))
    } catch (cause) {
      setStatus((cause as Error).message)
    }
  }

  return <>
    <button type="button" className="capture-fab" onClick={() => void show()} title="Capture an idea">🎙</button>
    {open && <div className="capture-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setOpen(false) }}>
      <section className="capture-modal" role="dialog" aria-modal="true" aria-label="Idea Capture and Inbox">
        <header><div><small>AUTHOR CAPTURE</small><h2>Talk Capture & Idea Inbox</h2><p>{project?.name || 'No active project'}</p></div><button type="button" onClick={() => setOpen(false)}>×</button></header>
        {status && <div className="capture-status">{status}</div>}
        {project && <><CaptureComposer project={project} items={items} onItems={setItems} /><CaptureInbox project={project} items={items} onItems={setItems} /></>}
      </section>
    </div>}
  </>
}
