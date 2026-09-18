import { useEffect, useMemo, useRef, useState } from 'react'

import StudioModelRouter from './StudioModelRouter'
import type { ProviderConfig, WorkspaceProject } from './workspace-types'
import './ai-studio.css'

const DEFAULT_PROVIDER: ProviderConfig = {
  provider: 'ollama',
  base_url: 'http://localhost:11434',
  model: '',
  api_key: '',
}

const STUDIO_CONTEXT_SENTINEL = '__EMBER_STUDIO_CONTEXT_V1__'
const CONTINUATION_INTENT = /^(?:please\s+)?(?:continue\b|keep\s+(?:going|writing)\b|resume\b|pick\s+up\b|finish\s+(?:this|the|current)\s+(?:scene|sex\s+scene|intimate\s+scene)\b)/i

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

function wordsIn(text: string) {
  return text.trim() ? text.trim().split(/\s+/).length : 0
}

function normalizeForOverlap(text: string) {
  return text.replace(/\s+/g, ' ').trim().toLocaleLowerCase()
}

function mergeContinuation(existing: string, continuation: string) {
  const left = existing.trim()
  let right = continuation.trim()
  if (!left) return right
  if (!right) return left

  const paragraphs = right.split(/\n\s*\n/)
  while (paragraphs.length > 1) {
    const first = paragraphs[0].trim()
    if (first.length < 80 || !normalizeForOverlap(left).includes(normalizeForOverlap(first))) break
    paragraphs.shift()
  }
  right = paragraphs.join('\n\n').trim()
  if (!right) return left

  const leftWords = left.split(/\s+/)
  const rightWords = right.split(/\s+/)
  const maxOverlap = Math.min(160, leftWords.length, rightWords.length)
  for (let size = maxOverlap; size >= 12; size -= 1) {
    const suffix = leftWords.slice(-size).join(' ').toLocaleLowerCase()
    const prefix = rightWords.slice(0, size).join(' ').toLocaleLowerCase()
    if (suffix === prefix) {
      right = rightWords.slice(size).join(' ').trim()
      break
    }
  }

  return right ? `${left}\n\n${right}` : left
}

const NON_MANUSCRIPT_HANDOFF_BLOCK = /(?:^|\b)(?:\[EMBER_PROMPT\]|I\s+understand(?:\s+the\s+parameters|[.,:]?\s+continuing)|Understood[.,:]?\s+beginning|Here\s+is\s+my\s+continuation|Continue\s+writing\s+in\s+character-specific|Please\s+confirm\s+which\s+is\s+the\s+case|adapt\s+the\s+recovery\s+pipeline|alert\s+the\s+system\s+administrator|CONTINUATION\s+BOUNDARY\s+PASS|ORIGINAL\s+SCENE\s+BRIEF|EXISTING\s+DRAFT\s+HANDOFF|WRITE\s+ONLY\s+NEW\s+PROSE)/i
const INSTRUCTION_BULLET = /^\s*[-*]\s+(?:preserve|match|advance|keep|avoid|continue|write|do\s+not)\b/im

function manuscriptOnlyHandoff(text: string) {
  const blocks = text.split(/\n\s*\n/)
  const kept = blocks.filter((block) => {
    const trimmed = block.trim().replace(/^[*#>\s]+/, '')
    if (!trimmed) return false
    if (NON_MANUSCRIPT_HANDOFF_BLOCK.test(trimmed)) return false
    const instructionBullets = block.split('\n').filter((line) => INSTRUCTION_BULLET.test(line)).length
    if (instructionBullets >= 2) return false
    return true
  })
  return kept.join('\n\n').trim()
}

function freshScenePrompt(direction: string) {
  return [
    direction,
    'STUDIO SCENE DELIVERY CONTRACT:',
    '- Deliver the complete requested scene, not only its setup or buildup.',
    '- Move into the author-requested core event early enough to complete its full dramatic arc on page.',
    '- If the requested core is adult intimacy, buildup alone does not satisfy the brief; complete the requested encounter and its immediate emotional or story consequence.',
    '- Do not stop at the first kiss, first escalation, threshold moment, or other transition into the requested core scene.',
    '- End only after the scene objective has actually happened and the immediate aftermath or changed state has landed.',
  ].join('\n\n')
}

function continuationPrompt(sceneBrief: string, direction: string, existing: string) {
  const handoff = existing.trim().slice(-9000)
  return [
    direction || 'Continue and finish the current scene.',
    'STUDIO CONTINUATION CONTRACT:',
    '- Continue from the EXACT END of the existing draft below.',
    '- The existing draft is already-written manuscript. Do not rewrite, recap, summarize, restart, or paraphrase any of it.',
    '- Do not return to the beginning of the scene or repeat its buildup.',
    '- Start with the very next action, perception, line of dialogue, or sentence after the final words of the handoff.',
    '- Finish the original requested scene objective and its immediate consequence. If the original request was an adult intimacy scene, do not stop after more buildup or at the threshold of the encounter.',
    '',
    'ORIGINAL SCENE BRIEF',
    sceneBrief,
    '',
    'EXISTING DRAFT HANDOFF — REFERENCE ONLY; DO NOT REPEAT',
    handoff,
    '',
    'WRITE ONLY NEW PROSE THAT COMES AFTER THAT FINAL LINE.',
  ].join('\n')
}

export default function AIStudioWorkspace({ apiBase, project }: Props) {
  const [studioMode, setStudioMode] = useState<StudioMode>('scene')
  const [prompt, setPrompt] = useState('')
  const [output, setOutput] = useState('')
  const [sceneBrief, setSceneBrief] = useState('')
  const [scratchpad, setScratchpad] = useState('')
  const [title, setTitle] = useState(() => defaultTitle('scene'))
  const [destination, setDestination] = useState<SaveDestination>('studio')
  const [provider, setProvider] = useState<ProviderConfig>(readStoredProvider)
  const [models, setModels] = useState<string[]>([])
  const [craft, setCraft] = useState<CraftControls>(readStoredCraft)
  const [contextFiles, setContextFiles] = useState<string[]>([])
  const [busy, setBusy] = useState(false)
  const [saving, setSaving] = useState(false)
  const [status, setStatus] = useState('Studio ready · fresh scenes start clean · Continue uses the current Studio draft')
  const [streamingDraft, setStreamingDraft] = useState(false)
  const streamSessionRef = useRef<{ base: string; continuation: boolean } | null>(null)
  const modeCopy = MODE_COPY[studioMode]

  const wordCount = useMemo(() => wordsIn(output), [output])

  useEffect(() => {
    localStorage.setItem('emberwriter.provider', JSON.stringify(provider))
  }, [provider])

  useEffect(() => {
    localStorage.setItem('emberwriter.craftControls', JSON.stringify(craft))
  }, [craft])

  useEffect(() => {
    function onPreview(event: Event) {
      const detail = (event as CustomEvent<{ slug?: string; text?: string; studio?: boolean }>).detail || {}
      const session = streamSessionRef.current
      if (!session || detail.slug !== project.slug || detail.studio !== true) return
      const streamed = detail.text || ''
      setStreamingDraft(true)
      setOutput(session.continuation ? mergeContinuation(session.base, streamed) : streamed)
    }

    function onFinal(event: Event) {
      const detail = (event as CustomEvent<{ slug?: string; studio?: boolean }>).detail || {}
      if (detail.slug === project.slug && detail.studio === true) setStreamingDraft(false)
    }

    function onError(event: Event) {
      const detail = (event as CustomEvent<{ slug?: string; studio?: boolean }>).detail || {}
      if (detail.slug === project.slug && detail.studio === true) setStreamingDraft(false)
    }

    window.addEventListener('emberwriter:generation-preview', onPreview)
    window.addEventListener('emberwriter:generation-final', onFinal)
    window.addEventListener('emberwriter:generation-error', onError)
    return () => {
      window.removeEventListener('emberwriter:generation-preview', onPreview)
      window.removeEventListener('emberwriter:generation-final', onFinal)
      window.removeEventListener('emberwriter:generation-error', onError)
    }
  }, [project.slug])

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
    } catch (error) {
      setStatus(`Model check failed: ${(error as Error).message}`)
    }
  }

  function chooseMode(next: StudioMode) {
    setStudioMode(next)
    setOutput('')
    setSceneBrief('')
    setContextFiles([])
    setTitle(defaultTitle(next))
    setStatus(`${MODE_COPY[next].title} ready · isolated from old manuscript prose`)
  }

  async function requestGeneration(requestPrompt: string, mode: 'write' | 'continue' | 'brainstorm') {
    return jsonFetch<GenerateResponse>(`${apiBase}/projects/${project.slug}/generate`, {
      method: 'POST',
      body: JSON.stringify({
        prompt: requestPrompt,
        mode,
        active_file: null,
        selected_text: STUDIO_CONTEXT_SENTINEL,
        provider,
        craft,
      }),
    })
  }

  async function continueDraft(existing: string, originalBrief: string, direction: string) {
    return requestGeneration(continuationPrompt(originalBrief, direction, existing), 'continue')
  }

  async function continueCurrentScene(direction = prompt.trim()) {
    if (!output.trim() || busy || !provider.model.trim()) return
    const cleanBase = manuscriptOnlyHandoff(output)
    if (!cleanBase) {
      setStatus('Continuation blocked · Working Draft contains no manuscript prose after removing assistant/prompt scaffolding')
      return
    }
    if (cleanBase !== output.trim()) setOutput(cleanBase)
    setBusy(true)
    setContextFiles([])
    streamSessionRef.current = { base: cleanBase, continuation: true }
    setStreamingDraft(true)
    setStatus('Continuing live in Working Draft · provisional until verification passes…')
    try {
      const originalBrief = sceneBrief.trim() || prompt.trim() || direction
      const result = await continueDraft(
        cleanBase,
        originalBrief,
        direction || 'Continue and finish this scene.',
      )
      const merged = mergeContinuation(cleanBase, result.text)
      setOutput(merged)
      setContextFiles(result.context_files || [])
      const words = wordsIn(merged)
      if (result.partial) {
        setStatus(`Partial / unverified continuation preserved · ${words.toLocaleString()} total words · ${result.warning || 'the backend did not verify complete scene delivery'}`)
      } else if (result.refined) {
        setStatus(`Scene continued and verified · Craft Pass applied · ${words.toLocaleString()} total words`)
      } else {
        setStatus(`Scene continued and verified · ${words.toLocaleString()} total words`)
      }
    } catch (error) {
      setStatus(`Continuation failed: ${(error as Error).message}`)
    } finally {
      streamSessionRef.current = null
      setStreamingDraft(false)
      setBusy(false)
    }
  }

  async function generate() {
    if (!prompt.trim() || busy) return
    if (!provider.model.trim()) {
      setStatus('Choose a local model before generating')
      return
    }

    const direction = prompt.trim()
    const explicitContinuation = studioMode === 'scene' && Boolean(output.trim()) && CONTINUATION_INTENT.test(direction)
    if (explicitContinuation) {
      await continueCurrentScene(direction)
      return
    }

    setBusy(true)
    setOutput('')
    setContextFiles([])
    streamSessionRef.current = { base: '', continuation: false }
    setStreamingDraft(true)
    setStatus(`${modeCopy.title} is writing live in Working Draft · provisional until complete…`)
    try {
      if (studioMode === 'scene') {
        setSceneBrief(direction)
        const result = await requestGeneration(freshScenePrompt(direction), 'write')
        const draft = result.text.trim()
        setOutput(draft)
        setContextFiles(result.context_files || [])
        const words = wordsIn(draft)
        if (result.partial) {
          setStatus(`Partial / unverified draft preserved · ${words.toLocaleString()} words · ${result.warning || 'the backend did not verify complete scene delivery'} · use Continue this scene to resume from the exact final state`)
        } else if (result.refined) {
          setStatus(`Scene complete · backend delivery verified · Craft Pass applied · ${words.toLocaleString()} words`)
        } else {
          setStatus(`Scene complete · backend delivery verified · ${words.toLocaleString()} words`)
        }
        return
      }

      const result = await requestGeneration(direction, modeCopy.mode)
      setOutput(result.text)
      setContextFiles(result.context_files || [])
      const words = wordsIn(result.text)
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
      streamSessionRef.current = null
      setStreamingDraft(false)
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
        <StudioModelRouter
          provider={provider}
          models={models}
          studioMode={studioMode}
          heatLevel={craft.heat_level}
          prompt={prompt}
          busy={busy}
          onProviderChange={setProvider}
          onRefresh={refreshModels}
        />
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
              <span className="ai-studio-independent">{studioMode === 'scene' && output ? 'Current Studio draft available to Continue' : 'No manuscript retrieval'}</span>
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
            {studioMode === 'scene' && output.trim() && (
              <button className="ai-studio-generate ai-studio-continue" type="button" onClick={() => void continueCurrentScene('Continue immediately from the exact final line and finish this scene.')} disabled={busy || !provider.model}>
                Continue this scene
              </button>
            )}
          </div>

          <div className="ai-studio-card ai-studio-output">
            <div className="ai-studio-card-head">
              <div><small>AI OUTPUT</small><h2>Working Draft</h2></div>
              <div className="ai-studio-output-meta">
                <span>{streamingDraft ? 'LIVE · UNVERIFIED' : `${wordCount.toLocaleString()} words`}</span>
                {output && !busy && (
                  <button
                    type="button"
                    className="quiet"
                    onClick={() => {
                      if (window.confirm('Clear the current Studio working draft?')) {
                        setOutput('')
                        setSceneBrief('')
                        setContextFiles([])
                        setStatus('Working Draft cleared')
                      }
                    }}
                  >
                    Clear draft
                  </button>
                )}
              </div>
            </div>
            {output ? (
              <textarea
                className="ai-studio-prose ai-studio-prose-editor"
                value={output}
                onChange={(event) => setOutput(event.target.value)}
                readOnly={busy}
                rows={24}
                spellCheck
                aria-label="Studio Working Draft"
              />
            ) : (
              <div className="ai-studio-empty">Your generated scene, brainstorm, or creative exploration will stream into this Working Draft as Ember writes.</div>
            )}
            {contextFiles.length > 0 && <details><summary>Studio context used ({contextFiles.length})</summary>{contextFiles.map((file) => <div key={file}>{file}</div>)}</details>}
          </div>
        </div>

        <aside className="ai-studio-sidebar">
          <div className="ai-studio-card">
            <small>CREATIVE SCRATCHPAD</small>
            <h2>Your thoughts</h2>
            <p>Capture fragments, alternate beats, dialogue, reminders, or notes without changing the manuscript.</p>
            <textarea value={scratchpad} onChange={(event) => setScratchpad(event.target.value)} placeholder="Private working notes for this idea…" rows={12} />
            {scratchpad && <button type="button" className="quiet ai-studio-clear" onClick={() => { if (window.confirm('Clear the Studio scratchpad?')) setScratchpad('') }}>Clear scratchpad</button>}
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
