import { useEffect, useMemo, useState } from 'react'

import type { ProviderConfig } from './workspace-types'
import './performance-panel.css'

type ModelCall = {
  stage?: string
  model?: string
  performance_profile?: string
  context_tokens?: number
  first_token_ms?: number | null
  total_ms?: number | null
  prompt_eval_tokens?: number
  prompt_eval_ms?: number | null
  prompt_tokens_per_second?: number | null
  eval_tokens?: number
  eval_ms?: number | null
  tokens_per_second?: number | null
}

type LoadedModel = {
  name?: string
  id?: string
  size?: string
  processor?: string
  until?: string
}

type GpuInfo = {
  name: string
  memory_total_mb: number
  memory_used_mb: number
  utilization_percent: number
}

type PerformanceStatus = {
  active_generation?: Record<string, unknown> | null
  last_generation?: Record<string, unknown> | null
  recent_calls?: ModelCall[]
  ollama?: {
    available?: boolean
    loaded_models?: LoadedModel[]
    flash_attention?: string
    kv_cache_type?: string
    num_parallel?: string
  }
  gpus?: GpuInfo[]
  recommendations?: string[]
}

const API = '/api'

function readProvider(): ProviderConfig {
  try {
    const raw = localStorage.getItem('emberwriter.provider')
    if (raw) return JSON.parse(raw) as ProviderConfig
  } catch {
    // Fall through to local default.
  }
  return { provider: 'ollama', base_url: 'http://localhost:11434', model: '' }
}

function seconds(ms: number | null | undefined) {
  if (!ms) return '—'
  if (ms < 1000) return `${Math.round(ms)} ms`
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)} s`
  return `${(ms / 60_000).toFixed(1)} min`
}

function memory(mb: number) {
  return `${(mb / 1024).toFixed(1)} GB`
}

async function readDetail(response: Response) {
  try {
    const payload = await response.json() as { detail?: string }
    return payload.detail || `${response.status} ${response.statusText}`
  } catch {
    return `${response.status} ${response.statusText}`
  }
}

export default function PerformancePanel() {
  const [open, setOpen] = useState(false)
  const [status, setStatus] = useState<PerformanceStatus | null>(null)
  const [error, setError] = useState('')
  const [action, setAction] = useState('')

  const latestProse = useMemo(
    () => [...(status?.recent_calls || [])].reverse().find((call) => call.stage?.includes('prose')),
    [status],
  )
  const latestVerifier = useMemo(
    () => [...(status?.recent_calls || [])].reverse().find((call) => call.stage?.includes('verifier')),
    [status],
  )

  async function refresh() {
    try {
      const response = await fetch(`${API}/performance`)
      if (!response.ok) throw new Error(await readDetail(response))
      setStatus(await response.json() as PerformanceStatus)
      setError('')
    } catch (cause) {
      setError((cause as Error).message)
    }
  }

  async function post(path: string, body?: unknown) {
    setAction(path)
    try {
      const response = await fetch(`${API}/performance/${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: body === undefined ? undefined : JSON.stringify(body),
      })
      if (!response.ok) throw new Error(await readDetail(response))
      setError('')
      await refresh()
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setAction('')
    }
  }

  useEffect(() => {
    if (!open) return
    void refresh()
    const timer = window.setInterval(() => void refresh(), 5000)
    return () => window.clearInterval(timer)
  }, [open])

  const loaded = status?.ollama?.loaded_models || []
  const gpus = status?.gpus || []

  return (
    <div className={`performance-panel-shell${open ? ' open' : ''}`}>
      <button type="button" className="performance-panel-toggle" onClick={() => setOpen((value) => !value)} title="Local AI performance">
        ⚡ Performance
      </button>
      {open && (
        <aside className="performance-panel" aria-label="Local AI performance">
          <header>
            <div><small>LOCAL INFERENCE</small><strong>Performance</strong></div>
            <button type="button" onClick={() => setOpen(false)} aria-label="Close performance panel">×</button>
          </header>

          <section>
            <div className="performance-actions">
              <button type="button" onClick={() => void refresh()} disabled={Boolean(action)}>Refresh</button>
              <button type="button" onClick={() => void post('warm', readProvider())} disabled={Boolean(action) || !readProvider().model}>{action === 'warm' ? 'Warming…' : 'Warm model'}</button>
              <button type="button" onClick={() => void post('restart-ollama')} disabled={Boolean(action)}>{action === 'restart-ollama' ? 'Restarting…' : 'Restart Ollama tuned'}</button>
            </div>
            <p className="performance-help">The tuned restart enables Flash Attention, q8 KV cache, and one local generation lane. Refresh after the model reloads to inspect CPU/GPU placement.</p>
          </section>

          {error && <div className="performance-error">{error}</div>}

          <section>
            <h3>Ollama runtime</h3>
            <div className="performance-grid">
              <span>Flash Attention</span><b>{status?.ollama?.flash_attention === '1' ? 'On' : 'Off / external server'}</b>
              <span>KV cache</span><b>{status?.ollama?.kv_cache_type || '—'}</b>
              <span>Parallel requests</span><b>{status?.ollama?.num_parallel || '—'}</b>
            </div>
            {loaded.length ? loaded.map((model, index) => (
              <div className="performance-model" key={`${model.name || model.id || 'model'}-${index}`}>
                <strong>{model.name || 'Loaded model'}</strong>
                <span>{model.processor || 'Processor placement unavailable'}</span>
                {model.size && <small>{model.size}{model.until ? ` · warm ${model.until}` : ''}</small>}
              </div>
            )) : <p className="performance-muted">No model is currently loaded. Warm the selected model to see placement.</p>}
          </section>

          <section>
            <h3>GPU</h3>
            {gpus.length ? gpus.map((gpu) => (
              <div className="performance-model" key={gpu.name}>
                <strong>{gpu.name}</strong>
                <span>{memory(gpu.memory_used_mb)} / {memory(gpu.memory_total_mb)} VRAM · {gpu.utilization_percent}% GPU</span>
              </div>
            )) : <p className="performance-muted">NVIDIA telemetry is unavailable. Ollama’s Processor column still reports CPU/GPU placement when supported.</p>}
          </section>

          <section>
            <h3>Latest prose call</h3>
            {latestProse ? (
              <div className="performance-grid">
                <span>Model</span><b title={latestProse.model}>{latestProse.model || '—'}</b>
                <span>Profile</span><b>{latestProse.performance_profile || '—'}</b>
                <span>Context</span><b>{latestProse.context_tokens?.toLocaleString() || '—'} tokens</b>
                <span>First token</span><b>{seconds(latestProse.first_token_ms)}</b>
                <span>Prompt eval</span><b>{seconds(latestProse.prompt_eval_ms)} · {latestProse.prompt_tokens_per_second || '—'} tok/s</b>
                <span>Generation</span><b>{seconds(latestProse.eval_ms)} · {latestProse.tokens_per_second || '—'} tok/s</b>
                <span>Total model call</span><b>{seconds(latestProse.total_ms)}</b>
              </div>
            ) : <p className="performance-muted">Run a generation on the updated backend to capture timing metrics.</p>}
          </section>

          <section>
            <h3>Latest semantic verifier</h3>
            {latestVerifier ? (
              <div className="performance-grid">
                <span>Context</span><b>{latestVerifier.context_tokens?.toLocaleString() || '—'} tokens</b>
                <span>Prompt eval</span><b>{seconds(latestVerifier.prompt_eval_ms)}</b>
                <span>Generation</span><b>{seconds(latestVerifier.eval_ms)} · {latestVerifier.tokens_per_second || '—'} tok/s</b>
                <span>Total verifier</span><b>{seconds(latestVerifier.total_ms)}</b>
              </div>
            ) : <p className="performance-muted">Verifier timing appears after a Studio scene reaches semantic delivery checking.</p>}
          </section>

          {!!status?.recommendations?.length && (
            <section>
              <h3>What to fix next</h3>
              <ul>{status.recommendations.map((item) => <li key={item}>{item}</li>)}</ul>
            </section>
          )}
        </aside>
      )}
    </div>
  )
}
