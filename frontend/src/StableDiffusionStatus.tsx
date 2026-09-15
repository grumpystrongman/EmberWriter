import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import './stable-diffusion-status.css'

const API = '/api'
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
  managed?: boolean
  managed_state?: string | null
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
  const [mountTarget, setMountTarget] = useState<HTMLElement | null>(null)

  async function check(autoDetect = true, showSpinner = true): Promise<Status | null> {
    if (showSpinner) setChecking(true)
    try {
      const url = currentUrl()
      const response = await fetch(
        `${API}/stable-diffusion/status?base_url=${encodeURIComponent(url)}&auto_detect=${autoDetect ? 'true' : 'false'}`,
      )
      if (!response.ok) throw new Error(`Image status returned ${response.status}`)
      const result = await response.json() as Status
      setStatus(result)
      return result
    } catch {
      if (showSpinner) setStatus(null)
      return null
    } finally {
      if (showSpinner) setChecking(false)
    }
  }

  async function ensureAndCheck(showSpinner = false) {
    const result = await check(true, showSpinner)
    if (!result || result.ok || !result.managed) return
    try {
      await fetch(`${API}/stable-diffusion/managed/ensure`, { method: 'POST' })
    } catch {
      // The next health poll retries. The user never has to babysit startup.
    }
  }

  useEffect(() => {
    setMountTarget(document.querySelector<HTMLElement>('.workspace-actions'))
    void ensureAndCheck(true)

    // Forge/model initialization can take several minutes on a cold machine.
    // Keep reconnecting in the background instead of making the author press a
    // test button or restart EmberWriter when the service becomes ready.
    const timer = window.setInterval(() => {
      void ensureAndCheck(false)
    }, 5000)
    return () => window.clearInterval(timer)
  }, [])

  function applyDetected() {
    if (!status?.resolved_url) return
    saveUrl(status.resolved_url)
    setExpanded(false)
    void check(false)
  }

  const managedStarting = Boolean(status?.managed && !status.ok)
  const managedRepairing = status?.managed_state === 'repairing'
  const chipText = checking
    ? 'Checking images…'
    : status?.ok
      ? 'Images ready'
      : managedRepairing
        ? 'Images repairing…'
        : managedStarting
          ? 'Images starting…'
          : 'Images offline'

  if (!mountTarget || (!status && !checking)) return null

  return createPortal(
    <aside className={`sd-status ${status?.ok ? 'ready' : managedStarting ? 'starting' : 'offline'} ${expanded ? 'expanded' : ''}`}>
      <button
        type="button"
        className="sd-status-chip"
        onClick={() => setExpanded((value) => !value)}
        title={status?.message || 'Check the local image server'}
      >
        <span className="sd-dot" />
        {chipText}
      </button>
      {expanded && status && (
        <div className="sd-status-card">
          <strong>
            {status.ok
              ? 'Stable Diffusion connected'
              : managedStarting
                ? 'Stable Diffusion is starting automatically'
                : 'Stable Diffusion needs attention'}
          </strong>
          <p>{status.message}</p>
          {status.model && <small>Model: {status.model}</small>}
          {status.auto_detected && status.resolved_url && (
            <button type="button" className="sd-apply" onClick={applyDetected}>Use detected server · {status.resolved_url}</button>
          )}
          {!status.ok && !managedStarting && status.attempts.length > 0 && (
            <details>
              <summary>Connection checks ({status.attempts.length})</summary>
              {status.attempts.map((attempt) => (
                <div className="sd-attempt" key={attempt.url}>
                  <b>{attempt.url}</b><span>{attempt.kind} · {attempt.message}</span>
                </div>
              ))}
            </details>
          )}
          {!status.ok && !managedStarting && status.suggestions.length > 0 && (
            <ul>{status.suggestions.map((item) => <li key={item}>{item}</li>)}</ul>
          )}
          <div className="sd-status-actions">
            <button type="button" onClick={() => void ensureAndCheck(true)} disabled={checking}>Recheck now</button>
            <button type="button" onClick={() => setExpanded(false)}>Close</button>
          </div>
        </div>
      )}
    </aside>,
    mountTarget,
  )
}
