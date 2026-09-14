import { useEffect, useRef, useState } from 'react'

import type { BinderState } from './BinderPanel'

type ImportMode = 'novel' | 'portion' | 'idea' | 'research'

type Props = {
  disabled: boolean
  onFiles: (files: File[], mode: ImportMode) => Promise<BinderState | null>
  onText: (title: string, content: string, mode: ImportMode) => Promise<BinderState | null>
  onProjectFolder?: (files: File[]) => Promise<boolean>
}

export default function ImportPanel({ disabled, onFiles, onText, onProjectFolder }: Props) {
  const [mode, setMode] = useState<ImportMode>('novel')
  const [title, setTitle] = useState('')
  const [text, setText] = useState('')
  const [open, setOpen] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const folderRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    // React's input typings do not expose the Chromium directory picker flag,
    // so apply it directly to the DOM input. File.webkitRelativePath preserves
    // the EmberWriter project tree for the restore endpoint.
    folderRef.current?.setAttribute('webkitdirectory', '')
    folderRef.current?.setAttribute('directory', '')
  }, [])

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
        title="Import a manuscript or restore an EmberWriter project folder"
      >
        <span>{open ? '▾' : '▸'} Import / Restore</span>
        <small>Manuscript files · EmberWriter project folders</small>
      </button>

      {open && (
        <div className="authoring-panel-body">
          {onProjectFolder && <>
            <label>Restore an EmberWriter project</label>
            <input
              ref={folderRef}
              className="hidden-file-input"
              type="file"
              multiple
              onChange={(event) => {
                const files = Array.from(event.target.files || [])
                if (files.length) void onProjectFolder(files)
                event.target.value = ''
              }}
            />
            <button type="button" disabled={disabled} onClick={() => folderRef.current?.click()}>
              Restore EmberWriter folder…
            </button>
            <small className="panel-help">
              Choose the old project folder itself. EmberWriter preserves manuscript files, Binder data, .ember history, revisions, checkpoints, and snapshots when present.
            </small>
            <div className="panel-divider" />
          </>}

          <label>Import manuscript as</label>
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