import { useEffect, useRef, useState } from 'react'

type ActiveGeneration = {
  slug: string
  startedAt: number
  cancelUrl: string
  controller: AbortController
}

const BROWSER_WATCHDOG_MS = 11 * 60 * 1000

function formatElapsed(ms: number): string {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000))
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${minutes}:${String(seconds).padStart(2, '0')}`
}

export default function GenerationWatchdog() {
  const [active, setActive] = useState<ActiveGeneration | null>(null)
  const [elapsed, setElapsed] = useState(0)
  const activeRef = useRef<ActiveGeneration | null>(null)

  useEffect(() => {
    const originalFetch = window.fetch.bind(window)

    window.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
      const url = typeof input === 'string'
        ? input
        : input instanceof URL
          ? input.toString()
          : input.url
      const method = (init?.method || (input instanceof Request ? input.method : 'GET')).toUpperCase()
      const match = method === 'POST'
        ? url.match(/\/api\/projects\/([^/]+)\/generate(?:\?.*)?$/)
        : null

      if (!match) return originalFetch(input, init)

      const controller = new AbortController()
      const cancelUrl = url.replace(/\/generate(?:\?.*)?$/, '/generate/cancel')
      const generation: ActiveGeneration = {
        slug: decodeURIComponent(match[1]),
        startedAt: Date.now(),
        cancelUrl,
        controller,
      }
      activeRef.current = generation
      setActive(generation)
      setElapsed(0)

      const externalSignal = init?.signal
      const relayAbort = () => controller.abort(externalSignal?.reason)
      if (externalSignal?.aborted) relayAbort()
      else externalSignal?.addEventListener('abort', relayAbort, { once: true })

      let watchdogExpired = false
      const timeout = window.setTimeout(() => {
        watchdogExpired = true
        void originalFetch(cancelUrl, { method: 'POST', headers: { 'Content-Type': 'application/json' } })
        controller.abort()
      }, BROWSER_WATCHDOG_MS)

      try {
        return await originalFetch(input, { ...init, signal: controller.signal })
      } catch (error) {
        if (watchdogExpired) {
          throw new Error('Generation was stopped after 11 minutes instead of being allowed to hang indefinitely.')
        }
        if (controller.signal.aborted) throw new Error('Generation cancelled')
        throw error
      } finally {
        window.clearTimeout(timeout)
        externalSignal?.removeEventListener('abort', relayAbort)
        if (activeRef.current?.controller === controller) {
          activeRef.current = null
          setActive(null)
          setElapsed(0)
        }
      }
    }

    return () => {
      window.fetch = originalFetch
      activeRef.current?.controller.abort()
      activeRef.current = null
    }
  }, [])

  useEffect(() => {
    if (!active) return
    const timer = window.setInterval(() => setElapsed(Date.now() - active.startedAt), 1000)
    return () => window.clearInterval(timer)
  }, [active])

  function cancel() {
    const current = activeRef.current
    if (!current) return
    // Tell the backend to cancel the actual model task before aborting the browser request.
    void window.fetch(current.cancelUrl, { method: 'POST', headers: { 'Content-Type': 'application/json' } })
    current.controller.abort()
  }

  if (!active) return null

  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        position: 'fixed',
        right: 20,
        bottom: 20,
        zIndex: 10000,
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        padding: '10px 12px',
        borderRadius: 10,
        background: 'var(--panel, #171a20)',
        border: '1px solid var(--border, #343a46)',
        boxShadow: '0 10px 30px rgba(0,0,0,.35)',
      }}
    >
      <span>Writing {formatElapsed(elapsed)}</span>
      <button type="button" onClick={cancel}>Cancel</button>
    </div>
  )
}
