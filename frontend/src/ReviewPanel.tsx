import { useEffect, useMemo, useState } from 'react'

import './review.css'

export type ReviewAnnotation = {
  id: string
  path: string
  anchor_text: string
  comment: string
  kind: 'comment' | 'question' | 'issue' | 'todo' | 'praise'
  status: 'open' | 'resolved' | 'dismissed'
  author: string
  source_hash: string
  source_start: number
  source_end: number
  current_start: number | null
  current_end: number | null
  stale: boolean
  reanchored: boolean
  created_at: string
  updated_at: string
  resolved_at: string | null
}

type Props = {
  apiBase: string
  slug: string
  activePath: string
  disabled: boolean
  refreshToken: number
  getSelectedText: () => string
  onOpen: (annotation: ReviewAnnotation) => void
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
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export default function ReviewPanel({
  apiBase,
  slug,
  activePath,
  disabled,
  refreshToken,
  getSelectedText,
  onOpen,
}: Props) {
  const [annotations, setAnnotations] = useState<ReviewAnnotation[]>([])
  const [kind, setKind] = useState<ReviewAnnotation['kind']>('comment')
  const [comment, setComment] = useState('')
  const [author, setAuthor] = useState(() => localStorage.getItem('emberwriter.reviewAuthor') || '')
  const [includeResolved, setIncludeResolved] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function refresh() {
    if (!activePath) {
      setAnnotations([])
      return
    }
    const params = new URLSearchParams({
      path: activePath,
      include_resolved: String(includeResolved),
    })
    setAnnotations(
      await request<ReviewAnnotation[]>(
        `${apiBase}/projects/${slug}/review/annotations?${params.toString()}`,
      ),
    )
  }

  useEffect(() => {
    setError('')
    void refresh().catch((cause) => setError((cause as Error).message))
  }, [apiBase, slug, activePath, includeResolved, refreshToken])

  useEffect(() => {
    localStorage.setItem('emberwriter.reviewAuthor', author)
  }, [author])

  const openCount = useMemo(
    () => annotations.filter((annotation) => annotation.status === 'open').length,
    [annotations],
  )

  async function add() {
    const anchor = getSelectedText().trim()
    if (!anchor || !comment.trim() || !activePath || busy) return
    setBusy(true)
    setError('')
    try {
      await request<ReviewAnnotation>(`${apiBase}/projects/${slug}/review/annotations`, {
        method: 'POST',
        body: JSON.stringify({
          path: activePath,
          anchor_text: anchor,
          comment: comment.trim(),
          kind,
          author: author.trim(),
        }),
      })
      setComment('')
      await refresh()
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function update(annotation: ReviewAnnotation, patch: Partial<Pick<ReviewAnnotation, 'status' | 'comment' | 'kind'>>) {
    if (busy) return
    setBusy(true)
    setError('')
    try {
      await request<ReviewAnnotation>(`${apiBase}/projects/${slug}/review/annotations/${annotation.id}`, {
        method: 'PATCH',
        body: JSON.stringify(patch),
      })
      await refresh()
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function remove(annotation: ReviewAnnotation) {
    if (busy) return
    setBusy(true)
    setError('')
    try {
      await request<void>(`${apiBase}/projects/${slug}/review/annotations/${annotation.id}`, {
        method: 'DELETE',
      })
      await refresh()
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <details className="authoring-panel review-panel" open={openCount > 0}>
      <summary>
        Review Comments <small>{openCount} open · source anchored</small>
      </summary>
      <div className="authoring-panel-body review-body">
        <div className="review-compose">
          <div className="review-compose-row">
            <select value={kind} onChange={(event) => setKind(event.target.value as ReviewAnnotation['kind'])} disabled={disabled || busy}>
              <option value="comment">Comment</option>
              <option value="question">Question</option>
              <option value="issue">Issue</option>
              <option value="todo">To-do</option>
              <option value="praise">Praise</option>
            </select>
            <input value={author} onChange={(event) => setAuthor(event.target.value)} placeholder="Reviewer name" disabled={disabled || busy} />
          </div>
          <textarea value={comment} onChange={(event) => setComment(event.target.value)} rows={3} placeholder="Select manuscript text, then leave a comment…" disabled={disabled || busy} />
          <button type="button" className="primary" onClick={() => void add()} disabled={disabled || busy || !comment.trim()}>
            Add comment to current selection
          </button>
          <small className="panel-help">Comments are stored in readable project JSON. Save the document before commenting so the selected passage can be anchored to the source.</small>
        </div>

        <label className="review-toggle">
          <input type="checkbox" checked={includeResolved} onChange={(event) => setIncludeResolved(event.target.checked)} />
          Show resolved / dismissed
        </label>

        <div className="review-list">
          {annotations.length === 0 && <small>No review comments for this document.</small>}
          {annotations.map((annotation) => (
            <article className={`review-card status-${annotation.status} ${annotation.stale ? 'stale' : ''}`} key={annotation.id}>
              <header>
                <span className={`review-kind kind-${annotation.kind}`}>{annotation.kind}</span>
                <span>{annotation.author || 'Reviewer'}</span>
                {annotation.reanchored && <b>re-anchored</b>}
                {annotation.stale && <b>stale</b>}
              </header>
              <button type="button" className="review-anchor" onClick={() => onOpen(annotation)} disabled={disabled}>
                “{annotation.anchor_text.length > 180 ? `${annotation.anchor_text.slice(0, 180)}…` : annotation.anchor_text}”
              </button>
              <p>{annotation.comment}</p>
              <footer>
                {annotation.status !== 'resolved' && <button type="button" onClick={() => void update(annotation, { status: 'resolved' })} disabled={busy}>Resolve</button>}
                {annotation.status !== 'open' && <button type="button" onClick={() => void update(annotation, { status: 'open' })} disabled={busy}>Reopen</button>}
                {annotation.status === 'open' && <button type="button" onClick={() => void update(annotation, { status: 'dismissed' })} disabled={busy}>Dismiss</button>}
                <button type="button" onClick={() => void remove(annotation)} disabled={busy}>Delete</button>
              </footer>
            </article>
          ))}
        </div>
        {error && <small className="panel-error">{error}</small>}
      </div>
    </details>
  )
}
