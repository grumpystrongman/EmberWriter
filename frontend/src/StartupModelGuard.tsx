import { type ReactNode, useEffect, useState } from 'react'

const API = 'http://127.0.0.1:8000/api'
const PROVIDER_KEY = 'emberwriter.provider'

type Provider = {
  provider: 'ollama' | 'openai_compatible'
  base_url: string
  model: string
  api_key?: string
}

const defaultProvider: Provider = {
  provider: 'ollama',
  base_url: 'http://localhost:11434',
  model: '',
  api_key: '',
}

const preferredLocalModels = [
  'R4C3R/qwen2.5-14b-instruct-heretic:q4_k_m',
  'R4C3R/qwen3-8b-heretic:q4_k_m',
]

function readProvider(): Provider {
  try {
    const raw = localStorage.getItem(PROVIDER_KEY)
    if (!raw) return defaultProvider
    return { ...defaultProvider, ...JSON.parse(raw) } as Provider
  } catch {
    return defaultProvider
  }
}

function chooseModel(models: string[]) {
  for (const preferred of preferredLocalModels) {
    const match = models.find((model) => model.toLowerCase() === preferred.toLowerCase())
    if (match) return match
  }
  return models[0] || ''
}

export default function StartupModelGuard({ children }: { children: ReactNode }) {
  const initialProvider = readProvider()
  const [ready, setReady] = useState(Boolean(initialProvider.model.trim()))

  useEffect(() => {
    if (initialProvider.model.trim()) {
      localStorage.setItem(PROVIDER_KEY, JSON.stringify(initialProvider))
      return
    }

    let disposed = false
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort(), 3000)

    async function restoreModel() {
      try {
        const response = await fetch(`${API}/models`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(initialProvider),
          signal: controller.signal,
        })
        if (!response.ok) return
        const payload = await response.json() as { models?: string[] }
        const model = chooseModel(payload.models || [])
        if (!model) return
        const restored = { ...initialProvider, model }
        localStorage.setItem(PROVIDER_KEY, JSON.stringify(restored))
        window.dispatchEvent(new CustomEvent('emberwriter:provider-ready', { detail: restored }))
      } catch {
        // Keep EmberWriter usable when the local model server is unavailable.
      } finally {
        window.clearTimeout(timeout)
        if (!disposed) setReady(true)
      }
    }

    void restoreModel()
    return () => {
      disposed = true
      window.clearTimeout(timeout)
      controller.abort()
    }
  }, [])

  if (!ready) {
    return <div className="startup-model-guard">Connecting to your local writing model…</div>
  }

  return <>{children}</>
}
