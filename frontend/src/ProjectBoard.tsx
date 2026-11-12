import { useEffect, useMemo, useRef, useState, type ChangeEvent, type PointerEvent } from 'react'

import type { BinderNode } from './BinderPanel'
import './project-board.css'

type BoardItemKind = 'sticky' | 'image' | 'attachment' | 'link' | 'binder'

type BoardItem = {
  id: string
  kind: BoardItemKind
  title: string
  body: string
  x: number
  y: number
  width: number
  height: number
  z: number
  color: string
  asset_path: string
  original_filename: string
  url: string
  binder_node_id: string
  parent_note_id?: string
  use_as_inspiration?: boolean
  created_at: string
  updated_at: string
}

type BoardState = {
  schema_version: number
  items: BoardItem[]
}

type Props = {
  apiBase: string
  slug: string
  binderNodes: BinderNode[]
  selectedBinder: BinderNode | null
  disabled: boolean
  onOpenBinder: (path: string) => void
}

type DragState = { id: string; dx: number; dy: number }
type ResizeState = { id: string; startX: number; startY: number; startWidth: number; startHeight: number }

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

export default function ProjectBoard({ apiBase, slug, binderNodes, selectedBinder, disabled, onOpenBinder }: Props) {
  const [state, setState] = useState<BoardState>({ schema_version: 1, items: [] })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [linkUrl, setLinkUrl] = useState('')
  const [linkTitle, setLinkTitle] = useState('')
  const [drag, setDrag] = useState<DragState | null>(null)
  const [resize, setResize] = useState<ResizeState | null>(null)
  const [expandedNote, setExpandedNote] = useState<BoardItem | null>(null)
  const [visionModel, setVisionModel] = useState('')
  const [imageDrafts, setImageDrafts] = useState<Record<string, string>>({})
  const [savedNote, setSavedNote] = useState('')
  const dialogRef = useRef<HTMLDialogElement>(null)
  const canvasRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setState({ schema_version: 1, items: [] })
    setError('')
    setDrag(null)
    setResize(null)
    setExpandedNote(null)
    void refresh()
  }, [slug])

  useEffect(() => {
    const dialog = dialogRef.current
    if (expandedNote && dialog && !dialog.open) dialog.showModal()
  }, [expandedNote])

  const sorted = useMemo(() => state.items.filter((item) => !item.parent_note_id).sort((a, b) => a.z - b.z), [state.items])
  const binderById = useMemo(() => new Map(binderNodes.map((node) => [node.id, node])), [binderNodes])
  const topZ = useMemo(() => Math.max(0, ...state.items.map((item) => item.z)), [state.items])

  async function refresh() {
    try {
      setState(await request<BoardState>(`${apiBase}/projects/${slug}/board`))
    } catch (cause) {
      setError((cause as Error).message)
    }
  }

  async function createItem(payload: Record<string, unknown>) {
    setBusy(true)
    setError('')
    try {
      const item = await request<BoardItem>(`${apiBase}/projects/${slug}/board/items`, {
        method: 'POST',
        body: JSON.stringify(payload),
      })
      setState((current) => ({ ...current, items: [...current.items, item] }))
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function patchItem(id: string, patch: Record<string, unknown>) {
    try {
      const item = await request<BoardItem>(`${apiBase}/projects/${slug}/board/items/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(patch),
      })
      setState((current) => ({
        ...current,
        items: current.items.map((entry) => entry.id === id ? { ...entry, ...patch, updated_at: item.updated_at } : entry),
      }))
      return true
    } catch (cause) {
      setError((cause as Error).message)
      return false
    }
  }

  async function removeItem(id: string) {
    try {
      await request(`${apiBase}/projects/${slug}/board/items/${id}`, { method: 'DELETE' })
      setState((current) => ({ ...current, items: current.items.filter((item) => item.id !== id && item.parent_note_id !== id) }))
    } catch (cause) {
      setError((cause as Error).message)
    }
  }

  async function uploadOne(file: File, index: number, noteId = '') {
    const form = new FormData()
    form.append('file', file)
    if (noteId) form.append('parent_note_id', noteId)
    form.append('x', String(140 + ((state.items.length + index) % 6) * 34))
    form.append('y', String(120 + ((state.items.length + index) % 6) * 34))
    const response = await fetch(`${apiBase}/projects/${slug}/board/upload`, { method: 'POST', body: form })
    if (!response.ok) {
      const body = await response.json().catch(() => ({}))
      throw new Error(body.detail || `${response.status} ${response.statusText}`)
    }
    return response.json() as Promise<BoardItem>
  }

  async function upload(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files || [])
    event.target.value = ''
    await uploadFiles(files)
  }

  async function uploadFiles(files: File[], noteId = '') {
    if (!files.length || disabled || busy) return
    setBusy(true)
    setError('')
    try {
      const uploaded: BoardItem[] = []
      for (const [index, file] of files.entries()) uploaded.push(await uploadOne(file, index, noteId))
      setState((current) => ({ ...current, items: [...current.items, ...uploaded] }))
    } catch (cause) {
      setError((cause as Error).message)
      await refresh()
    } finally {
      setBusy(false)
    }
  }

  function bringToFront(item: BoardItem) {
    if (item.z >= topZ) return
    const nextZ = topZ + 1
    setState((current) => ({
      ...current,
      items: current.items.map((entry) => entry.id === item.id ? { ...entry, z: nextZ } : entry),
    }))
    void patchItem(item.id, { z: nextZ })
  }

  function beginDrag(event: PointerEvent<HTMLDivElement>, item: BoardItem) {
    if (disabled || resize || (event.target as HTMLElement).closest('input, textarea, button, a, .board-resize-handle')) return
    const rect = canvasRef.current?.getBoundingClientRect()
    if (!rect) return
    bringToFront(item)
    event.currentTarget.setPointerCapture(event.pointerId)
    setDrag({
      id: item.id,
      dx: event.clientX - rect.left - item.x,
      dy: event.clientY - rect.top - item.y,
    })
  }

  function beginResize(event: PointerEvent<HTMLButtonElement>, item: BoardItem) {
    if (disabled) return
    event.preventDefault()
    event.stopPropagation()
    event.currentTarget.setPointerCapture(event.pointerId)
    bringToFront(item)
    setResize({
      id: item.id,
      startX: event.clientX,
      startY: event.clientY,
      startWidth: item.width,
      startHeight: item.height,
    })
  }

  function movePointer(event: PointerEvent<HTMLDivElement>) {
    if (drag) {
      const rect = canvasRef.current?.getBoundingClientRect()
      if (!rect) return
      const x = Math.max(0, event.clientX - rect.left - drag.dx)
      const y = Math.max(0, event.clientY - rect.top - drag.dy)
      setState((current) => ({
        ...current,
        items: current.items.map((item) => item.id === drag.id ? { ...item, x, y } : item),
      }))
      return
    }
    if (resize) {
      const width = Math.max(120, Math.min(1200, resize.startWidth + event.clientX - resize.startX))
      const height = Math.max(80, Math.min(1000, resize.startHeight + event.clientY - resize.startY))
      setState((current) => ({
        ...current,
        items: current.items.map((item) => item.id === resize.id ? { ...item, width, height } : item),
      }))
    }
  }

  function endPointer() {
    if (drag) {
      const item = state.items.find((entry) => entry.id === drag.id)
      setDrag(null)
      if (item) void patchItem(item.id, { x: item.x, y: item.y })
    }
    if (resize) {
      const item = state.items.find((entry) => entry.id === resize.id)
      setResize(null)
      if (item) void patchItem(item.id, { width: item.width, height: item.height })
    }
  }

  function addSticky() {
    void createItem({
      kind: 'sticky',
      title: 'New note',
      body: '',
      x: 100 + (state.items.length % 6) * 30,
      y: 100 + (state.items.length % 6) * 30,
      width: 260,
      height: 190,
      color: 'amber',
    })
  }

  function pinBinder() {
    if (!selectedBinder) return
    void createItem({
      kind: 'binder',
      title: selectedBinder.title,
      body: selectedBinder.synopsis,
      binder_node_id: selectedBinder.id,
      x: 120 + (state.items.length % 6) * 30,
      y: 120 + (state.items.length % 6) * 30,
      width: 280,
      height: 180,
      color: 'blue',
    })
  }

  function addLink() {
    const url = linkUrl.trim()
    if (!url) return
    void createItem({
      kind: 'link',
      title: linkTitle.trim() || url,
      url,
      x: 140 + (state.items.length % 6) * 30,
      y: 140 + (state.items.length % 6) * 30,
      width: 300,
      height: 140,
      color: 'slate',
    })
    setLinkUrl('')
    setLinkTitle('')
  }

  function assetUrl(item: BoardItem) {
    return `${apiBase}/projects/${slug}/board/asset?path=${encodeURIComponent(item.asset_path)}`
  }

  async function describeImage(item: BoardItem) {
    setBusy(true)
    setError('')
    try {
      const result = await request<{ description: string }>(`${apiBase}/projects/${slug}/board/items/${item.id}/describe`, {
        method: 'POST', body: JSON.stringify({ model: visionModel.trim() }),
      })
      setImageDrafts((drafts) => ({ ...drafts, [item.id]: result.description }))
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  function openNote(item: BoardItem) {
    setError('')
    setSavedNote('')
    setImageDrafts({})
    setExpandedNote(item)
  }

  async function closeNote() {
    if (!disabled && expandedNote) {
      setBusy(true)
      const ok = await patchItem(expandedNote.id, {
        title: expandedNote.title, body: expandedNote.body,
        use_as_inspiration: Boolean(expandedNote.use_as_inspiration),
      })
      setBusy(false)
      if (!ok) return
    }
    dialogRef.current?.close()
    setExpandedNote(null)
  }

  async function saveNote() {
    if (!expandedNote || busy) return
    setBusy(true)
    setError('')
    setSavedNote('')
    try {
      if (await patchItem(expandedNote.id, {
        title: expandedNote.title, body: expandedNote.body,
        use_as_inspiration: Boolean(expandedNote.use_as_inspiration),
      })) setSavedNote('Saved to the corkboard.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="project-board-shell">
      <header className="project-board-toolbar">
        <div>
          <strong>Visual Corkboard</strong>
          <small>{state.items.length} project item{state.items.length === 1 ? '' : 's'} · saved with this manuscript</small>
        </div>
        <div className="project-board-actions">
          <button type="button" onClick={addSticky} disabled={disabled || busy}>+ Sticky</button>
          <button type="button" onClick={pinBinder} disabled={disabled || busy || !selectedBinder}>Pin selected scene</button>
          <label className="board-upload-button">
            {busy ? 'Uploading…' : 'Upload images/files'}
            <input type="file" multiple onChange={(event) => void upload(event)} disabled={disabled || busy} />
          </label>
        </div>
      </header>

      <div className="board-link-row">
        <input value={linkTitle} onChange={(event) => setLinkTitle(event.target.value)} placeholder="Reference title" />
        <input value={linkUrl} onChange={(event) => setLinkUrl(event.target.value)} placeholder="https://…" />
        <button type="button" onClick={addLink} disabled={disabled || busy || !linkUrl.trim()}>Add link</button>
      </div>

      <div
        ref={canvasRef}
        className="project-board-canvas"
        onPointerMove={movePointer}
        onPointerUp={endPointer}
        onPointerCancel={endPointer}
      >
        {sorted.map((item) => {
          const binder = item.binder_node_id ? binderById.get(item.binder_node_id) : null
          return (
            <div
              key={item.id}
              className={`board-item board-${item.kind} board-color-${item.color}${item.kind === 'binder' && !binder ? ' board-stale' : ''}`}
              style={{ left: item.x, top: item.y, width: item.width, height: item.height, zIndex: item.z }}
              onPointerDown={(event) => beginDrag(event, item)}
              onDoubleClick={() => {
                if (item.kind === 'sticky') openNote(item)
                if (item.kind === 'binder' && binder?.path && !binder.custom_metadata.source_missing) onOpenBinder(binder.path)
              }}
            >
              <div className="board-item-head">
                <span>{item.kind === 'sticky' ? '✎' : item.kind === 'image' ? '▧' : item.kind === 'attachment' ? '▤' : item.kind === 'link' ? '↗' : '▦'}</span>
                <input
                  key={item.title}
                  defaultValue={item.title}
                  onFocus={() => bringToFront(item)}
                  onBlur={(event) => { if (event.target.value !== item.title) void patchItem(item.id, { title: event.target.value }) }}
                  aria-label="Board item title"
                />
                {item.kind === 'sticky' && <button type="button" onClick={() => openNote(item)} aria-label="Expand note" title="Expand note">⤢</button>}
                <button type="button" onClick={() => void removeItem(item.id)} aria-label="Remove from board">×</button>
              </div>

              {item.kind === 'image' && item.asset_path && (
                <img src={assetUrl(item)} alt={item.title || item.original_filename} draggable={false} />
              )}
              {item.kind === 'attachment' && item.asset_path && (
                <a href={assetUrl(item)} target="_blank" rel="noreferrer">Open {item.original_filename || item.title}</a>
              )}
              {item.kind === 'link' && item.url && (
                <a href={item.url} target="_blank" rel="noreferrer">{item.url}</a>
              )}
              {(item.kind === 'sticky' || item.kind === 'binder') && (
                <textarea
                  key={item.body}
                  defaultValue={item.body}
                  placeholder={item.kind === 'sticky' ? 'Write a thought, question, beat, reminder…' : 'Scene note…'}
                  onFocus={() => bringToFront(item)}
                  onBlur={(event) => { if (event.target.value !== item.body) void patchItem(item.id, { body: event.target.value }) }}
                />
              )}
              {item.kind === 'sticky' && (
                <div className="board-color-row" aria-label="Sticky note color">
                  {['amber', 'blue', 'rose', 'green', 'slate'].map((color) => (
                    <button
                      key={color}
                      type="button"
                      className={`board-color-dot color-${color}${item.color === color ? ' active' : ''}`}
                      aria-label={`Set ${color} color`}
                      onClick={() => void patchItem(item.id, { color })}
                    />
                  ))}
                </div>
              )}
              {item.kind === 'binder' && (
                <small className="board-binder-status">{binder ? `Pinned to ${binder.title}` : 'Pinned Binder item no longer exists'}</small>
              )}
              <button
                type="button"
                className="board-resize-handle"
                aria-label="Resize board item. Use arrow keys to adjust size."
                title="Drag to resize, or use the arrow keys"
                disabled={disabled}
                onKeyDown={(event) => {
                  const steps: Record<string, [number, number]> = {
                    ArrowLeft: [-24, 0], ArrowRight: [24, 0], ArrowUp: [0, -24], ArrowDown: [0, 24],
                  }
                  const step = steps[event.key]
                  if (!step) return
                  event.preventDefault()
                  void patchItem(item.id, {
                    width: Math.max(120, Math.min(1200, item.width + step[0])),
                    height: Math.max(80, Math.min(1000, item.height + step[1])),
                  })
                }}
                onPointerDown={(event) => beginResize(event, item)}
              >
                ◢
              </button>
            </div>
          )
        })}
        {state.items.length === 0 && (
          <div className="project-board-empty">
            <strong>This manuscript’s board is empty.</strong>
            <span>Add sticky notes, pin Binder scenes, upload visual references or files, and arrange them spatially. Everything here belongs only to this project.</span>
          </div>
        )}
      </div>
      {expandedNote && (
        <dialog className="board-note-editor" ref={dialogRef} aria-label="Expanded corkboard note"
          onCancel={(event) => { event.preventDefault(); if (!busy) void closeNote() }}
          onPaste={(event) => {
            const files = Array.from(event.clipboardData.files)
            if (!files.length) return
            event.preventDefault()
            void uploadFiles(files, expandedNote.id)
          }}>
          <header>
            <h2>Corkboard note</h2>
            <button type="button" onClick={() => void closeNote()} disabled={busy}>Close</button>
          </header>
          <div className="board-note-content">
            <label>Title<input value={expandedNote.title} maxLength={500} disabled={disabled || busy}
              onChange={(event) => { setSavedNote(''); setExpandedNote({ ...expandedNote, title: event.target.value }) }} /></label>
            <label>Note<textarea value={expandedNote.body} maxLength={50000} disabled={disabled || busy}
              onChange={(event) => { setSavedNote(''); setExpandedNote({ ...expandedNote, body: event.target.value }) }}
              placeholder="Write ideas, paste URLs, or paste a screenshot here." /></label>
            {[...new Set(expandedNote.body.match(/https?:\/\/[^\s<>"')]+/g) ?? [])].map((url) => (
              <a key={url} href={url} target="_blank" rel="noreferrer">{url}</a>
            ))}
            <label className="board-upload-button">Attach images or files
              <input type="file" multiple disabled={disabled || busy} onChange={(event) => {
                const files = Array.from(event.target.files ?? [])
                event.target.value = ''
                void uploadFiles(files, expandedNote.id)
              }} />
            </label>
            {state.items.some((item) => item.parent_note_id === expandedNote.id && item.kind === 'image') && (
              <label>Local Ollama vision model (optional)
                <input value={visionModel} maxLength={200} disabled={disabled || busy} placeholder="Installed vision model name"
                  onChange={(event) => setVisionModel(event.target.value)} />
              </label>
            )}
            <div className="board-note-attachments">
              {state.items.filter((item) => item.parent_note_id === expandedNote.id).map((item) => (
                <article key={item.id}>
                  {item.kind === 'image' && <img src={assetUrl(item)} alt={item.title} />}
                  <a href={assetUrl(item)} target="_blank" rel="noreferrer">{item.title}</a>
                  {item.kind === 'image' && (
                    <button type="button" disabled={disabled || busy || !visionModel.trim()} onClick={() => void describeImage(item)}>Describe with local AI</button>
                  )}
                  {imageDrafts[item.id] && (
                    <div>
                      <p>{imageDrafts[item.id]}</p>
                      <button type="button" disabled={disabled || busy} onClick={() => {
                        const body = [item.body, imageDrafts[item.id]].filter(Boolean).join('\n\n').slice(0, 50000)
                        void patchItem(item.id, { body }).then((ok) => {
                          if (ok) setImageDrafts((drafts) => ({ ...drafts, [item.id]: '' }))
                        })
                      }}>Add description to reference notes</button>
                    </div>
                  )}
                  <label>What should I remember about this attachment?
                    <textarea key={item.body} defaultValue={item.body} maxLength={50000} disabled={disabled || busy}
                      onBlur={(event) => { if (event.target.value !== item.body) void patchItem(item.id, { body: event.target.value }) }} />
                  </label>
                  <button type="button" disabled={disabled || busy} onClick={() => void removeItem(item.id)}>Remove attachment</button>
                </article>
              ))}
            </div>
          </div>
          <footer>
            <label><input type="checkbox" checked={Boolean(expandedNote.use_as_inspiration)} disabled={disabled || busy}
              onChange={(event) => { setSavedNote(''); setExpandedNote({ ...expandedNote, use_as_inspiration: event.target.checked }) }} />
              Share this note and attachment descriptions with AI as inspiration</label>
            <button type="button" className="primary" onClick={() => void saveNote()} disabled={disabled || busy}>Save note</button>
            <span role="status">{savedNote}</span>
            {error && <span role="alert">{error}</span>}
          </footer>
        </dialog>
      )}
      {error && <small className="panel-error">{error}</small>}
    </section>
  )
}
