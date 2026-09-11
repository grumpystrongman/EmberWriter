import { useEffect, useMemo, useState } from 'react'

import './sprint.css'

type Sprint = {
  id: string
  path: string
  started_at: string
  ended_at: string | null
  start_words: number
  end_words: number | null
  target_words: number
  duration_minutes: number
  elapsed_seconds: number
  status: 'active' | 'completed' | 'cancelled'
  net_words: number | null
  words_per_minute: number | null
}

type Props = {
  apiBase: string
  slug: string
  path: string
  wordCount: number
  disabled?: boolean
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

function clock(seconds: number) {
  const safe = Math.max(0, Math.floor(seconds))
  const minutes = Math.floor(safe / 60)
  const rest = safe % 60
  return `${minutes}:${String(rest).padStart(2, '0')}`
}

function sameLocalDay(value: string, date = new Date()) {
  const parsed = new Date(value)
  return !Number.isNaN(parsed.getTime()) && parsed.toDateString() === date.toDateString()
}

export default function SprintPanel({ apiBase, slug, path, wordCount, disabled = false }: Props) {
  const [active, setActive] = useState<Sprint | null>(null)
  const [history, setHistory] = useState<Sprint[]>([])
  const [duration, setDuration] = useState(() => Number(localStorage.getItem('emberwriter.sprintDuration') || 25))
  const [target, setTarget] = useState(() => Number(localStorage.getItem('emberwriter.sprintTarget') || 500))
  const [focusOnStart, setFocusOnStart] = useState(() => localStorage.getItem('emberwriter.sprintFocus') !== 'false')
  const [now, setNow] = useState(Date.now())
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function refresh() {
    if (!slug) return
    try {
      const [current, recent] = await Promise.all([
        request<Sprint | null>(`${apiBase}/projects/${slug}/sprints/active`),
        request<Sprint[]>(`${apiBase}/projects/${slug}/sprints?limit=30`),
      ])
      setActive(current)
      setHistory(recent)
    } catch (cause) {
      setError((cause as Error).message)
    }
  }

  useEffect(() => { void refresh() }, [apiBase, slug])

  useEffect(() => {
    localStorage.setItem('emberwriter.sprintDuration', String(duration))
    localStorage.setItem('emberwriter.sprintTarget', String(target))
    localStorage.setItem('emberwriter.sprintFocus', String(focusOnStart))
  }, [duration, target, focusOnStart])

  useEffect(() => {
    if (!active) return
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [active?.id])

  const elapsed = active ? Math.max(0, Math.floor((now - new Date(active.started_at).getTime()) / 1000)) : 0
  const remaining = active ? Math.max(0, active.duration_minutes * 60 - elapsed) : 0
  const sameDocument = Boolean(active && active.path === path)
  const liveNet = active && sameDocument ? wordCount - active.start_words : 0
  const liveWpm = active && elapsed > 0 && sameDocument ? Math.max(0, liveNet) / Math.max(elapsed / 60, 1 / 60) : 0
  const goalProgress = active ? Math.max(0, Math.min(100, (Math.max(0, liveNet) / active.target_words) * 100)) : 0
  const timeProgress = active ? Math.max(0, Math.min(100, (elapsed / (active.duration_minutes * 60)) * 100)) : 0

  const today = useMemo(() => history.filter((item) => sameLocalDay(item.started_at)), [history])
  const todayWords = today.reduce((sum, item) => sum + Math.max(0, item.net_words || 0), 0)
  const bestWpm = history.reduce((best, item) => Math.max(best, item.words_per_minute || 0), 0)

  async function start() {
    if (!slug || !path || disabled || busy) return
    setBusy(true)
    setError('')
    try {
      const sprint = await request<Sprint>(`${apiBase}/projects/${slug}/sprints`, {
        method: 'POST',
        body: JSON.stringify({
          path,
          start_words: wordCount,
          target_words: Math.max(1, target),
          duration_minutes: Math.max(1, duration),
        }),
      })
      setActive(sprint)
      setNow(Date.now())
      await refresh()
      if (focusOnStart) window.dispatchEvent(new CustomEvent('emberwriter:focus-mode', { detail: true }))
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function finish(status: 'completed' | 'cancelled') {
    if (!active || busy) return
    setBusy(true)
    setError('')
    try {
      await request<Sprint>(`${apiBase}/projects/${slug}/sprints/${active.id}`, {
        method: 'PUT',
        body: JSON.stringify({
          end_words: sameDocument ? wordCount : active.start_words,
          status,
        }),
      })
      setActive(null)
      await refresh()
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    if (!active || remaining > 0 || busy || !sameDocument) return
    void finish('completed')
  }, [active?.id, remaining, sameDocument])

  return (
    <details className={`sprint-panel ${active ? 'active' : ''}`} open={Boolean(active)}>
      <summary>
        <span>⏱ Writing Sprint</span>
        {active ? (
          <strong>{clock(remaining)} · {liveNet >= 0 ? '+' : ''}{liveNet} words · {liveWpm.toFixed(1)} WPM</strong>
        ) : (
          <small>{duration} min · {target} word goal · today +{todayWords}</small>
        )}
      </summary>
      <div className="sprint-body">
        {active ? (
          <>
            {!sameDocument && <div className="sprint-warning">This sprint started in {active.path}. Return to that document to track live word gain accurately.</div>}
            <div className="sprint-stats">
              <span><b>{clock(remaining)}</b><small>remaining</small></span>
              <span><b>{liveNet >= 0 ? '+' : ''}{liveNet}</b><small>net words</small></span>
              <span><b>{liveWpm.toFixed(1)}</b><small>WPM</small></span>
              <span><b>{active.target_words}</b><small>goal</small></span>
            </div>
            <div className="sprint-progress-label"><span>Word goal</span><span>{Math.round(goalProgress)}%</span></div>
            <div className="sprint-progress"><i style={{ width: `${goalProgress}%` }} /></div>
            <div className="sprint-progress-label"><span>Time</span><span>{Math.round(timeProgress)}%</span></div>
            <div className="sprint-progress time"><i style={{ width: `${timeProgress}%` }} /></div>
            <div className="sprint-actions">
              <button type="button" className="primary" onClick={() => void finish('completed')} disabled={busy || !sameDocument}>Finish sprint</button>
              <button type="button" onClick={() => void finish('cancelled')} disabled={busy}>Cancel</button>
              <button type="button" onClick={() => window.dispatchEvent(new CustomEvent('emberwriter:focus-mode', { detail: true }))}>Focus</button>
            </div>
          </>
        ) : (
          <>
            <div className="sprint-presets">
              {[10, 25, 45, 60].map((minutes) => (
                <button key={minutes} type="button" className={duration === minutes ? 'active' : ''} onClick={() => setDuration(minutes)}>{minutes}m</button>
              ))}
            </div>
            <div className="sprint-config">
              <label>Minutes<input type="number" min="1" max="480" value={duration} onChange={(event) => setDuration(Number(event.target.value))} /></label>
              <label>Word goal<input type="number" min="1" max="100000" value={target} onChange={(event) => setTarget(Number(event.target.value))} /></label>
              <label className="sprint-focus"><input type="checkbox" checked={focusOnStart} onChange={(event) => setFocusOnStart(event.target.checked)} /> Enter Focus mode</label>
            </div>
            <button type="button" className="primary" onClick={() => void start()} disabled={disabled || busy || !path}>Start sprint</button>
          </>
        )}

        <div className="sprint-today">
          <span>Today <b>+{todayWords.toLocaleString()}</b> words</span>
          <span>{today.length} session{today.length === 1 ? '' : 's'}</span>
          <span>Best <b>{bestWpm.toFixed(1)}</b> WPM</span>
        </div>

        {history.length > 0 && (
          <details className="sprint-history">
            <summary>Recent sprints</summary>
            {history.slice(0, 6).map((item) => (
              <div key={item.id}>
                <span>{new Date(item.started_at).toLocaleString()}</span>
                <span>{item.duration_minutes}m</span>
                <span>{item.net_words === null ? 'active' : `${item.net_words >= 0 ? '+' : ''}${item.net_words} words`}</span>
                <span>{item.words_per_minute === null ? '' : `${item.words_per_minute.toFixed(1)} WPM`}</span>
              </div>
            ))}
          </details>
        )}
        {error && <small className="sprint-error">{error}</small>}
      </div>
    </details>
  )
}
