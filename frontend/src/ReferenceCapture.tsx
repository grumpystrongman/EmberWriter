import { useEffect, useRef, useState } from 'react'
import type { WorkspaceProject } from './workspace-types'
import './reference-capture.css'

type Props = { project: WorkspaceProject | null; open: boolean; onClose: () => void }
const API = 'http://127.0.0.1:8000/api'
const validTypes = ['image/png', 'image/jpeg', 'image/webp']

function slug(value: string) {
  return value.toLowerCase().trim().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 60) || 'inspiration'
}
export default function ReferenceCapture({ project, open, onClose }: Props) {
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState('')
  const [title, setTitle] = useState('')
  const [note, setNote] = useState('')
  const [sourceUrl, setSourceUrl] = useState('')
  const [kind, setKind] = useState('scene')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const pasteRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!file) { setPreview(''); return }
    const url = URL.createObjectURL(file)
    setPreview(url)
    return () => URL.revokeObjectURL(url)
  }, [file])
  useEffect(() => {
    if (!open) return
    const timer = window.setTimeout(() => pasteRef.current?.focus(), 0)
    const escape = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !busy) { event.stopPropagation(); onClose() }
    }
    window.addEventListener('keydown', escape, true)
    return () => { window.clearTimeout(timer); window.removeEventListener('keydown', escape, true) }
  }, [open, busy, onClose])
  useEffect(() => {
    if (!open) { setFile(null); setPreview(''); setError(''); setTitle(''); setNote(''); setSourceUrl('') }
  }, [open])

  function selectFile(image: File | undefined) {
    if (!image) return
    if (!validTypes.includes(image.type)) { setError('Use a PNG, JPEG, or WebP picture.'); return }
    if (image.size > 20 * 1024 * 1024) { setError('Images must be smaller than 20 MB.'); return }
    setError('')
    setFile(image)
    if (!title) setTitle(image.name.replace(/\.[^.]+$/, ''))
  }
  async function save() {
    if (!file || !project || busy) return
    if (sourceUrl.trim() && !/^https?:\/\//i.test(sourceUrl.trim())) {
      setError('The source link must start with https:// or http://')
      return
    }
    setBusy(true); setError('')
    try {
      const assetId = slug(title || file.name) + '-' + crypto.randomUUID().slice(0, 8)
      const params = new URLSearchParams({ title: title.trim() || file.name, kind })
      if (sourceUrl.trim()) params.set('source_url', sourceUrl.trim())
      const data = new FormData()
      data.append('image', file)
      const root = `${API}/projects/${encodeURIComponent(project.slug)}/visual-assets/${assetId}`
      const uploaded = await fetch(root + '/upload?' + params.toString(), { method: 'POST', body: data })
      if (!uploaded.ok) {
        const detail = await uploaded.json().catch(() => ({}))
        throw new Error(detail.detail || 'Could not save the reference image')
      }
      if (note.trim() || project.activePath) {
        const metadata = await fetch(root + '/metadata', {
          method: 'PUT', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            notes: note.trim(),
            linked_entities: project.activePath ? [`Chapter: ${project.activePath}`] : [],
          }),
        })
        if (!metadata.ok) throw new Error('Picture saved, but its story notes could not be added. You can edit them in World → Visual Studio.')
      }
      window.dispatchEvent(new CustomEvent('emberwriter:visuals-changed'))
      onClose()
    } catch (cause) { setError((cause as Error).message) }
    finally { setBusy(false) }
  }
  if (!open) return null
  return <div className="reference-capture-backdrop" role="presentation">
    <section className="reference-capture" role="dialog" aria-modal="true" aria-labelledby="reference-capture-title">
      <header><div><h2 id="reference-capture-title">Keep this inspiration</h2><p>Capture an image without leaving your story. It stays a reference until you choose otherwise.</p></div>
        <button type="button" aria-label="Close picture reference" disabled={busy} onClick={onClose}>✕</button></header>
      {!project && <p role="alert">Open a story project to save references.</p>}
      <div className="reference-capture-drop" ref={pasteRef} tabIndex={0} role="group" aria-label="Paste or drop an image here"
        onPaste={event => {
          const image = Array.from(event.clipboardData.files).find(item => item.type.startsWith('image/'))
          if (image) { event.preventDefault(); selectFile(image) }
        }}
        onDragOver={event => event.preventDefault()}
        onDrop={event => { event.preventDefault(); selectFile(Array.from(event.dataTransfer.files).find(item => item.type.startsWith('image/'))) }}>
        {preview ? <img src={preview} alt="Preview of image being saved as inspiration" /> :
          <p>Copy an image online, click here, then press <b>Ctrl+V</b> — or drop an image.</p>}
        <label>Choose a file<input type="file" accept="image/png,image/jpeg,image/webp" disabled={busy} onChange={event => { selectFile(event.target.files?.[0]); event.target.value = '' }} /></label>
      </div>
      <div className="reference-capture-fields">
        <label>What should we call it?<input value={title} onChange={event => setTitle(event.target.value)} maxLength={240} placeholder="The fortress at dawn" /></label>
        <label>Reference for<select value={kind} onChange={event => setKind(event.target.value)}>
          <option value="scene">Scene</option><option value="character">Character</option>
          <option value="location">Location</option><option value="object">Object</option>
          <option value="reference">Mood / inspiration</option>
        </select></label>
        <label>What matters about this picture?<textarea value={note} maxLength={4000} onChange={event => setNote(event.target.value)}
          placeholder="Use its light and atmosphere, but not the characters or clothing." /></label>
        <label>Where did you find it? (optional)<input type="url" value={sourceUrl} maxLength={2000} onChange={event => setSourceUrl(event.target.value)}
          placeholder="https://…" /></label>
      </div>
      {project?.activePath && <p className="reference-capture-linked">Connected to the open chapter: {project.activePath}</p>}
      {error && <p role="alert" className="reference-capture-error">{error}</p>}
      <footer><button type="button" disabled={busy} onClick={onClose}>Cancel</button>
        <button type="button" disabled={busy || !project || !file} onClick={() => void save()}>
          {busy ? 'Saving reference…' : 'Save inspiration'}</button></footer>
      <small>You own the decisions. Saving an image does not insert it into prose, grant publication rights, or establish new story canon.</small>
    </section>
  </div>
}
