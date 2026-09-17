import { useEffect, useMemo, useState } from 'react'

import ChemistryPanel, { type AftermathProposal, type ChemistryProfile } from './ChemistryPanel'
import CraftPanel, {
  type CraftControls,
  type CraftProfile,
  type VoiceProfile,
} from './CraftPanel'
import MemoryPanel, { type MemoryFact, type MemoryStats } from './MemoryPanel'
import StoryIntelligencePanel, { type StoryIntelligence } from './StoryIntelligencePanel'
import VersionHistoryPanel from './VersionHistoryPanel'
import type { ProviderConfig, WorkspaceProject } from './workspace-types'
import './tools-notes.css'

type Props = {
  apiBase: string
  project: WorkspaceProject
  onOpenSource: (path: string, anchor?: string) => void
}

type ToolTab = 'history' | 'memory' | 'relationships' | 'settings'
type ProjectDetail = { files: string[] }
type AnalyzeResult = { summary: string; facts_written: number; skipped: boolean }

const defaultProvider: ProviderConfig = {
  provider: 'ollama',
  base_url: 'http://localhost:11434',
  model: '',
  api_key: '',
}

const defaultCraftProfile: CraftProfile = {
  default_heat: 'hot',
  default_tension_curve: 'slow_burn',
  quality_pass_default: false,
  prose_directive: '',
  avoidances: [],
}

const defaultCraftControls: CraftControls = {
  heat_level: 'hot',
  tension_curve: 'slow_burn',
  voice_lock: true,
  quality_pass: false,
  sensory_intensity: 3,
  dialogue_intensity: 3,
  interiority: 3,
}

const emptyStats: MemoryStats = { facts: 0, documents: 0, by_kind: {} }
const emptyIntelligence: StoryIntelligence = { characters: [], relationships: [] }

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

function readStoredProvider(): ProviderConfig {
  try {
    return { ...defaultProvider, ...JSON.parse(localStorage.getItem('emberwriter.provider') || '{}') }
  } catch {
    return defaultProvider
  }
}

function readStoredCraft(): CraftControls {
  try {
    return { ...defaultCraftControls, ...JSON.parse(localStorage.getItem('emberwriter.craftControls') || '{}') }
  } catch {
    return defaultCraftControls
  }
}

export default function ToolsWorkspace({ apiBase, project, onOpenSource }: Props) {
  const [tab, setTab] = useState<ToolTab>('history')
  const [provider, setProvider] = useState<ProviderConfig>(readStoredProvider)
  const [models, setModels] = useState<string[]>([])
  const [craftControls, setCraftControls] = useState<CraftControls>(readStoredCraft)
  const [craftProfile, setCraftProfile] = useState<CraftProfile>(defaultCraftProfile)
  const [voiceProfile, setVoiceProfile] = useState<VoiceProfile | null>(null)
  const [facts, setFacts] = useState<MemoryFact[]>([])
  const [stats, setStats] = useState<MemoryStats>(emptyStats)
  const [intelligence, setIntelligence] = useState<StoryIntelligence>(emptyIntelligence)
  const [memoryQuery, setMemoryQuery] = useState('')
  const [autoMemory, setAutoMemory] = useState(() => localStorage.getItem('emberwriter.autoMemory') !== 'false')
  const [files, setFiles] = useState<string[]>([])
  const [chemistry, setChemistry] = useState<ChemistryProfile[]>([])
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState('')
  const [historyToken, setHistoryToken] = useState(0)

  const manuscriptFiles = useMemo(() => files.filter((path) => path.startsWith('manuscript/')), [files])
  const characterNames = useMemo(() => intelligence.characters.map((character) => character.name), [intelligence.characters])

  useEffect(() => {
    localStorage.setItem('emberwriter.provider', JSON.stringify(provider))
    window.dispatchEvent(new CustomEvent('emberwriter:settings-changed'))
  }, [provider])

  useEffect(() => {
    localStorage.setItem('emberwriter.craftControls', JSON.stringify(craftControls))
  }, [craftControls])

  useEffect(() => {
    localStorage.setItem('emberwriter.autoMemory', String(autoMemory))
    window.dispatchEvent(new CustomEvent('emberwriter:auto-memory-changed', { detail: autoMemory }))
  }, [autoMemory])

  useEffect(() => {
    void loadAll()
  }, [project.slug])

  useEffect(() => {
    const timer = window.setTimeout(() => void refreshMemory(memoryQuery), 180)
    return () => window.clearTimeout(timer)
  }, [memoryQuery, project.slug])

  async function loadAll() {
    setStatus('Loading project tools…')
    const results = await Promise.allSettled([
      request<ProjectDetail>(`${apiBase}/projects/${project.slug}`),
      request<CraftProfile>(`${apiBase}/projects/${project.slug}/craft-profile`),
      request<VoiceProfile | null>(`${apiBase}/projects/${project.slug}/voice-profile`),
      request<ChemistryProfile[]>(`${apiBase}/projects/${project.slug}/chemistry`),
      refreshMemory(''),
      refreshModels(),
    ])
    const [detail, craft, voice, chemistryResult] = results
    if (detail.status === 'fulfilled') setFiles(detail.value.files)
    if (craft.status === 'fulfilled') setCraftProfile(craft.value)
    if (voice.status === 'fulfilled') setVoiceProfile(voice.value)
    if (chemistryResult.status === 'fulfilled') setChemistry(chemistryResult.value)
    const rejected = results.find((result) => result.status === 'rejected')
    setStatus(rejected?.status === 'rejected' ? `Some tools could not load: ${(rejected.reason as Error).message}` : '')
  }

  async function refreshModels() {
    if (!provider.base_url.trim()) return
    try {
      const result = await request<{ models: string[] }>(`${apiBase}/models`, {
        method: 'POST',
        body: JSON.stringify(provider),
      })
      setModels(result.models)
      if (!provider.model && result.models[0]) setProvider((current) => ({ ...current, model: result.models[0] }))
    } catch (cause) {
      setStatus(`Model server: ${(cause as Error).message}`)
    }
  }

  async function refreshMemory(query = memoryQuery) {
    const suffix = query.trim() ? `?query=${encodeURIComponent(query.trim())}` : ''
    try {
      const [nextFacts, nextStats, nextIntelligence] = await Promise.all([
        request<MemoryFact[]>(`${apiBase}/projects/${project.slug}/memory${suffix}`),
        request<MemoryStats>(`${apiBase}/projects/${project.slug}/memory/stats`),
        request<StoryIntelligence>(`${apiBase}/projects/${project.slug}/story-intelligence`),
      ])
      setFacts(nextFacts)
      setStats(nextStats)
      setIntelligence(nextIntelligence)
    } catch (cause) {
      setStatus(`Story memory: ${(cause as Error).message}`)
    }
  }

  async function analyzePath(path: string, force: boolean) {
    return request<AnalyzeResult>(`${apiBase}/projects/${project.slug}/memory/analyze`, {
      method: 'POST',
      body: JSON.stringify({ path, provider, force }),
    })
  }

  async function analyzeCurrent() {
    if (!project.activePath.startsWith('manuscript/') || !provider.model || busy) return
    setBusy(true)
    setStatus(`Analyzing ${project.activePath}…`)
    try {
      const result = await analyzePath(project.activePath, true)
      await refreshMemory(memoryQuery)
      setStatus(result.skipped ? 'Story Memory was already current.' : `Remembered ${result.facts_written} story facts.`)
    } catch (cause) {
      setStatus(`Memory analysis failed: ${(cause as Error).message}`)
    } finally {
      setBusy(false)
    }
  }

  async function analyzeAll() {
    if (!provider.model || !manuscriptFiles.length || busy) return
    setBusy(true)
    let learned = 0
    try {
      for (const [index, path] of manuscriptFiles.entries()) {
        setStatus(`Building Story Memory ${index + 1}/${manuscriptFiles.length} · ${path}`)
        const result = await analyzePath(path, false)
        if (!result.skipped) learned += result.facts_written
      }
      await refreshMemory(memoryQuery)
      setStatus(`Story Memory updated · ${learned} new facts.`)
    } catch (cause) {
      setStatus(`Memory build stopped: ${(cause as Error).message}`)
    } finally {
      setBusy(false)
    }
  }

  async function saveCraftProfile(profile: CraftProfile) {
    try {
      const saved = await request<CraftProfile>(`${apiBase}/projects/${project.slug}/craft-profile`, {
        method: 'PUT',
        body: JSON.stringify(profile),
      })
      setCraftProfile(saved)
      setStatus('Craft defaults saved.')
    } catch (cause) {
      setStatus(`Could not save craft defaults: ${(cause as Error).message}`)
    }
  }

  async function activeText() {
    if (!project.activePath) return ''
    const response = await request<{ content: string }>(`${apiBase}/projects/${project.slug}/file?path=${encodeURIComponent(project.activePath)}`)
    return response.content
  }

  async function analyzeVoice(profileName: string) {
    if (!provider.model || busy) return
    setBusy(true)
    setStatus('Learning book voice from the active document…')
    try {
      const sample = (await activeText()).trim()
      if (sample.length < 200) throw new Error('The active document needs at least 200 characters for Voice Lab.')
      const result = await request<{ profile: VoiceProfile }>(`${apiBase}/projects/${project.slug}/voice/analyze`, {
        method: 'POST',
        body: JSON.stringify({ sample_text: sample, provider, profile_name: profileName }),
      })
      setVoiceProfile(result.profile)
      setStatus('Voice profile learned and saved.')
    } catch (cause) {
      setStatus(`Voice Lab: ${(cause as Error).message}`)
    } finally {
      setBusy(false)
    }
  }

  async function refreshChemistry() {
    try {
      setChemistry(await request<ChemistryProfile[]>(`${apiBase}/projects/${project.slug}/chemistry`))
    } catch (cause) {
      setStatus(`Relationship chemistry: ${(cause as Error).message}`)
    }
  }

  async function inferChemistry(participants: string[], authorDirection: string) {
    if (!provider.model || busy) return null
    setBusy(true)
    setStatus(`Building chemistry for ${participants.join(' + ')}…`)
    try {
      const result = await request<{ profile: ChemistryProfile }>(`${apiBase}/projects/${project.slug}/chemistry/infer`, {
        method: 'POST',
        body: JSON.stringify({ participants, author_direction: authorDirection, provider, save: true }),
      })
      await refreshChemistry()
      setStatus('Relationship chemistry updated.')
      return result.profile
    } catch (cause) {
      setStatus(`Chemistry analysis failed: ${(cause as Error).message}`)
      return null
    } finally {
      setBusy(false)
    }
  }

  async function saveChemistry(profile: ChemistryProfile) {
    if (busy) return null
    setBusy(true)
    try {
      const saved = await request<ChemistryProfile>(`${apiBase}/projects/${project.slug}/chemistry`, {
        method: 'PUT',
        body: JSON.stringify(profile),
      })
      await refreshChemistry()
      setStatus(`Chemistry saved for ${saved.participants.join(' + ')}.`)
      return saved
    } catch (cause) {
      setStatus(`Could not save chemistry: ${(cause as Error).message}`)
      return null
    } finally {
      setBusy(false)
    }
  }

  async function analyzeAftermath(participants: string[]) {
    if (!provider.model || !project.activePath || busy) return null
    setBusy(true)
    setStatus('Analyzing relationship aftermath from the active document…')
    try {
      const sceneText = (await activeText()).trim()
      if (sceneText.length < 200) throw new Error('The active document needs at least 200 characters.')
      const proposal = await request<AftermathProposal>(`${apiBase}/projects/${project.slug}/aftermath/analyze`, {
        method: 'POST',
        body: JSON.stringify({ scene_text: sceneText, provider, source_path: project.activePath, participants }),
      })
      setStatus('Aftermath proposal ready for review.')
      return proposal
    } catch (cause) {
      setStatus(`Aftermath analysis failed: ${(cause as Error).message}`)
      return null
    } finally {
      setBusy(false)
    }
  }

  async function applyAftermath(proposal: AftermathProposal) {
    if (busy) return false
    setBusy(true)
    try {
      await request(`${apiBase}/projects/${project.slug}/aftermath/apply`, {
        method: 'POST',
        body: JSON.stringify(proposal),
      })
      await Promise.all([refreshChemistry(), refreshMemory(memoryQuery)])
      setStatus('Reviewed relationship changes applied.')
      return true
    } catch (cause) {
      setStatus(`Could not apply aftermath: ${(cause as Error).message}`)
      return false
    } finally {
      setBusy(false)
    }
  }

  async function restored() {
    setHistoryToken((value) => value + 1)
    if (project.activePath) onOpenSource(project.activePath)
  }

  return (
    <section className="center-tool tools-workspace">
      <header className="center-tool-header">
        <div>
          <small>TOOLS · {project.name}</small>
          <h1>Project Tools</h1>
          <p>The utilities that used to crowd the right rail now live here. Studio is the only AI-writing interface; these tools support the manuscript without shrinking it.</p>
        </div>
      </header>

      <nav className="center-subtabs" aria-label="Project tools">
        <button type="button" className={tab === 'history' ? 'active' : ''} onClick={() => setTab('history')}>History</button>
        <button type="button" className={tab === 'memory' ? 'active' : ''} onClick={() => setTab('memory')}>Story Memory <span>{stats.facts}</span></button>
        <button type="button" className={tab === 'relationships' ? 'active' : ''} onClick={() => setTab('relationships')}>Relationships <span>{chemistry.length}</span></button>
        <button type="button" className={tab === 'settings' ? 'active' : ''} onClick={() => setTab('settings')}>Craft & Model</button>
      </nav>

      {tab === 'history' && (
        <div className="tool-surface">
          <div className="center-section-heading"><div><h2>Document History</h2><p>{project.activePath || 'Open a manuscript document in Write to inspect its revisions.'}</p></div></div>
          {project.activePath ? (
            <VersionHistoryPanel apiBase={apiBase} slug={project.slug} path={project.activePath} disabled={busy} refreshToken={historyToken} onRestored={restored} />
          ) : <div className="center-empty">Choose a Binder document in Write, then return here to compare or restore revisions.</div>}
        </div>
      )}

      {tab === 'memory' && (
        <div className="tools-two-column">
          <StoryIntelligencePanel intelligence={intelligence} onRefresh={() => void refreshMemory(memoryQuery)} onOpenSource={(path) => onOpenSource(path)} />
          <MemoryPanel
            facts={facts}
            stats={stats}
            query={memoryQuery}
            autoMemory={autoMemory}
            busy={busy}
            canAnalyze={project.activePath.startsWith('manuscript/') && Boolean(provider.model)}
            canAnalyzeAll={manuscriptFiles.length > 0 && Boolean(provider.model)}
            onQueryChange={setMemoryQuery}
            onAutoMemoryChange={setAutoMemory}
            onAnalyze={() => void analyzeCurrent()}
            onAnalyzeAll={() => void analyzeAll()}
            onRefresh={() => void refreshMemory(memoryQuery)}
            onOpenSource={(path) => onOpenSource(path)}
          />
        </div>
      )}

      {tab === 'relationships' && (
        <div className="tool-surface">
          <ChemistryPanel
            characterNames={characterNames}
            profiles={chemistry}
            disabled={busy || !provider.model}
            canAnalyzeScene={Boolean(project.activePath)}
            onInfer={inferChemistry}
            onSave={saveChemistry}
            onAnalyzeAftermath={analyzeAftermath}
            onApplyAftermath={applyAftermath}
          />
        </div>
      )}

      {tab === 'settings' && (
        <div className="tools-settings-grid">
          <section className="tool-surface model-tool-card">
            <div className="center-section-heading"><div><h2>AI Model</h2><p>One provider configuration is shared by Studio and the project tools.</p></div></div>
            <label>Provider
              <select value={provider.provider} onChange={(event) => setProvider({ ...provider, provider: event.target.value as ProviderConfig['provider'] })}>
                <option value="ollama">Ollama</option>
                <option value="openai_compatible">OpenAI-compatible</option>
              </select>
            </label>
            <label>Server<input value={provider.base_url} onChange={(event) => setProvider({ ...provider, base_url: event.target.value })} /></label>
            <label>Model
              <div className="tool-model-row">
                <input list="tools-model-list" value={provider.model} onChange={(event) => setProvider({ ...provider, model: event.target.value })} placeholder="Choose or type model" />
                <button type="button" onClick={() => void refreshModels()} disabled={busy}>↻</button>
              </div>
            </label>
            <datalist id="tools-model-list">{models.map((model) => <option key={model} value={model} />)}</datalist>
            {provider.provider === 'openai_compatible' && <label>API key<input type="password" value={provider.api_key || ''} onChange={(event) => setProvider({ ...provider, api_key: event.target.value })} /></label>}
          </section>

          <section className="tool-surface craft-tool-card">
            <CraftPanel
              controls={craftControls}
              profile={craftProfile}
              voiceProfile={voiceProfile}
              disabled={busy || !provider.model}
              sampleAvailable={Boolean(project.activePath)}
              onControlsChange={setCraftControls}
              onSaveProfile={saveCraftProfile}
              onAnalyzeVoice={analyzeVoice}
            />
          </section>
        </div>
      )}

      {status && <div className="tools-status" role="status">{status}</div>}
    </section>
  )
}
