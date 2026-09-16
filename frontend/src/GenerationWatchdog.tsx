import { useEffect, useRef, useState } from 'react'

type ActiveGeneration = {
  slug: string
  startedAt: number
  cancelUrl: string
  controller: AbortController
}

type StreamFinal = {
  text: string
  context_files: string[]
  refined: boolean
  assistance_event_id?: string | null
  partial?: boolean
  warning?: string
}

type StreamEvent =
  | { type: 'delta'; text: string }
  | { type: 'status'; message: string }
  | ({ type: 'final' } & StreamFinal)
  | { type: 'error'; detail: string }

const BROWSER_WATCHDOG_MS = 11 * 60 * 1000
const PREVIEW_CHARS = 6000

function formatElapsed(ms: number): string {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000))
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${minutes}:${String(seconds).padStart(2, '0')}`
}

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

export default function GenerationWatchdog() {
  const [active, setActive] = useState<ActiveGeneration | null>(null)
  const [elapsed, setElapsed] = useState(0)
  const [phase, setPhase] = useState('Preparing story context…')
  const [preview, setPreview] = useState('')
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
      const streamUrl = url.replace(/\/generate(?:\?.*)?$/, '/generate/stream')
      const generation: ActiveGeneration = {
        slug: decodeURIComponent(match[1]),
        startedAt: Date.now(),
        cancelUrl,
        controller,
      }
      activeRef.current = generation
      setActive(generation)
      setElapsed(0)
      setPhase('Preparing story context…')
      setPreview('')

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
        const response = await originalFetch(streamUrl, { ...init, signal: controller.signal })
        if (!response.ok || !response.body) return response

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''
        let accumulated = ''
        let finalPayload: StreamFinal | null = null
        let streamError = ''
        let lastPreviewPaint = 0

        const consumeLine = (line: string) => {
          const trimmed = line.trim()
          if (!trimmed) return
          let event: StreamEvent
          try {
            event = JSON.parse(trimmed) as StreamEvent
          } catch {
            streamError = 'EmberWriter received an invalid generation stream from the local API.'
            return
          }

          if (event.type === 'status') {
            setPhase(event.message)
            return
          }
          if (event.type === 'delta') {
            accumulated += event.text
            const now = Date.now()
            if (now - lastPreviewPaint >= 120) {
              setPreview(accumulated.slice(-PREVIEW_CHARS))
              lastPreviewPaint = now
            }
            return
          }
          if (event.type === 'error') {
            streamError = event.detail
            return
          }
          if (event.type === 'final') {
            finalPayload = {
              text: event.text,
              context_files: event.context_files || [],
              refined: Boolean(event.refined),
              assistance_event_id: event.assistance_event_id,
              partial: event.partial,
              warning: event.warning,
            }
            accumulated = event.text
            setPreview(event.text.slice(-PREVIEW_CHARS))
            if (event.partial && event.warning) setPhase(event.warning)
          }
        }

        while (true) {
          const { value, done } = await reader.read()
          buffer += decoder.decode(value || new Uint8Array(), { stream: !done })
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''
          lines.forEach(consumeLine)
          if (done) break
        }
        buffer += decoder.decode()
        if (buffer.trim()) consumeLine(buffer)

        if (streamError && !finalPayload) return jsonResponse({ detail: streamError }, 502)
        if (!finalPayload && accumulated.trim()) {
          finalPayload = {
            text: accumulated.trim(),
            context_files: [],
            refined: false,
            partial: true,
            warning: streamError || 'Generation ended before EmberWriter received the final completion event.',
          }
        }
        if (!finalPayload) {
          return jsonResponse(
            { detail: streamError || 'The model connection closed before any text was generated.' },
            502,
          )
        }
        return jsonResponse(finalPayload)
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
          setPhase('Preparing story context…')
          setPreview('')
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
        width: 'min(520px, calc(100vw - 40px))',
        maxHeight: '52vh',
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
        padding: '12px 14px',
        borderRadius: 10,
        background: 'var(--panel, #171a20)',
        border: '1px solid var(--border, #343a46)',
        boxShadow: '0 10px 30px rgba(0,0,0,.35)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        <div>
          <strong>Ember is writing · {formatElapsed(elapsed)}</strong>
          <div style={{ opacity: 0.75, fontSize: 12, marginTop: 2 }}>{phase}</div>
        </div>
        <button type="button" onClick={cancel}>Cancel</button>
      </div>
      {preview && (
        <div
          aria-live="off"
          style={{
            maxHeight: '34vh',
            overflow: 'auto',
            whiteSpace: 'pre-wrap',
            fontFamily: 'Georgia, serif',
            fontSize: 13,
            lineHeight: 1.45,
            padding: '10px 11px',
            borderRadius: 8,
            background: 'rgba(0,0,0,.18)',
          }}
        >
          {preview}
        </div>
      )}
    </div>
  )
}
