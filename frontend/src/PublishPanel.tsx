import { useMemo, useState } from 'react'

import CoverStudioPanel from './CoverStudioPanel'
import DistributionPanel from './DistributionPanel'
import ProjectHistoryPanel from './ProjectHistoryPanel'
import SubmissionPanel from './SubmissionPanel'

type PublishFormat = 'docx' | 'epub' | 'pdf'

type Artifact = {
  format: PublishFormat
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
  const [formats, setFormats] = useState<Record<PublishFormat, boolean>>({
    epub: true,
    docx: true,
    pdf: true,
  })
  const [includeToc, setIncludeToc] = useState(true)
  const [trimWidth, setTrimWidth] = useState(6)
  const [trimHeight, setTrimHeight] = useState(9)
  const [result, setResult] = useState<PublishResult | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const selectedFormats = useMemo<PublishFormat[]>(
    () =>
      (Object.entries(formats) as [PublishFormat, boolean][])
        .filter(([, enabled]) => enabled)
        .map(([format]) => format),
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

  function setFormat(format: PublishFormat, enabled: boolean) {
    setFormats((current) => ({ ...current, [format]: enabled }))
  }

  return (
    <>
      <ProjectHistoryPanel apiBase={apiBase} slug={slug} disabled={disabled || busy} />
      <CoverStudioPanel apiBase={apiBase} slug={slug} projectName={projectName} disabled={disabled || busy} />

      <details className="authoring-panel">
        <summary>
          Interior Compile &amp; Publish <small>EPUB · DOCX · PDF</small>
        </summary>

        <div className="authoring-panel-body">
          <label htmlFor="publish-title">Book title</label>
          <input
            id="publish-title"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            disabled={disabled || busy}
          />

          <label htmlFor="publish-author">Author</label>
          <input
            id="publish-author"
            value={author}
            onChange={(event) => setAuthor(event.target.value)}
            placeholder="Author / pen name"
            disabled={disabled || busy}
          />

          <div className="publish-grid">
            <label htmlFor="publish-language">
              Language
              <input
                id="publish-language"
                value={language}
                onChange={(event) => setLanguage(event.target.value)}
                disabled={disabled || busy}
              />
            </label>
            <label htmlFor="publish-trim-width">
              Trim width
              <input
                id="publish-trim-width"
                type="number"
                min="4"
                max="8.5"
                step="0.125"
                value={trimWidth}
                onChange={(event) => setTrimWidth(Number(event.target.value))}
                disabled={disabled || busy}
              />
            </label>
            <label htmlFor="publish-trim-height">
              Trim height
              <input
                id="publish-trim-height"
                type="number"
                min="6"
                max="11.7"
                step="0.125"
                value={trimHeight}
                onChange={(event) => setTrimHeight(Number(event.target.value))}
                disabled={disabled || busy}
              />
            </label>
          </div>

          <div className="publish-formats">
            {(['epub', 'docx', 'pdf'] as PublishFormat[]).map((format) => (
              <label key={format}>
                <input
                  type="checkbox"
                  checked={formats[format]}
                  onChange={(event) => setFormat(format, event.target.checked)}
                  disabled={disabled || busy}
                />
                {format.toUpperCase()}
              </label>
            ))}
            <label>
              <input
                type="checkbox"
                checked={includeToc}
                onChange={(event) => setIncludeToc(event.target.checked)}
                disabled={disabled || busy}
              />
              EPUB TOC
            </label>
          </div>

          <button
            type="button"
            className="primary"
            onClick={() => void publish()}
            disabled={disabled || busy || !title.trim() || selectedFormats.length === 0}
          >
            {busy ? 'Compiling…' : 'Build interior publishing files'}
          </button>

          <small className="panel-help">
            Interior compile uses Binder order and the Compile checkbox. PDF uses the selected print trim
            size; EPUB is reflowable for ebook distribution; DOCX is suitable for editorial and
            submission workflows. Cover Studio above builds the separate print-wrap or eBook cover asset.
          </small>

          {result && (
            <div className="publish-result">
              <strong>
                {result.documents} documents · {result.words.toLocaleString()} words
              </strong>
              {result.artifacts.map((artifact) => {
                const downloadUrl = `${apiBase}/projects/${slug}/exports/download?path=${encodeURIComponent(artifact.relative_path)}`
                return (
                  <a key={artifact.relative_path} href={downloadUrl} download={artifact.filename}>
                    Download {artifact.filename}{' '}
                    <small>
                      {Math.max(1, Math.round(artifact.bytes / 1024)).toLocaleString()} KB
                    </small>
                  </a>
                )
              })}
            </div>
          )}

          {error && <small className="panel-error">{error}</small>}
        </div>
      </details>

      <SubmissionPanel apiBase={apiBase} slug={slug} disabled={disabled || busy} />
      <DistributionPanel apiBase={apiBase} slug={slug} projectName={projectName} disabled={disabled || busy} />
    </>
  )
}
