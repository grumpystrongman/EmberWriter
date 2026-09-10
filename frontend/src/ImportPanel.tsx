import { useRef, useState } from 'react'

import type { BinderState } from './BinderPanel'

type ImportMode = 'novel' | 'portion' | 'idea' | 'research'

type Props = {
  disabled: boolean
  onFiles: (files: File[], mode: ImportMode) => Promise<BinderState | null>
  onText: (title: string, content: string, mode: ImportMode) => Promise<BinderState | null>
}

export default function ImportPanel({ disabled, onFiles, onText }: Props) {
  const [mode, setMode] = useState<ImportMode>('novel')
  const [title, setTitle] = useState('')
  const [text, setText] = useState('')
  const [open, setOpen] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  async function submitText() {
    if (!text.trim()) return
    const result = await onText(title.trim() || 'Imported Text', text, mode)
    if (result) {
      setText('')
      setTitle('')
    }
  }

  return (
    <details className="authoring-panel" open={open} onToggle={(event) => setOpen(event.currentTarget.open)}>
      <summary>Import <small>novel · portions · ideas</small></summary>
      <div className="authoring-panel-body">
        <label>Import as</label>
        <select value={mode} onChange={(event) => setMode(event.target.value as ImportMode)} disabled={disabled}>
          <option value="novel">Novel — split detected chapters</option>
          <option value="portion">Novel portion — one document</option>
          <option value="idea">Idea / notes</option>
          <option value="research">Research</option>
        </select>
        <input
          ref={inputRef}
          className="hidden-file-input"
          type="file"
          multiple
          accept=".docx,.pdf,.epub,.rtf,.md,.txt,.html,.htm"
          onChange={(event) => {
            const files = Array.from(event.target.files || [])
            if (files.length) void onFiles(files, mode)
            event.target.value = ''
          }}
        />
        <button type="button" disabled={disabled} onClick={() => inputRef.current?.click()}>
          Choose files…
        </button>
        <small className="panel-help">DOCX, PDF, EPUB, RTF, Markdown, text, and HTML. Novel mode detects chapter/prologue/epilogue boundaries and creates Binder documents.</small>

        <div className="panel-divider" />
        <label>Paste material</label>
        <input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Title / idea name" disabled={disabled} />
        <textarea value={text} onChange={(event) => setText(event.target.value)} placeholder="Paste a novel, scene, outline, lore, or raw idea…" disabled={disabled} />
        <button type="button" disabled={disabled || !text.trim()} onClick={() => void submitText()}>Import pasted text</button>
      </div>
    </details>
  )
}
