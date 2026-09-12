import { useEffect, useMemo, useState } from 'react'
import './preview-studio.css'

type PreviewMode = 'phone' | 'tablet' | 'kindle' | 'print'

type PreviewDocument = {
  title: string
  path: string
  word_count: number
  html: string
}

type PreviewPayload = {
  title: string
  author: string
  trim_width: number
  trim_height: number
  documents: PreviewDocument[]
  words: number
}

type PreviewArtifact = {
  filename: string
  relative_path: string
  bytes: number
  documents: number
  words: number
}

type ValidationIssue = {
  level: 'error' | 'warning' | 'info'
  code: string
  message: string
  retailer: string | null
}

type Validation = {
  valid: boolean
  issues: ValidationIssue[]
}

type ReleaseProfile = Record<string, unknown>

type Props = {
  apiBase: string
  slug: string
  projectName: string
  disabled: boolean
}

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

const modes: Array<{ id: PreviewMode; label: string; note: string }> = [
  { id: 'phone', label: 'iPhone / phone', note: 'narrow reflow' },
  { id: 'tablet', label: 'iPad / tablet', note: 'wide reflow' },
  { id: 'kindle', label: 'Kindle-style', note: 'e-ink reading width' },
  { id: 'print', label: 'Print', note: 'trim-page simulation' },
]

export default function PreviewStudioPanel({ apiBase, slug, projectName, disabled }: Props) {
  const [title, setTitle] = useState(projectName)
  const [author, setAuthor] = useState('')
  const [trimWidth, setTrimWidth] = useState(6)
  const [trimHeight, setTrimHeight] = useState(9)
  const [mode, setMode] = useState<PreviewMode>('kindle')
  const [preview, setPreview] = useState<PreviewPayload | null>(null)
  const [chapterIndex, setChapterIndex] = useState(0)
  const [artifact, setArtifact] = useState<PreviewArtifact | null>(null)
  const [kdpValidation, setKdpValidation] = useState<Validation | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const current = preview?.documents[chapterIndex] || preview?.documents[0] || null
  const kdpIssues = useMemo(
    () => kdpValidation?.issues.filter((issue) => !issue.retailer || issue.retailer === 'kdp') || [],
    [kdpValidation],
  )
  const kdpErrors = kdpIssues.filter((issue) => issue.level === 'error')
  const kdpWarnings = kdpIssues.filter((issue) => issue.level === 'warning')

  async function buildPreview() {
    if (busy || !title.trim()) return
    setBusy(true)
    setError('')
    try {
      const next = await request<PreviewPayload>(`${apiBase}/projects/${slug}/preview`, {
        method: 'POST',
        body: JSON.stringify({ title: title.trim(), author: author.trim(), trim_width: trimWidth, trim_height: trimHeight }),
      })
      setPreview(next)
      setChapterIndex((index) => Math.min(index, Math.max(0, next.documents.length - 1)))
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function refreshKdp() {
    setError('')
    try {
      const profile = await request<ReleaseProfile>(`${apiBase}/projects/${slug}/distribution/profile`)
      const validation = await request<Validation>(`${apiBase}/projects/${slug}/distribution/validate`, {
        method: 'POST',
        body: JSON.stringify(profile),
      })
      setKdpValidation(validation)
    } catch (cause) {
      setError((cause as Error).message)
    }
  }

  async function buildSite() {
    if (busy || !title.trim()) return
    setBusy(true)
    setError('')
    try {
      const next = await request<PreviewArtifact>(`${apiBase}/projects/${slug}/preview/site`, {
        method: 'POST',
        body: JSON.stringify({ title: title.trim(), author: author.trim(), trim_width: trimWidth, trim_height: trimHeight }),
      })
      setArtifact(next)
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    void buildPreview()
    void refreshKdp()
  }, [slug])

  const frameStyle = mode === 'print'
    ? ({ '--preview-ratio': `${trimWidth} / ${trimHeight}` } as React.CSSProperties)
    : undefined

  return (
    <details className="authoring-panel preview-studio" open>
      <summary>
        Preview Studio <small>phone · tablet · Kindle · print · private site</small>
      </summary>
      <div className="authoring-panel-body preview-studio-body">
        <div className="preview-top-grid">
          <label>Book title<input value={title} onChange={(event) => setTitle(event.target.value)} disabled={disabled || busy} /></label>
          <label>Author<input value={author} onChange={(event) => setAuthor(event.target.value)} placeholder="Author / pen name" disabled={disabled || busy} /></label>
          <label>Print trim<input value={`${trimWidth} × ${trimHeight} in`} readOnly /></label>
        </div>

        <div className="preview-mode-row">
          {modes.map((item) => (
            <button key={item.id} type="button" className={mode === item.id ? 'active' : ''} onClick={() => setMode(item.id)}>
              <strong>{item.label}</strong><small>{item.note}</small>
            </button>
          ))}
          <button type="button" className="preview-refresh" onClick={() => void buildPreview()} disabled={disabled || busy}>Refresh preview</button>
        </div>

        <div className="preview-workbench">
          <aside>
            <strong>{preview?.documents.length || 0} compiled sections</strong>
            <small>{(preview?.words || 0).toLocaleString()} words · Binder compile order</small>
            <div className="preview-chapters">
              {preview?.documents.map((document, index) => (
                <button key={document.path} type="button" className={chapterIndex === index ? 'active' : ''} onClick={() => setChapterIndex(index)}>
                  <span>{document.title}</span><small>{document.word_count.toLocaleString()}</small>
                </button>
              ))}
            </div>
          </aside>

          <div className={`preview-device preview-device-${mode}`} style={frameStyle}>
            <div className="preview-device-bar"><span>{mode === 'print' ? `${trimWidth} × ${trimHeight} print page` : modes.find((item) => item.id === mode)?.label}</span></div>
            <div className="preview-page">
              <h1>{current?.title || 'No compiled chapter'}</h1>
              {current && <article dangerouslySetInnerHTML={{ __html: current.html }} />}
            </div>
          </div>
        </div>

        <div className={`kdp-readiness ${kdpErrors.length ? 'blocked' : kdpWarnings.length ? 'warning' : 'ready'}`}>
          <div>
            <small>AMAZON KDP READINESS</small>
            <strong>{kdpErrors.length ? `${kdpErrors.length} blocker${kdpErrors.length === 1 ? '' : 's'}` : kdpWarnings.length ? `Ready with ${kdpWarnings.length} warning${kdpWarnings.length === 1 ? '' : 's'}` : 'Ready'}</strong>
            <span>Uses the same retailer validation as Release &amp; Distribution.</span>
          </div>
          <button type="button" onClick={() => void refreshKdp()} disabled={disabled || busy}>Recheck KDP</button>
          {kdpIssues.length > 0 && <div className="kdp-issues">{kdpIssues.slice(0, 8).map((issue) => <p key={`${issue.code}-${issue.message}`} className={issue.level}><b>{issue.level}</b>{issue.message}</p>)}</div>}
        </div>

        <div className="private-preview-builder">
          <div><strong>Private preview site package</strong><p>Build a clean standalone browser reader for beta readers or family. Host it behind authentication for confidential remote sharing.</p></div>
          <button type="button" className="primary" onClick={() => void buildSite()} disabled={disabled || busy || !title.trim()}>{busy ? 'Building…' : 'Build preview site ZIP'}</button>
          {artifact && <a href={`${apiBase}/projects/${slug}/exports/download?path=${encodeURIComponent(artifact.relative_path)}`} download={artifact.filename}>Download {artifact.filename}</a>}
        </div>

        {error && <small className="panel-error">{error}</small>}
      </div>
    </details>
  )
}
