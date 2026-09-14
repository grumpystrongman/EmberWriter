import { useEffect, useState } from 'react'
import './stable-diffusion-status.css'

const API = 'http://127.0.0.1:8000/api'
const DEFAULT_URL = 'http://127.0.0.1:7860'

type Attempt = {
  url: string
  ok: boolean
  kind: string
  message: string
}

type Status = {
  ok: boolean
  configured_url: string
  resolved_url: string | null
  auto_detected: boolean
  server_type: string | null
  model: string
  message: string
  attempts: Attempt[]
  suggestions: string[]
}

function currentUrl() {
  const visual = localStorage.getItem('emberwriter.sd_url')?.trim()
  if (visual) return visual
  try {
    const provider = JSON.parse(localStorage.getItem('emberwriter.imageProvider') || '{}') as { base_url?: string }
    if (provider.base_url?.trim()) return provider.base_url.trim()
  } catch {
    // Ignore malformed local settings and fall back to the default.
  }
  return DEFAULT_URL
}

function saveUrl(url: string) {
  localStorage.setItem('emberwriter.sd_url', url)
  let provider: Record<string, unknown> = {}
  try {
    provider = JSON.parse(localStorage.getItem('emberwriter.imageProvider') || '{}') as Record<string, unknown>
  } catch {
    provider = {}
  }
  localStorage.setItem('emberwriter.imageProvider', JSON.stringify({ ...provider, base_url: url }))
}

export default function StableDiffusionStatus() {
  const [status, setStatus] = useState<Status | null>(null)
  const [checking, setChecking] = useState(false)
  const [expanded, setExpanded] = useState(false)

  async function check(autoDetect = true) {
    setChecking(true)
    try {
      const url = currentUrl()
      const response = await fetch(
        `${API}/stable-diffusion/status?base_url=${encodeURIComponent(url)}&auto_detect=${autoDetect ? 'true' : 'false'}`,
      )
      const result = await response.json() as Status
      setStatus(result)
      if (!result.ok) setExpanded(true)
    } catch {
      setStatus(null)
    } finally {
      setChecking(false)
    }
  }

  useEffect(() => { void check(true) }, [])

  function applyDetected() {
    if (!status?.resolved_url) return
    saveUrl(status.resolved_url)
    window.location.reload()
  }

  if (!status && !checking) return null

  return (
    <aside className={`sd-status ${status?.ok ? 'ready' : 'offline'} ${expanded ? 'expanded' : ''}`}>
      <button type="button" className="sd-status-chip" onClick={() => setExpanded((value) => !value)}>
        <span className="sd-dot" />
        {checking ? 'Checking image server…' : status?.ok ? 'Image server ready' : 'Image server offline'}
      </button>
      {expanded && status && (
        <div className="sd-status-card">
          <strong>{status.ok ? 'Stable Diffusion connected' : 'Stable Diffusion needs attention'}</strong>
          <p>{status.message}</p>
          {status.model && <small>Model: {status.model}</small>}
          {status.auto_detected && status.resolved_url && (
            <button type="button" className="sd-apply" onClick={applyDetected}>Use detected server · {status.resolved_url}</button>
          )}
          {!status.ok && status.attempts.length > 0 && (
            <details>
              <summary>Connection checks ({status.attempts.length})</summary>
              {status.attempts.map((attempt) => (
                <div className="sd-attempt" key={attempt.url}>
                  <b>{attempt.url}</b><span>{attempt.kind} · {attempt.message}</span>
                </div>
              ))}
            </details>
          )}
          {!status.ok && status.suggestions.length > 0 && (
            <ul>{status.suggestions.map((item) => <li key={item}>{item}</li>)}</ul>
          )}
          <div className="sd-status-actions">
            <button type="button" onClick={() => void check(true)} disabled={checking}>Test & auto-detect</button>
            <button type="button" onClick={() => setExpanded(false)}>Close</button>
          </div>
        </div>
      )}
    </aside>
  )
}
