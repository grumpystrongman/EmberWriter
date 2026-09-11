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
    <section className="authoring-panel import-panel" aria-label="Import manuscript and writing material">
      <button
        type="button"
        className="primary import-toggle"
        disabled={disabled}
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        title="Import a complete novel, novel portion, idea, or research file"
      >
        <span>{open ? '▾' : '▸'} Import Manuscript</span>
        <small>DOCX · PDF · EPUB · RTF · MD · TXT · HTML</small>
      </button>

      {open && (
        <div className="authoring-panel-body">
          <label>Import as</label>
          <select value={mode} onChange={(event) => setMode(event.target.value as ImportMode)} disabled={disabled}>
            <option value="novel">Whole novel — detect and split chapters</option>
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
            Choose manuscript file…
          </button>
          <small className="panel-help">
            Whole novel mode detects chapter, prologue, epilogue, interlude, and part boundaries and creates real Binder documents.
          </small>

          <div className="panel-divider" />
          <label>Or paste writing material</label>
          <input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Title / idea name" disabled={disabled} />
          <textarea value={text} onChange={(event) => setText(event.target.value)} placeholder="Paste a novel, scene, outline, lore, or raw idea…" disabled={disabled} />
          <button type="button" disabled={disabled || !text.trim()} onClick={() => void submitText()}>Import pasted text</button>
        </div>
      )}
    </section>
  )
}
