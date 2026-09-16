import { useEffect, useMemo, useState } from 'react'

import type { ProviderConfig, WorkspaceProject } from './workspace-types'
import './ai-studio.css'

const DEFAULT_PROVIDER: ProviderConfig = {
  provider: 'ollama',
  base_url: 'http://localhost:11434',
  model: '',
  api_key: '',
}

const STUDIO_CONTEXT_SENTINEL = '__EMBER_STUDIO_CONTEXT_V1__'

type StudioMode = 'scene' | 'brainstorm' | 'creative'
type SaveDestination = 'studio' | 'draft' | 'research'
type HeatLevel = 'simmer' | 'hot' | 'scorching' | 'inferno'
type TensionCurve = 'slow_burn' | 'steady_rise' | 'pressure_cooker' | 'flashpoint'

type CraftControls = {
  heat_level: HeatLevel
  tension_curve: TensionCurve
  voice_lock: boolean
  quality_pass: boolean
  sensory_intensity: number
  dialogue_intensity: number
  interiority: number
}

type GenerateResponse = {
  text: string
  context_files: string[]
  refined: boolean
  partial?: boolean
  warning?: string
}

type BinderNode = {
  id: string
  title: string
  kind: string
  parent_id: string | null
  path: string | null
}

type BinderState = {
  roots: string[]
  nodes: BinderNode[]
}

type Props = {
  apiBase: string
  project: WorkspaceProject
}

const DEFAULT_CRAFT: CraftControls = {
  heat_level: 'hot',
  tension_curve: 'slow_burn',
  voice_lock: true,
  quality_pass: false,
  sensory_intensity: 3,
  dialogue_intensity: 3,
  interiority: 3,
}

const MODE_COPY: Record<StudioMode, { title: string; description: string; mode: 'write' | 'brainstorm'; placeholder: string }> = {
  scene: {
    title: 'Scene Writer',
    description: 'Draft a complete scene from your direction without letting old chapter prose become the continuation target.',
    mode: 'write',
    placeholder: 'Describe the scene you want: participants, location, emotional objective, required beats, ending state, and anything the prose must or must not do…',
  },
  brainstorm: {
    title: 'Brainstorm Room',
    description: 'Explore plot turns, relationship beats, world ideas, complications, alternatives, and consequences.',
    mode: 'brainstorm',
    placeholder: 'What are you trying to solve or explore? Ask for options, tradeoffs, consequences, twists, scene beats, or character possibilities…',
  },
  creative: {
    title: 'Creative Lab',
    description: 'Freeform story thinking for fragments, riffs, dialogue ideas, imagery, lore, titles, and strange possibilities.',
    mode: 'brainstorm',
    placeholder: 'Give Ember a fragment, question, image, mood, line of dialogue, half-formed idea, or creative problem to play with…',
  },
}

async function jsonFetch<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
  })
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`
    try {
      const body = await response.json()
      detail = body.detail || detail
    } catch {
      // Keep the HTTP status when the response is not JSON.
    }
    throw new Error(detail)
  }
  return response.json() as Promise<T>
}

function readStoredProvider(): ProviderConfig {
  try {
    const stored = localStorage.getItem('emberwriter.provider')
    return stored ? { ...DEFAULT_PROVIDER, ...JSON.parse(stored) } : DEFAULT_PROVIDER
  } catch {
    return DEFAULT_PROVIDER
  }
}

function readStoredCraft(): CraftControls {
  try {
    const stored = localStorage.getItem('emberwriter.craftControls')
    return stored ? { ...DEFAULT_CRAFT, ...JSON.parse(stored) } : DEFAULT_CRAFT
  } catch {
    return DEFAULT_CRAFT
  }
}

function defaultTitle(mode: StudioMode) {
  const label = mode === 'scene' ? 'Studio Scene' : mode === 'brainstorm' ? 'Brainstorm' : 'Creative Notes'
  return `${label} ${new Date().toLocaleDateString()}`
}

function rootByTitle(state: BinderState, title: string): BinderNode | undefined {
  const roots = new Set(state.roots)
  return state.nodes.find((node) => roots.has(node.id) && node.title === title)
}

export default function AIStudioWorkspace({ apiBase, project }: Props) {
  const [studioMode, setStudioMode] = useState<StudioMode>('scene')
  const [prompt, setPrompt] = useState('')
  const [output, setOutput] = useState('')
  const [scratchpad, setScratchpad] = useState('')
  const [title, setTitle] = useState(() => defaultTitle('scene'))
  const [destination, setDestination] = useState<SaveDestination>('studio')
  const [provider, setProvider] = useState<ProviderConfig>(readStoredProvider)
  const [models, setModels] = useState<string[]>([])
  const [craft, setCraft] = useState<CraftControls>(readStoredCraft)
  const [contextFiles, setContextFiles] = useState<string[]>([])
  const [busy, setBusy] = useState(false)
  const [saving, setSaving] = useState(false)
  const [status, setStatus] = useState('Studio ready · isolated scene context · no manuscript continuation anchor')
  const modeCopy = MODE_COPY[studioMode]

  const wordCount = useMemo(() => output.trim() ? output.trim().split(/\s+/).length : 0, [output])

  useEffect(() => {
    localStorage.setItem('emberwriter.provider', JSON.stringify(provider))
  }, [provider])

  useEffect(() => {
    localStorage.setItem('emberwriter.craftControls', JSON.stringify(craft))
  }, [craft])

  useEffect(() => {
    setTitle((current) => current.trim() ? current : defaultTitle(studioMode))
  }, [studioMode])

  useEffect(() => {
    void refreshModels()
    // Provider settings can be edited in the main app and persist through localStorage.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function refreshModels() {
    try {
      const next = await jsonFetch<{ models: string[] }>(`${apiBase}/models`, {
        method: 'POST',
        body: JSON.stringify(provider),
      })
      setModels(next.models)
      if (!provider.model && next.models[0]) {
        setProvider((current) => ({ ...current, model: next.models[0] }))
      }
    } catch (error) {
      setStatus(`Model check failed: ${(error as Error).message}`)
    }
  }

  function chooseMode(next: StudioMode) {
    setStudioMode(next)
    setOutput('')
    setContextFiles([])
    setTitle(defaultTitle(next))
    setStatus(`${MODE_COPY[next].title} ready · isolated from old manuscript prose`)
  }

  async function generate() {
    if (!prompt.trim() || busy) return
    if (!provider.model.trim()) {
      setStatus('Choose a local model before generating')
      return
    }

    setBusy(true)
    setOutput('')
    setContextFiles([])
    setStatus(`${modeCopy.title} is working…`)
    try {
      const result = await jsonFetch<GenerateResponse>(`${apiBase}/projects/${project.slug}/generate`, {
        method: 'POST',
        body: JSON.stringify({
          prompt: prompt.trim(),
          mode: modeCopy.mode,
          active_file: null,
          selected_text: STUDIO_CONTEXT_SENTINEL,
          provider,
          craft,
        }),
      })
      setOutput(result.text)
      setContextFiles(result.context_files || [])
      const words = result.text.trim() ? result.text.trim().split(/\s+/).length : 0
      if (result.partial) {
        setStatus(`Partial draft preserved · ${words.toLocaleString()} words · ${result.warning || 'generation ended before the full scene completed'}`)
      } else if (result.refined) {
        setStatus(`${modeCopy.title} complete · Craft Pass applied · ${words.toLocaleString()} words`)
      } else {
        setStatus(`${modeCopy.title} complete · ${words.toLocaleString()} words`)
      }
    } catch (error) {
      setStatus(`Generation failed: ${(error as Error).message}`)
    } finally {
      setBusy(false)
    }
  }

  async function ensureStudioFolder(state: BinderState): Promise<{ state: BinderState; folder: BinderNode }> {
    const storyBible = rootByTitle(state, 'Story Bible')
    const existing = state.nodes.find((node) => node.kind === 'folder' && node.title === 'AI Studio')
    if (existing) return { state, folder: existing }

    const before = new Set(state.nodes.map((node) => node.id))
    const next = await jsonFetch<BinderState>(`${apiBase}/projects/${project.slug}/binder/nodes`, {
      method: 'POST',
      body: JSON.stringify({
        title: 'AI Studio',
        kind: 'folder',
        parent_id: storyBible?.id || null,
        include_in_compile: false,
        custom_metadata: { workspace: 'studio' },
      }),
    })
    const folder = next.nodes.find((node) => !before.has(node.id) && node.kind === 'folder')
      || next.nodes.find((node) => node.kind === 'folder' && node.title === 'AI Studio')
    if (!folder) throw new Error('Could not create the AI Studio Binder folder')
    return { state: next, folder }
  }

  async function saveToBinder(text: string, source: 'generated' | 'scratchpad') {
    const body = text.trim()
    if (!body || saving) return
    setSaving(true)
    setStatus('Saving to Binder…')
    try {
      let state = await jsonFetch<BinderState>(`${apiBase}/projects/${project.slug}/binder`)
      let parent: BinderNode | undefined
      let kind: 'document' | 'note' | 'research' = 'note'
      let includeInCompile = false

      if (destination === 'draft') {
        parent = rootByTitle(state, 'Draft')
        kind = 'document'
        includeInCompile = true
      } else if (destination === 'research') {
        parent = rootByTitle(state, 'Research')
        kind = 'research'
      } else {
        const studio = await ensureStudioFolder(state)
        state = studio.state
        parent = studio.folder
        kind = 'note'
      }

      if (!parent) throw new Error(`Could not find the Binder destination for ${destination}`)

      const before = new Set(state.nodes.map((node) => node.id))
      const documentTitle = title.trim() || defaultTitle(studioMode)
      const next = await jsonFetch<BinderState>(`${apiBase}/projects/${project.slug}/binder/nodes`, {
        method: 'POST',
        body: JSON.stringify({
          title: documentTitle,
          kind,
          parent_id: parent.id,
          include_in_compile: includeInCompile,
          keywords: ['ai-studio', studioMode, source],
          custom_metadata: { workspace: 'studio', studio_mode: studioMode, source },
        }),
      })
      const created = next.nodes.find((node) => !before.has(node.id) && node.path)
      if (!created?.path) throw new Error('Binder created the item but did not assign a document path')

      await jsonFetch(`${apiBase}/projects/${project.slug}/file?path=${encodeURIComponent(created.path)}`, {
        method: 'PUT',
        body: JSON.stringify({ content: `# ${documentTitle}\n\n${body}\n` }),
      })

      window.dispatchEvent(new CustomEvent('emberwriter:binder-changed', { detail: { slug: project.slug } }))
      setStatus(`Saved “${documentTitle}” to Binder · ${created.path}`)
    } catch (error) {
      setStatus(`Binder save failed: ${(error as Error).message}`)
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="ai-studio center-tool">
      <header className="ai-studio-header">
        <div>
          <small>STUDIO · {project.name}</small>
          <h1>Ember Studio</h1>
          <p>AI writing, story exploration, and creative scratch work in a dedicated workspace. Studio uses named-character canon, relationship state, voice, craft rules, and relevant world references while excluding unrelated chapter prose from retrieval.</p>
        </div>
        <div className="ai-studio-model">
          <label>Model</label>
          <div>
            <select value={provider.model} onChange={(event) => setProvider({ ...provider, model: event.target.value })}>
              {!provider.model && <option value="">Choose model</option>}
              {models.map((model) => <option key={model} value={model}>{model}</option>)}
              {provider.model && !models.includes(provider.model) && <option value={provider.model}>{provider.model}</option>}
            </select>
            <button type="button" onClick={() => void refreshModels()} disabled={busy}>↻</button>
          </div>
        </div>
      </header>

      <div className="ai-studio-modebar" role="tablist" aria-label="Studio mode">
        {(Object.keys(MODE_COPY) as StudioMode[]).map((item) => (
          <button key={item} type="button" className={studioMode === item ? 'active' : ''} onClick={() => chooseMode(item)}>
            <strong>{MODE_COPY[item].title}</strong>
            <span>{MODE_COPY[item].description}</span>
          </button>
        ))}
      </div>

      <div className="ai-studio-grid">
        <div className="ai-studio-compose">
          <div className="ai-studio-card">
            <div className="ai-studio-card-head">
              <div><small>DIRECT THE AI</small><h2>{modeCopy.title}</h2></div>
              <span className="ai-studio-independent">No manuscript retrieval</span>
            </div>
            <textarea
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              placeholder={modeCopy.placeholder}
              rows={10}
            />

            {studioMode === 'scene' && (
              <div className="ai-studio-craft">
                <div className="ai-studio-field">
                  <label>Heat</label>
                  <div className="ai-studio-heat">
                    {(['simmer', 'hot', 'scorching', 'inferno'] as HeatLevel[]).map((level) => (
                      <button key={level} type="button" className={craft.heat_level === level ? 'active' : ''} onClick={() => setCraft({ ...craft, heat_level: level })}>{level}</button>
                    ))}
                  </div>
                </div>
                <div className="ai-studio-field">
                  <label>Tension curve</label>
                  <select value={craft.tension_curve} onChange={(event) => setCraft({ ...craft, tension_curve: event.target.value as TensionCurve })}>
                    <option value="slow_burn">Slow burn</option>
                    <option value="steady_rise">Steady rise</option>
                    <option value="pressure_cooker">Pressure cooker</option>
                    <option value="flashpoint">Flashpoint</option>
                  </select>
                </div>
                <div className="ai-studio-sliders">
                  <label>Sensory <span>{craft.sensory_intensity}/5</span><input type="range" min="1" max="5" value={craft.sensory_intensity} onChange={(event) => setCraft({ ...craft, sensory_intensity: Number(event.target.value) })} /></label>
                  <label>Dialogue <span>{craft.dialogue_intensity}/5</span><input type="range" min="1" max="5" value={craft.dialogue_intensity} onChange={(event) => setCraft({ ...craft, dialogue_intensity: Number(event.target.value) })} /></label>
                  <label>Interiority <span>{craft.interiority}/5</span><input type="range" min="1" max="5" value={craft.interiority} onChange={(event) => setCraft({ ...craft, interiority: Number(event.target.value) })} /></label>
                </div>
                <div className="ai-studio-checks">
                  <label><input type="checkbox" checked={craft.voice_lock} onChange={(event) => setCraft({ ...craft, voice_lock: event.target.checked })} /> Voice Lock</label>
                  <label><input type="checkbox" checked={craft.quality_pass} onChange={(event) => setCraft({ ...craft, quality_pass: event.target.checked })} /> Craft Pass</label>
                </div>
              </div>
            )}

            <button className="ai-studio-generate" type="button" onClick={() => void generate()} disabled={busy || !prompt.trim() || !provider.model}>
              {busy ? 'Ember is writing…' : studioMode === 'scene' ? 'Write the scene' : studioMode === 'brainstorm' ? 'Brainstorm' : 'Explore the idea'}
            </button>
          </div>

          <div className="ai-studio-card ai-studio-output">
            <div className="ai-studio-card-head">
              <div><small>AI OUTPUT</small><h2>Working Draft</h2></div>
              <span>{wordCount.toLocaleString()} words</span>
            </div>
            {output ? <div className="ai-studio-prose">{output}</div> : <div className="ai-studio-empty">Your generated scene, brainstorm, or creative exploration will appear here. Live generation is shown by the global writing overlay while the model is working.</div>}
            {contextFiles.length > 0 && <details><summary>Studio context used ({contextFiles.length})</summary>{contextFiles.map((file) => <div key={file}>{file}</div>)}</details>}
          </div>
        </div>

        <aside className="ai-studio-sidebar">
          <div className="ai-studio-card">
            <small>CREATIVE SCRATCHPAD</small>
            <h2>Your thoughts</h2>
            <p>Capture fragments, alternate beats, dialogue, reminders, or notes without changing the manuscript.</p>
            <textarea value={scratchpad} onChange={(event) => setScratchpad(event.target.value)} placeholder="Private working notes for this idea…" rows={12} />
          </div>

          <div className="ai-studio-card ai-studio-save">
            <small>SAVE TO BINDER</small>
            <h2>Keep what matters</h2>
            <label>Title<input value={title} onChange={(event) => setTitle(event.target.value)} /></label>
            <label>Destination
              <select value={destination} onChange={(event) => setDestination(event.target.value as SaveDestination)}>
                <option value="studio">AI Studio notes</option>
                <option value="draft">Draft manuscript</option>
                <option value="research">Research</option>
              </select>
            </label>
            <div className="ai-studio-save-actions">
              <button type="button" onClick={() => void saveToBinder(output, 'generated')} disabled={saving || !output.trim()}>Save AI output</button>
              <button type="button" onClick={() => void saveToBinder(scratchpad, 'scratchpad')} disabled={saving || !scratchpad.trim()}>Save scratchpad</button>
            </div>
            <p className="ai-studio-save-note">Studio notes are kept outside the compiled manuscript. Choosing Draft creates a real manuscript document and includes it in compile order.</p>
          </div>

          <div className="ai-studio-status" role="status" aria-live="polite">{status}</div>
        </aside>
      </div>
    </section>
  )
}
