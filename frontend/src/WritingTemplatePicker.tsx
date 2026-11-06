import { useEffect, useMemo, useRef, useState } from 'react'
import type { WorkspaceProject } from './workspace-types'
import './writing-template-picker.css'

const API = 'http://127.0.0.1:8000/api'
type Entry = { id: string; title: string; group: string; icon: string; description: string; format: string; genre: string }
type Preview = { title: string; format: string; genre: string; content: string; guide: string }
type Props = { open: boolean; project: WorkspaceProject | null; onClose: () => void; onCreated: (path: string) => void }

export default function WritingTemplatePicker({ open, project, onClose, onCreated }: Props) {
  const [templates, setTemplates] = useState<Entry[]>([])
  const [selected, setSelected] = useState('')
  const [title, setTitle] = useState('Untitled work')
  const [newProjectName, setNewProjectName] = useState('')
  const [query, setQuery] = useState('')
  const [preview, setPreview] = useState<Preview | null>(null)
  const [view, setView] = useState<'structure' | 'guide'>('structure')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)
  const dialogRef = useRef<HTMLElement>(null)

  useEffect(() => {
    if (!open) return
    let alive = true
    setError('')
    void fetch(`${API}/writing-templates`)
      .then(async response => {
        if (!response.ok) throw new Error('Writing formats are not available')
        return response.json() as Promise<Entry[]>
      }).then(rows => { if (alive) { setTemplates(rows); setSelected(rows[0]?.id || '') } })
      .catch(cause => { if (alive) setError((cause as Error).message) })
    const timer = window.setTimeout(() => inputRef.current?.focus(), 50)
    return () => { alive = false; window.clearTimeout(timer) }
  }, [open])

  useEffect(() => {
    if (!open) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !busy) { event.preventDefault(); onClose() }
      if (event.key !== 'Tab' || !dialogRef.current) return
      const focusable = Array.from(dialogRef.current.querySelectorAll<HTMLElement>(
        'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href]'
      ))
      if (!focusable.length) return
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault(); last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault(); first.focus()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [open, busy, onClose])

  useEffect(() => {
    if (!open || !selected || !title.trim()) { setPreview(null); return }
    let alive = true
    const timer = window.setTimeout(() => {
      void fetch(`${API}/writing-templates/preview`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ template_id: selected, title }),
      }).then(async response => {
        if (!response.ok) throw new Error('Could not preview writing format')
        return response.json() as Promise<Preview>
      }).then(result => { if (alive) setPreview(result) })
        .catch(() => { if (alive) setPreview(null) })
    }, 140)
    return () => { alive = false; window.clearTimeout(timer) }
  }, [open, selected, title])

  const filtered = useMemo(() => {
    const text = query.toLowerCase()
    return templates.filter(item => [item.title, item.description, item.group, item.genre].some(value => value.toLowerCase().includes(text)))
  }, [templates, query])
  const groups = Array.from(new Set(filtered.map(item => item.group)))
  const chosen = templates.find(row => row.id === selected)

  async function create() {
    if (!selected || !preview || busy || (!project && !newProjectName.trim())) return
    setBusy(true); setError('')
    try {
      let slug = project?.slug || ''
      let createdNewProject = false
      if (!slug) {
        const created = await fetch(`${API}/projects`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: newProjectName.trim(), description: '' }),
        })
        const result = await created.json().catch(() => ({}))
        if (!created.ok || !result.slug) throw new Error(result.detail || 'Could not create your writing project')
        slug = result.slug
        createdNewProject = true
      }
      const response = await fetch(`${API}/projects/${encodeURIComponent(slug)}/writing-templates`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ template_id: selected, title }),
      })
      const result = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(result.detail || 'Could not create your new writing document')
      window.dispatchEvent(new CustomEvent('emberwriter:binder-changed'))
      if (createdNewProject) {
        window.dispatchEvent(new CustomEvent('emberwriter:open-writing-document',
          { detail: { slug, path: result.path } }))
      } else {
        onCreated(result.path)
      }
      onClose()
    } catch (cause) { setError((cause as Error).message) }
    finally { setBusy(false) }
  }

  if (!open) return null
  return <div className="writing-picker-backdrop">
    <section ref={dialogRef} className="writing-picker" role="dialog" aria-modal="true" aria-labelledby="writing-picker-title">
      <header className="writing-picker-header">
        <div><span className="writing-picker-kicker">YOUR NEXT PIECE</span>
          <h2 id="writing-picker-title">What would you like to write?</h2>
          <p>Choose a starting shape. Every template is editable, and nothing touches your existing pages.</p>
        </div>
        <button type="button" onClick={onClose} disabled={busy} aria-label="Close writing templates">✕</button>
      </header>
      <div className="writing-picker-layout">
        <div className="writing-picker-catalog">
          <label className="writing-picker-search">Find a genre or format
            <input ref={inputRef} type="search" value={query} onChange={event => setQuery(event.target.value)}
              placeholder="Horror, sci-fi, screenplay, essay…" />
          </label>
          <div className="writing-picker-cards" role="group" aria-label="Writing formats">
            {groups.map(group => <div key={group}>
              <h3>{group}</h3>
              {filtered.filter(item => item.group === group).map(item => <button type="button" key={item.id}
                className={selected === item.id ? 'writing-picker-card selected' : 'writing-picker-card'}
                aria-pressed={selected === item.id} onClick={() => { setSelected(item.id); setView('structure') }}>
                <span aria-hidden="true">{item.icon}</span>
                <span><strong>{item.title}</strong><small>{item.description}</small></span>
              </button>)}
            </div>)}
            {!filtered.length && <p>No matching formats. Try a broader search.</p>}
          </div>
        </div>
        <div className="writing-picker-detail">
          <span className="writing-picker-kicker">{chosen?.group || 'Writing'} · {chosen?.format?.replaceAll('_', ' ')}</span>
          <h3>{chosen?.title || 'Choose a format'}</h3>
          <p>{chosen?.description}</p>
          {!project && <label className="writing-picker-title">First, name your writing project
            <input value={newProjectName} onChange={event => setNewProjectName(event.target.value)}
              maxLength={120} placeholder="My new writing project" />
            <small>A private local project will be created when you confirm. Your work stays on this computer.</small>
          </label>}
          <label className="writing-picker-title">Document title
            <input value={title} onChange={event => setTitle(event.target.value)} maxLength={160}
              placeholder="Give your work a name" />
          </label>
          <div className="writing-picker-tabs" role="group" aria-label="Template preview">
            <button className={view === 'structure' ? 'selected' : ''} onClick={() => setView('structure')} type="button">Starting page</button>
            <button className={view === 'guide' ? 'selected' : ''} onClick={() => setView('guide')} type="button">Writing guidance</button>
          </div>
          <pre className="writing-picker-preview">{preview ? (view === 'structure' ? preview.content : preview.guide) : 'Enter a title to see your starting page.'}</pre>
          <p className="writing-picker-safety">Creates a new page, plus a separate editable writing guide. Existing writing is never replaced.</p>
          {error && <p className="writing-picker-error" role="alert">{error}</p>}
          <footer>
            <button type="button" onClick={onClose} disabled={busy}>Not now</button>
            <button type="button" className="writing-picker-primary" onClick={() => void create()}
              disabled={!preview || !title.trim() || (!project && !newProjectName.trim()) || busy}>
              {busy ? 'Creating your page…' : 'Create my writing page →'}
            </button>
          </footer>

        </div>
      </div>
    </section>
  </div>
}
