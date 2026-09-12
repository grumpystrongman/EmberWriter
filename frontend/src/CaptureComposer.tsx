import { useRef, useState } from 'react'

import {
  createCapture,
  routeCapture,
  saveInbox,
  type CaptureItem,
  type CaptureKind,
  type Destination,
  type ProjectSummary,
} from './capture-store'

type Props = {
  project: ProjectSummary
  items: CaptureItem[]
  onItems: (items: CaptureItem[]) => void
}

export default function CaptureComposer({ project, items, onItems }: Props) {
  const [text, setText] = useState('')
  const [kind, setKind] = useState<CaptureKind>('idea')
  const [destination, setDestination] = useState<Destination>('inbox')
  const [status, setStatus] = useState('')
  const [busy, setBusy] = useState(false)
  const input = useRef<HTMLTextAreaElement>(null)

  function dictate() {
    input.current?.focus()
    setStatus(navigator.platform.toLowerCase().includes('mac')
      ? 'Use your macOS dictation shortcut and start speaking.'
      : 'Press Win+H and start speaking.')
  }

  async function save() {
    if (!text.trim() || busy) return
    setBusy(true)
    try {
      const item = createCapture(text, kind, destination, 'typed')
      await routeCapture(project, item)
      const next = [item, ...items]
      await saveInbox(project, next)
      onItems(next)
      setText('')
      setStatus(destination === 'inbox' ? 'Saved to Idea Inbox.' : 'Saved and routed to project files.')
    } catch (cause) {
      setStatus((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return <div className="capture-compose">
    <button type="button" className="capture-dictate" onClick={dictate}>🎙 Dictate idea</button>
    <textarea ref={input} rows={6} value={text} onChange={(event) => setText(event.target.value)} placeholder="Speak with system dictation or type it exactly as it comes to you…" />
    <div className="capture-fields">
      <label>Kind<select value={kind} onChange={(event) => setKind(event.target.value as CaptureKind)}>{['idea','dialogue','character','world','plot','scene','research','todo'].map((value) => <option key={value}>{value}</option>)}</select></label>
      <label>Send to<select value={destination} onChange={(event) => setDestination(event.target.value as Destination)}><option value="inbox">Idea Inbox only</option><option value="beat_sheet">Beat Sheet</option><option value="world">World note</option><option value="character">Character note</option><option value="scene">Scene note</option><option value="project_note">Project note</option></select></label>
      <button type="button" className="primary" onClick={() => void save()} disabled={!text.trim() || busy}>{busy ? 'Saving…' : destination === 'inbox' ? 'Save idea' : 'Save & route'}</button>
    </div>
    {status && <div className="capture-status">{status}</div>}
  </div>
}
