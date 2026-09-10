import { useMemo, useState } from 'react'

import ProjectHistoryPanel from './ProjectHistoryPanel'

type Artifact = {
  format: 'docx' | 'epub' | 'pdf'
  filename: string
  relative_path: string
  bytes: number
}

type PublishResult = {
  export_id: string
  title: string
  documents: number
  words: number
  artifacts: Artifact[]
}

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

export default function PublishPanel({ apiBase, slug, projectName, disabled }: Props) {
  const [title, setTitle] = useState(projectName)
  const [author, setAuthor] = useState('')
  const [language, setLanguage] = useState('en')
  const [formats, setFormats] = useState({ epub: true, docx: true, pdf: true })
  const [includeToc, setIncludeToc] = useState(true)
  const [trimWidth, setTrimWidth] = useState(6)
  const [trimHeight, setTrimHeight] = useState(9)
  const [result, setResult] = useState<PublishResult | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const selectedFormats = useMemo(
    () => Object.entries(formats).filter(([, enabled]) => enabled).map(([format]) => format),
    [formats],
  )

  async function publish() {
    if (!title.trim() || selectedFormats.length === 0 || busy) return
    setBusy(true)
    setError('')
    try {
      const output = await request<PublishResult>(`${apiBase}/projects/${slug}/publish`, {
        method: 'POST',
        body: JSON.stringify({
          formats: selectedFormats,
          title: title.trim(),
          author: author.trim(),
          language: language.trim() || 'en',
          include_toc: includeToc,
          trim_width: trimWidth,
          trim_height: trimHeight,
        }),
      })
      setResult(output)
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <ProjectHistoryPanel apiBase={apiBase} slug={slug} disabled={disabled || busy} />
      <details className="authoring-panel">
        <summary>Compile & Publish <small>EPUB · DOCX · PDF</small></summary>
        <div className="authoring-panel-body">
          <label>Book title</label>
          <input value={title} onChange={(event) => setTitle(event.target.value)} disabled={disabled || busy} />
          <label>Author</label>
          <input value={author} onChange={(event) => setAuthor(event.target.value)} placeholder="Author / pen name" disabled={disabled || busy} />
          <div className="publish-grid">
            <label>Language<input value={language} onChange={(event) => setLanguage(event.target.value)} disabled={disabled || busy} /></label>
            <label>Trim width<input type="number" min="4" max="8.5" step="0.125" value={trimWidth} onChange={(event) => setTrimWidth(Number(event.target.value))} disabled={disabled || busy} /></label>
            <label>Trim height<input type="number" min="6" max="11.7" step="0.125" value={trimHeight} onChange={(event) => setTrimHeight(Number(event.target.value))} disabled={disabled || busy} /></label>
          </div>
          <div className="publish-formats">
            {(['epub', 'docx', 'pdf'] as const).map((format) => (
              <label key={format}>
                <input
                  type="checkbox"
                  checked={formats[format]}
                  onChange={(event) => setFormats((current) => ({ ...current, [format]: event.target.checked }))
                  disabled={disabled || busy}
                />
                {format.toUpperCase()}
              </label>
            ))}
            <label><input type="checkbox" checked={includeToc} onChange={(event) => setIncludeToc(event.target.checked)} disabled={disabled || busy} />EPUB TOC</label>
          </div>
          <button type="button" className="primary" onClick={() => void publish()} disabled={disabled || busy || !title.trim() || selectedFormats.length === 0}>
            {busy ? 'Compiling…' : 'Build publishing files'}
          </button>
          <small className="panel-help">Compile uses Binder order and the Compile checkbox. PDF uses the selected print trim size; EPUB is reflowable for ebook distribution; DOCX is suitable for editorial/submission workflows.</small>
          {result && (
            <div className="publish-result">
              <strong>{result.documents} documents · {result.words.toLocaleString()} words</strong>
              {result.artifacts.map((artifact) => (
                <a
                  key={artifact.relative_path}
                  href={`${apiBase}/projects/${slug}/exports/download?path=${encodeURIComponent(artifact.relative_path)}`}
                  download={artifact.filename}
                >
                  Download {artifact.filename} <small>{Math.max(1, Math.round(artifact.bytes / 1024)).toLocaleString()} KB</small>
                </a>
              ))}
            </div>
          )}
          {error && <small className="panel-error">{error}</small>}
        </div>
      </details>
    </>
  )
}
