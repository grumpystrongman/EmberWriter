import { useEffect, useMemo, useRef, useState } from 'react'

import BinderPanel, {
  type BinderNode,
  type BinderNodeKind,
  type BinderState,
} from './BinderPanel'
import ChemistryPanel, {
  type AftermathProposal,
  type ChemistryProfile,
} from './ChemistryPanel'
import CraftPanel, {
  type CraftControls,
  type CraftProfile,
  type VoiceProfile,
} from './CraftPanel'
import ImportPanel from './ImportPanel'
import MemoryPanel, { type MemoryFact, type MemoryStats } from './MemoryPanel'
import PublishPanel from './PublishPanel'
import RichTextEditor, { type RichEditorHandle } from './RichTextEditor'
import SceneArchitectPanel, { type ScenePlan, type ScenePlanResponse } from './SceneArchitectPanel'
import StoryIntelligencePanel, { type StoryIntelligence } from './StoryIntelligencePanel'
import VersionHistoryPanel from './VersionHistoryPanel'
import './authoring.css'

const API = 'http://127.0.0.1:8000/api'

type ProjectSummary = {
  slug: string
  name: string
  description: string
  updated_at: string
}

type ProjectDetail = ProjectSummary & {
  files: string[]
  content_profile: Record<string, unknown>
}

type Provider = {
  provider: 'ollama' | 'openai_compatible'
  base_url: string
  model: string
  api_key?: string
}

type AnalyzeResult = {
  summary: string
  facts_written: number
  skipped: boolean
}

type SceneArchitectInput = {
  prompt: string
  pov: string
  participants: string[]
  location: string
  desired_heat: string
}

type BinderCreateInput = {
  title: string
  kind: BinderNodeKind
  parent_id: string | null
}

type ImportMode = 'novel' | 'portion' | 'idea' | 'research'
type Mode = 'write' | 'continue' | 'rewrite' | 'brainstorm' | 'critic' | 'continuity'

const defaultProvider: Provider = {
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

const emptyMemoryStats: MemoryStats = { facts: 0, documents: 0, by_kind: {} }
const emptyStoryIntelligence: StoryIntelligence = { characters: [], relationships: [] }

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
      // Keep HTTP status text.
    }
    throw new Error(detail)
  }
  return response.json() as Promise<T>
}

function firstDraftPath(state: BinderState): string {
  const nodes = new Map(state.nodes.map((node) => [node.id, node]))
  const draft = state.roots.map((id) => nodes.get(id)).find((node) => node?.title === 'Draft')
  if (!draft) return ''
  const children = new Map<string, BinderNode[]>()
  for (const node of state.nodes) {
    if (!node.parent_id) continue
    const list = children.get(node.parent_id) || []
    list.push(node)
    children.set(node.parent_id, list)
  }
  for (const list of children.values()) list.sort((a, b) => a.position - b.position)
  function visit(nodeId: string): string {
    for (const child of children.get(nodeId) || []) {
      if (child.path && !child.custom_metadata.source_missing) return child.path
      const nested = visit(child.id)
      if (nested) return nested
    }
    return ''
  }
  return visit(draft.id)
}

export default function AppV2() {
  const [projects, setProjects] = useState<ProjectSummary[]>([])
  const [project, setProject] = useState<ProjectDetail | null>(null)
  const [binderState, setBinderState] = useState<BinderState | null>(null)
  const [activeFile, setActiveFile] = useState('')
  const [content, setContent] = useState('')
  const [dirty, setDirty] = useState(false)
  const [newProjectName, setNewProjectName] = useState('')
  const [prompt, setPrompt] = useState('')
  const [mode, setMode] = useState<Mode>('continue')
  const [output, setOutput] = useState('')
  const [contextFiles, setContextFiles] = useState<string[]>([])
  const [models, setModels] = useState<string[]>([])
  const [busy, setBusy] = useState(false)
  const [memoryBusy, setMemoryBusy] = useState(false)
  const [sceneBusy, setSceneBusy] = useState(false)
  const [craftBusy, setCraftBusy] = useState(false)
  const [chemistryBusy, setChemistryBusy] = useState(false)
  const [binderBusy, setBinderBusy] = useState(false)
  const [importBusy, setImportBusy] = useState(false)
  const [memoryFacts, setMemoryFacts] = useState<MemoryFact[]>([])
  const [memoryStats, setMemoryStats] = useState<MemoryStats>(emptyMemoryStats)
  const [storyIntelligence, setStoryIntelligence] = useState<StoryIntelligence>(emptyStoryIntelligence)
  const [craftProfile, setCraftProfile] = useState<CraftProfile>(defaultCraftProfile)
  const [voiceProfile, setVoiceProfile] = useState<VoiceProfile | null>(null)
  const [chemistryProfiles, setChemistryProfiles] = useState<ChemistryProfile[]>([])
  const [memoryQuery, setMemoryQuery] = useState('')
  const [status, setStatus] = useState('Ready')
  const [revisionToken, setRevisionToken] = useState(0)
  const [provider, setProvider] = useState<Provider>(() => {
    const stored = localStorage.getItem('emberwriter.provider')
    return stored ? { ...defaultProvider, ...JSON.parse(stored) } : defaultProvider
  })
  const [craftControls, setCraftControls] = useState<CraftControls>(() => {
    const stored = localStorage.getItem('emberwriter.craftControls')
    return stored ? { ...defaultCraftControls, ...JSON.parse(stored) } : defaultCraftControls
  })
  const [autoMemory, setAutoMemory] = useState(() => {
    const stored = localStorage.getItem('emberwriter.autoMemory')
    return stored === null ? true : stored === 'true'
  })
  const editorRef = useRef<RichEditorHandle>(null)
  const lastAutoMemoryRef = useRef('')

  const manuscriptFiles = useMemo(
    () => project?.files.filter((file) => file.startsWith('manuscript/')) ?? [],
    [project],
  )
  const characterNames = useMemo(
    () => storyIntelligence.characters.map((character) => character.name),
    [storyIntelligence],
  )
  const modelOccupied = busy || memoryBusy || sceneBusy || craftBusy || chemistryBusy
  const workspaceBusy = modelOccupied || binderBusy || importBusy

  useEffect(() => { void refreshProjects() }, [])
  useEffect(() => { localStorage.setItem('emberwriter.provider', JSON.stringify(provider)) }, [provider])
  useEffect(() => { localStorage.setItem('emberwriter.craftControls', JSON.stringify(craftControls)) }, [craftControls])
  useEffect(() => { localStorage.setItem('emberwriter.autoMemory', String(autoMemory)) }, [autoMemory])

  useEffect(() => {
    if (!dirty || !project || !activeFile) return
    const timer = window.setTimeout(() => void saveActiveFile(), 900)
    return () => window.clearTimeout(timer)
  }, [content, dirty, project?.slug, activeFile])

  useEffect(() => {
    if (!project) return
    const timer = window.setTimeout(() => void refreshMemory(project.slug, memoryQuery), 250)
    return () => window.clearTimeout(timer)
  }, [memoryQuery, project?.slug])

  useEffect(() => {
    if (!autoMemory || !project || !activeFile.startsWith('manuscript/') || !provider.model || dirty || modelOccupied) return
    const key = `${project.slug}\u0000${activeFile}\u0000${content}`
    if (lastAutoMemoryRef.current === key) return
    const timer = window.setTimeout(() => {
      lastAutoMemoryRef.current = key
      void analyzeActiveFile(false)
    }, 4500)
    return () => window.clearTimeout(timer)
  }, [autoMemory, project?.slug, activeFile, content, provider.model, provider.provider, provider.base_url, dirty, modelOccupied])

  async function refreshProjects() {
    try {
      setProjects(await jsonFetch<ProjectSummary[]>(`${API}/projects`))
    } catch (error) {
      setStatus(`API offline: ${(error as Error).message}`)
    }
  }

  async function refreshProjectDetail(slug = project?.slug) {
    if (!slug) return null
    const detail = await jsonFetch<ProjectDetail>(`${API}/projects/${slug}`)
    setProject(detail)
    return detail
  }

  async function refreshBinder(slug = project?.slug): Promise<BinderState | null> {
    if (!slug) return null
    try {
      const state = await jsonFetch<BinderState>(`${API}/projects/${slug}/binder`)
      setBinderState(state)
      return state
    } catch (error) {
      setStatus(`Binder unavailable: ${(error as Error).message}`)
      return null
    }
  }

  async function refreshMemory(slug = project?.slug, query = memoryQuery) {
    if (!slug) return
    try {
      const suffix = query.trim() ? `?query=${encodeURIComponent(query.trim())}` : ''
      const [facts, stats, intelligence] = await Promise.all([
        jsonFetch<MemoryFact[]>(`${API}/projects/${slug}/memory${suffix}`),
        jsonFetch<MemoryStats>(`${API}/projects/${slug}/memory/stats`),
        jsonFetch<StoryIntelligence>(`${API}/projects/${slug}/story-intelligence`),
      ])
      setMemoryFacts(facts)
      setMemoryStats(stats)
      setStoryIntelligence(intelligence)
    } catch (error) {
      setStatus(`Story intelligence unavailable: ${(error as Error).message}`)
    }
  }

  async function refreshCraft(slug: string) {
    try {
      const [profile, voice] = await Promise.all([
        jsonFetch<CraftProfile>(`${API}/projects/${slug}/craft-profile`),
        jsonFetch<VoiceProfile | null>(`${API}/projects/${slug}/voice-profile`),
      ])
      setCraftProfile(profile)
      setVoiceProfile(voice)
      setCraftControls((current) => ({
        ...current,
        heat_level: profile.default_heat,
        tension_curve: profile.default_tension_curve,
        quality_pass: profile.quality_pass_default,
      }))
    } catch (error) {
      setStatus(`Craft profile unavailable: ${(error as Error).message}`)
    }
  }

  async function refreshChemistry(slug = project?.slug) {
    if (!slug) return
    try {
      setChemistryProfiles(await jsonFetch<ChemistryProfile[]>(`${API}/projects/${slug}/chemistry`))
    } catch (error) {
      setStatus(`Relationship chemistry unavailable: ${(error as Error).message}`)
    }
  }

  async function openProject(slug: string) {
    setStatus('Opening project…')
    try {
      const [detail, binder] = await Promise.all([
        jsonFetch<ProjectDetail>(`${API}/projects/${slug}`),
        jsonFetch<BinderState>(`${API}/projects/${slug}/binder`),
      ])
      setProject(detail)
      setBinderState(binder)
      setMemoryQuery('')
      const first = firstDraftPath(binder) || detail.files.find((file) => file.startsWith('manuscript/')) || detail.files[0] || ''
      if (first) await openFile(detail.slug, first)
      await Promise.all([refreshMemory(detail.slug, ''), refreshCraft(detail.slug), refreshChemistry(detail.slug)])
      setStatus('Project loaded')
    } catch (error) {
      setStatus((error as Error).message)
    }
  }

  async function createProject() {
    if (!newProjectName.trim()) return
    setBusy(true)
    try {
      const detail = await jsonFetch<ProjectDetail>(`${API}/projects`, {
        method: 'POST',
        body: JSON.stringify({ name: newProjectName.trim(), description: '' }),
      })
      setNewProjectName('')
      await refreshProjects()
      await openProject(detail.slug)
    } catch (error) {
      setStatus((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function openFile(slug: string, path: string) {
    try {
      const data = await jsonFetch<{ path: string; content: string }>(`${API}/projects/${slug}/file?path=${encodeURIComponent(path)}`)
      setActiveFile(path)
      setContent(data.content)
      setDirty(false)
      lastAutoMemoryRef.current = ''
      setRevisionToken((value) => value + 1)
      setStatus(path)
    } catch (error) {
      setStatus((error as Error).message)
    }
  }

  async function saveActiveFile() {
    if (!project || !activeFile || !dirty) return
    try {
      await jsonFetch(`${API}/projects/${project.slug}/file?path=${encodeURIComponent(activeFile)}`, {
        method: 'PUT',
        body: JSON.stringify({ content }),
      })
      setDirty(false)
      setRevisionToken((value) => value + 1)
      void refreshBinder(project.slug)
      setStatus(`Saved ${activeFile}`)
    } catch (error) {
      setStatus(`Save failed: ${(error as Error).message}`)
    }
  }

  async function createBinderNode(input: BinderCreateInput) {
    if (!project || binderBusy) return
    setBinderBusy(true)
    const before = new Set(binderState?.nodes.map((node) => node.id) || [])
    try {
      const state = await jsonFetch<BinderState>(`${API}/projects/${project.slug}/binder/nodes`, {
        method: 'POST',
        body: JSON.stringify(input),
      })
      setBinderState(state)
      await refreshProjectDetail(project.slug)
      const created = state.nodes.find((node) => !before.has(node.id))
      if (created?.path) await openFile(project.slug, created.path)
      setStatus(`Added ${input.title} to Binder`)
    } catch (error) {
      setStatus(`Binder create failed: ${(error as Error).message}`)
    } finally {
      setBinderBusy(false)
    }
  }

  async function updateBinderNode(nodeId: string, patch: Record<string, unknown>) {
    if (!project || binderBusy) return
    setBinderBusy(true)
    try {
      setBinderState(await jsonFetch<BinderState>(`${API}/projects/${project.slug}/binder/nodes/${nodeId}`, {
        method: 'PUT',
        body: JSON.stringify(patch),
      }))
      setStatus('Binder metadata saved')
    } catch (error) {
      setStatus(`Binder update failed: ${(error as Error).message}`)
    } finally {
      setBinderBusy(false)
    }
  }

  async function reorderBinder(parentId: string | null, nodeIds: string[]) {
    if (!project || binderBusy) return
    setBinderBusy(true)
    try {
      setBinderState(await jsonFetch<BinderState>(`${API}/projects/${project.slug}/binder/reorder`, {
        method: 'POST',
        body: JSON.stringify({ parent_id: parentId, node_ids: nodeIds }),
      }))
      setStatus('Binder order updated')
    } catch (error) {
      setStatus(`Binder reorder failed: ${(error as Error).message}`)
    } finally {
      setBinderBusy(false)
    }
  }

  async function trashBinderNode(nodeId: string) {
    if (!project || binderBusy) return
    setBinderBusy(true)
    try {
      setBinderState(await jsonFetch<BinderState>(`${API}/projects/${project.slug}/binder/nodes/${nodeId}/trash`, { method: 'POST' }))
      setStatus('Moved Binder item to Trash; source file preserved')
    } catch (error) {
      setStatus(`Binder Trash failed: ${(error as Error).message}`)
    } finally {
      setBinderBusy(false)
    }
  }

  async function restoreBinderNode(nodeId: string) {
    if (!project || binderBusy) return
    setBinderBusy(true)
    try {
      setBinderState(await jsonFetch<BinderState>(`${API}/projects/${project.slug}/binder/nodes/${nodeId}/restore`, { method: 'POST' }))
      setStatus('Binder item restored')
    } catch (error) {
      setStatus(`Binder restore failed: ${(error as Error).message}`)
    } finally {
      setBinderBusy(false)
    }
  }

  async function syncBinder() {
    if (!project || binderBusy) return
    setBinderBusy(true)
    setStatus('Synchronizing Binder with project files…')
    try {
      setBinderState(await jsonFetch<BinderState>(`${API}/projects/${project.slug}/binder/sync`, { method: 'POST' }))
      await refreshProjectDetail(project.slug)
      setStatus('Binder synchronized')
    } catch (error) {
      setStatus(`Binder sync failed: ${(error as Error).message}`)
    } finally {
      setBinderBusy(false)
    }
  }

  async function importFiles(files: File[], importMode: ImportMode): Promise<BinderState | null> {
    if (!project || importBusy) return null
    setImportBusy(true)
    setStatus(`Importing ${files.length} file${files.length === 1 ? '' : 's'}…`)
    try {
      const form = new FormData()
      files.forEach((file) => form.append('files', file))
      form.append('mode', importMode)
      const response = await fetch(`${API}/projects/${project.slug}/import/files`, { method: 'POST', body: form })
      if (!response.ok) {
        const body = await response.json().catch(() => ({}))
        throw new Error(body.detail || `${response.status} ${response.statusText}`)
      }
      const result = await response.json() as {
        imports: { documents: { path: string }[] }[]
        documents: number
        words: number
        binder: BinderState
      }
      setBinderState(result.binder)
      await refreshProjectDetail(project.slug)
      const first = result.imports.flatMap((item) => item.documents)[0]?.path
      if (first) await openFile(project.slug, first)
      setRevisionToken((value) => value + 1)
      setStatus(`Imported ${result.documents} document${result.documents === 1 ? '' : 's'} · ${result.words.toLocaleString()} words`)
      return result.binder
    } catch (error) {
      setStatus(`Import failed: ${(error as Error).message}`)
      return null
    } finally {
      setImportBusy(false)
    }
  }

  async function importText(title: string, text: string, importMode: ImportMode): Promise<BinderState | null> {
    if (!project || importBusy) return null
    setImportBusy(true)
    setStatus('Importing pasted material…')
    try {
      const result = await jsonFetch<{ documents: { path: string }[]; total_words: number; binder: BinderState }>(
        `${API}/projects/${project.slug}/import/text`,
        { method: 'POST', body: JSON.stringify({ title, content: text, mode: importMode }) },
      )
      setBinderState(result.binder)
      await refreshProjectDetail(project.slug)
      if (result.documents[0]?.path) await openFile(project.slug, result.documents[0].path)
      setRevisionToken((value) => value + 1)
      setStatus(`Imported ${result.documents.length} document${result.documents.length === 1 ? '' : 's'} · ${result.total_words.toLocaleString()} words`)
      return result.binder
    } catch (error) {
      setStatus(`Import failed: ${(error as Error).message}`)
      return null
    } finally {
      setImportBusy(false)
    }
  }

  async function refreshModels() {
    setBusy(true)
    setStatus('Checking model server…')
    try {
      const result = await jsonFetch<{ models: string[] }>(`${API}/models`, {
        method: 'POST',
        body: JSON.stringify(provider),
      })
      setModels(result.models)
      if (!provider.model && result.models[0]) setProvider({ ...provider, model: result.models[0] })
      setStatus(`Found ${result.models.length} model${result.models.length === 1 ? '' : 's'}`)
    } catch (error) {
      setStatus((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function analyzeActiveFile(force = true) {
    if (!project || !activeFile.startsWith('manuscript/') || !provider.model || modelOccupied) return
    setMemoryBusy(true)
    setStatus(`Analyzing ${activeFile} for story memory…`)
    try {
      if (dirty) await saveActiveFile()
      const result = await jsonFetch<AnalyzeResult>(`${API}/projects/${project.slug}/memory/analyze`, {
        method: 'POST',
        body: JSON.stringify({ path: activeFile, provider, force }),
      })
      await refreshMemory(project.slug, memoryQuery)
      setStatus(result.skipped ? `Memory already current for ${activeFile}` : `Remembered ${result.facts_written} story facts from ${activeFile}`)
    } catch (error) {
      setStatus(`Memory analysis failed: ${(error as Error).message}`)
    } finally {
      setMemoryBusy(false)
    }
  }

  async function analyzeAllManuscript() {
    if (!project || !provider.model || manuscriptFiles.length === 0 || modelOccupied) return
    setMemoryBusy(true)
    let learned = 0
    let analyzed = 0
    let skipped = 0
    try {
      if (dirty) await saveActiveFile()
      for (const [index, path] of manuscriptFiles.entries()) {
        setStatus(`Building story memory ${index + 1}/${manuscriptFiles.length}: ${path}`)
        const result = await jsonFetch<AnalyzeResult>(`${API}/projects/${project.slug}/memory/analyze`, {
          method: 'POST',
          body: JSON.stringify({ path, provider, force: false }),
        })
        if (result.skipped) skipped += 1
        else {
          analyzed += 1
          learned += result.facts_written
        }
      }
      lastAutoMemoryRef.current = `${project.slug}\u0000${activeFile}\u0000${content}`
      await refreshMemory(project.slug, memoryQuery)
      setStatus(`Story memory built: ${learned} facts from ${analyzed} files; ${skipped} already current`)
    } catch (error) {
      setStatus(`Memory build stopped: ${(error as Error).message}`)
    } finally {
      setMemoryBusy(false)
    }
  }

  function selectionText() {
    return editorRef.current?.getSelectedText() || ''
  }

  async function saveCraftProfile(profile: CraftProfile) {
    if (!project) return
    try {
      setCraftProfile(await jsonFetch<CraftProfile>(`${API}/projects/${project.slug}/craft-profile`, {
        method: 'PUT',
        body: JSON.stringify(profile),
      }))
      setStatus('Project craft defaults saved')
    } catch (error) {
      setStatus(`Could not save craft profile: ${(error as Error).message}`)
    }
  }

  async function analyzeVoiceFromCurrentText(profileName: string) {
    if (!project || !provider.model || modelOccupied) return
    const selected = selectionText().trim()
    const sample = selected.length >= 200 ? selected : content.trim()
    if (sample.length < 200) {
      setStatus('Voice Lab needs at least 200 characters of prose')
      return
    }
    setCraftBusy(true)
    setStatus(`Learning ${profileName} from prose sample…`)
    try {
      if (dirty) await saveActiveFile()
      const result = await jsonFetch<{ profile: VoiceProfile; saved_path: string }>(`${API}/projects/${project.slug}/voice/analyze`, {
        method: 'POST',
        body: JSON.stringify({ sample_text: sample, provider, profile_name: profileName }),
      })
      setVoiceProfile(result.profile)
      setStatus(`Voice Lock learned and saved to ${result.saved_path}`)
    } catch (error) {
      setStatus(`Voice Lab failed: ${(error as Error).message}`)
    } finally {
      setCraftBusy(false)
    }
  }

  async function inferChemistry(participants: string[], authorDirection: string): Promise<ChemistryProfile | null> {
    if (!project || !provider.model || modelOccupied) return null
    setChemistryBusy(true)
    setStatus(`Building chemistry profile for ${participants.join(' + ')}…`)
    try {
      const result = await jsonFetch<{ profile: ChemistryProfile; saved_path: string | null }>(`${API}/projects/${project.slug}/chemistry/infer`, {
        method: 'POST',
        body: JSON.stringify({ participants, author_direction: authorDirection, provider, save: true }),
      })
      await Promise.all([refreshChemistry(project.slug), refreshProjectDetail(project.slug)])
      setStatus(result.saved_path ? `Chemistry saved to ${result.saved_path}` : 'Chemistry profile ready')
      return result.profile
    } catch (error) {
      setStatus(`Chemistry analysis failed: ${(error as Error).message}`)
      return null
    } finally {
      setChemistryBusy(false)
    }
  }

  async function saveChemistry(profile: ChemistryProfile): Promise<ChemistryProfile | null> {
    if (!project || modelOccupied) return null
    setChemistryBusy(true)
    try {
      const saved = await jsonFetch<ChemistryProfile>(`${API}/projects/${project.slug}/chemistry`, {
        method: 'PUT',
        body: JSON.stringify(profile),
      })
      await Promise.all([refreshChemistry(project.slug), refreshProjectDetail(project.slug)])
      setStatus(`Chemistry saved for ${saved.participants.join(' + ')}`)
      return saved
    } catch (error) {
      setStatus(`Could not save chemistry: ${(error as Error).message}`)
      return null
    } finally {
      setChemistryBusy(false)
    }
  }

  async function analyzeAftermath(participants: string[]): Promise<AftermathProposal | null> {
    if (!project || !provider.model || modelOccupied) return null
    const selected = selectionText().trim()
    const sample = selected.length >= 200 ? selected : content.trim()
    if (sample.length < 200) {
      setStatus('Aftermath needs at least 200 characters from the current scene or chapter')
      return null
    }
    setChemistryBusy(true)
    setStatus(`Analyzing aftermath for ${participants.join(' + ')}…`)
    try {
      if (dirty) await saveActiveFile()
      const proposal = await jsonFetch<AftermathProposal>(`${API}/projects/${project.slug}/aftermath/analyze`, {
        method: 'POST',
        body: JSON.stringify({ scene_text: sample, provider, source_path: activeFile || '', participants }),
      })
      setStatus('Aftermath proposal ready for review')
      return proposal
    } catch (error) {
      setStatus(`Aftermath analysis failed: ${(error as Error).message}`)
      return null
    } finally {
      setChemistryBusy(false)
    }
  }

  async function applyAftermath(proposal: AftermathProposal): Promise<boolean> {
    if (!project || modelOccupied) return false
    setChemistryBusy(true)
    setStatus('Applying reviewed relationship changes…')
    try {
      const result = await jsonFetch<{ profiles: ChemistryProfile[]; saved_paths: string[] }>(`${API}/projects/${project.slug}/aftermath/apply`, {
        method: 'POST',
        body: JSON.stringify(proposal),
      })
      await Promise.all([refreshChemistry(project.slug), refreshProjectDetail(project.slug)])
      setStatus(`Aftermath applied to ${result.profiles.length} relationship profile${result.profiles.length === 1 ? '' : 's'}`)
      return true
    } catch (error) {
      setStatus(`Could not apply aftermath: ${(error as Error).message}`)
      return false
    } finally {
      setChemistryBusy(false)
    }
  }

  async function runGeneration() {
    if (!project || !prompt.trim() || modelOccupied) return
    setBusy(true)
    setOutput('')
    setStatus(`Running ${mode}${craftControls.quality_pass ? ' + Craft Pass' : ''}…`)
    try {
      const result = await jsonFetch<{ text: string; context_files: string[]; refined: boolean }>(`${API}/projects/${project.slug}/generate`, {
        method: 'POST',
        body: JSON.stringify({
          prompt: prompt.trim(),
          mode,
          active_file: activeFile || null,
          selected_text: selectionText() || null,
          provider,
          craft: craftControls,
        }),
      })
      setOutput(result.text)
      setContextFiles(result.context_files)
      setStatus(result.refined ? 'Generation complete · Craft Pass applied' : 'Generation complete')
    } catch (error) {
      setStatus((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function runSceneArchitect(input: SceneArchitectInput): Promise<ScenePlanResponse | null> {
    if (!project || !provider.model || modelOccupied) return null
    setSceneBusy(true)
    setStatus('Architecting scene from story state…')
    try {
      if (dirty) await saveActiveFile()
      const result = await jsonFetch<ScenePlanResponse>(`${API}/projects/${project.slug}/scene-plan`, {
        method: 'POST',
        body: JSON.stringify({
          ...input,
          desired_heat: input.desired_heat === 'author controlled' ? (craftControls.heat_level || craftProfile.default_heat) : input.desired_heat,
          provider,
          active_file: activeFile || null,
          save: true,
        }),
      })
      await refreshProjectDetail(project.slug)
      setStatus(result.saved_path ? `Scene plan saved to ${result.saved_path}` : 'Scene plan ready')
      return result
    } catch (error) {
      setStatus(`Scene Architect failed: ${(error as Error).message}`)
      return null
    } finally {
      setSceneBusy(false)
    }
  }

  function useScenePlanAsPrompt(plan: ScenePlan) {
    const beats = plan.beats.map((beat, index) => `${index + 1}. ${beat.beat}`).join('\n')
    const guardrails = plan.continuity_requirements.map((item) => `- ${item}`).join('\n')
    const relationshipMoves = plan.relationship_moves.map((item) => `- ${item}`).join('\n')
    const intimacyNotes = plan.intimacy_notes.map((item) => `- ${item}`).join('\n')
    setMode('write')
    setPrompt(
      `Write the planned scene "${plan.title}" as polished manuscript prose.\n\n` +
      `POV: ${plan.pov}\nLocation: ${plan.location}\nObjective: ${plan.scene_objective}\nConflict: ${plan.conflict}\n\n` +
      `Required beats:\n${beats}\n\nContinuity guardrails:\n${guardrails || '- Preserve established canon and knowledge boundaries.'}\n\n` +
      `Relationship movement:\n${relationshipMoves || '- Preserve established relationship state.'}\n\n` +
      `${intimacyNotes ? `Intimacy / tension notes:\n${intimacyNotes}\n\n` : ''}` +
      `Ending state: ${plan.ending_state}\nNext-scene pressure: ${plan.next_scene_pressure}`,
    )
    setStatus('Scene plan loaded into Writer prompt')
  }

  function insertOutput(replaceSelection: boolean) {
    if (!output || !editorRef.current) return
    if (replaceSelection && selectionText()) editorRef.current.replaceSelection(output)
    else editorRef.current.insertAtEnd(output)
    setDirty(true)
  }

  async function reloadAfterRestore() {
    if (!project || !activeFile) return
    await openFile(project.slug, activeFile)
    await refreshBinder(project.slug)
    setRevisionToken((value) => value + 1)
    setStatus('Revision restored; later history remains available')
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand"><span className="ember">◆</span> EmberWriter</div>
        <div className="status">{dirty ? 'Unsaved changes' : status}</div>
        <button className="quiet" onClick={() => void saveActiveFile()} disabled={!dirty}>Save</button>
      </header>

      <aside className="library panel">
        <h2>Library</h2>
        <div className="create-row">
          <input value={newProjectName} onChange={(event) => setNewProjectName(event.target.value)} placeholder="New story project" />
          <button onClick={() => void createProject()} disabled={workspaceBusy || !newProjectName.trim()}>+</button>
        </div>
        <div className="project-list">
          {projects.map((item) => (
            <button key={item.slug} className={`project-card ${project?.slug === item.slug ? 'active' : ''}`} onClick={() => void openProject(item.slug)}>
              <strong>{item.name}</strong><small>{item.description || 'Local story project'}</small>
            </button>
          ))}
        </div>

        {project && <ImportPanel disabled={workspaceBusy} onFiles={importFiles} onText={importText} />}

        {project && binderState && (
          <BinderPanel
            state={binderState}
            activePath={activeFile}
            disabled={binderBusy}
            onOpen={(path) => void openFile(project.slug, path)}
            onCreate={createBinderNode}
            onUpdate={updateBinderNode}
            onReorder={reorderBinder}
            onTrash={trashBinderNode}
            onRestore={restoreBinderNode}
            onSync={syncBinder}
          />
        )}
        {project && !binderState && <small>Loading Binder…</small>}
      </aside>

      <main className="editor-panel rich-editor-panel">
        {project ? <>
          <div className="editor-header">
            <div><small>{project.name}</small><h1>{activeFile || 'Select a file'}</h1></div>
            <span className="word-count">{content.trim() ? content.trim().split(/\s+/).length : 0} words</span>
          </div>
          {activeFile ? (
            <RichTextEditor
              ref={editorRef}
              markdown={content}
              documentKey={`${project.slug}:${activeFile}`}
              disabled={false}
              onChange={(next) => { setContent(next); setDirty(true) }}
            />
          ) : <div className="empty-state"><h1>Select a Binder document</h1></div>}
        </> : <div className="empty-state"><span className="ember-mark">◆</span><h1>Your stories stay yours.</h1><p>Create a project or open one from the library. EmberWriter stores readable files locally, versions every saved document, and builds story intelligence around them.</p></div>}
      </main>

      <aside className="assistant panel">
        <div className="assistant-title"><span className="ember">◆</span><div><h2>Ember</h2><small>Story-aware writing partner</small></div></div>

        {project && activeFile && (
          <VersionHistoryPanel
            apiBase={API}
            slug={project.slug}
            path={activeFile}
            disabled={workspaceBusy}
            refreshToken={revisionToken}
            onRestored={reloadAfterRestore}
          />
        )}

        {project && <PublishPanel apiBase={API} slug={project.slug} projectName={project.name} disabled={workspaceBusy} />}

        <label>Mode</label>
        <div className="mode-grid">
          {(['continue', 'write', 'rewrite', 'brainstorm', 'critic', 'continuity'] as Mode[]).map((item) => (
            <button key={item} className={mode === item ? 'active' : ''} onClick={() => setMode(item)}>{item}</button>
          ))}
        </div>

        <textarea className="prompt" value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder="Tell Ember what you want from this scene…" />

        {project && (
          <CraftPanel
            controls={craftControls}
            profile={craftProfile}
            voiceProfile={voiceProfile}
            disabled={modelOccupied || !provider.model}
            sampleAvailable={content.trim().length >= 200}
            onControlsChange={setCraftControls}
            onSaveProfile={saveCraftProfile}
            onAnalyzeVoice={analyzeVoiceFromCurrentText}
          />
        )}

        <button className="primary" onClick={() => void runGeneration()} disabled={modelOccupied || !project || !prompt.trim() || !provider.model}>
          {busy ? 'Writing…' : memoryBusy ? 'Memory busy…' : sceneBusy ? 'Scene Architect busy…' : craftBusy ? 'Voice Lab busy…' : chemistryBusy ? 'Chemistry busy…' : 'Generate'}
        </button>

        {output && <div className="result-card">
          <div className="result-actions"><strong>Result</strong><span><button onClick={() => insertOutput(false)}>Append</button><button onClick={() => insertOutput(true)}>Replace selection</button></span></div>
          <div className="result-text">{output}</div>
          {contextFiles.length > 0 && <details><summary>Context used ({contextFiles.length})</summary>{contextFiles.map((file) => <div className="context-file" key={file}>{file}</div>)}</details>}
        </div>}

        {project && (
          <SceneArchitectPanel
            characters={storyIntelligence.characters}
            disabled={modelOccupied || !provider.model}
            onGenerate={runSceneArchitect}
            onOpenSaved={(path) => void openFile(project.slug, path)}
            onUseAsPrompt={useScenePlanAsPrompt}
          />
        )}

        {project && (
          <ChemistryPanel
            characterNames={characterNames}
            profiles={chemistryProfiles}
            disabled={modelOccupied || !provider.model}
            canAnalyzeScene={content.trim().length >= 200}
            onInfer={inferChemistry}
            onSave={saveChemistry}
            onAnalyzeAftermath={analyzeAftermath}
            onApplyAftermath={applyAftermath}
          />
        )}

        {project && (
          <StoryIntelligencePanel
            intelligence={storyIntelligence}
            onRefresh={() => void refreshMemory(project.slug, memoryQuery)}
            onOpenSource={(path) => void openFile(project.slug, path)}
          />
        )}

        {project && (
          <MemoryPanel
            facts={memoryFacts}
            stats={memoryStats}
            query={memoryQuery}
            autoMemory={autoMemory}
            busy={memoryBusy || sceneBusy || craftBusy || chemistryBusy}
            canAnalyze={activeFile.startsWith('manuscript/') && Boolean(provider.model)}
            canAnalyzeAll={manuscriptFiles.length > 0 && Boolean(provider.model)}
            onQueryChange={setMemoryQuery}
            onAutoMemoryChange={setAutoMemory}
            onAnalyze={() => void analyzeActiveFile(true)}
            onAnalyzeAll={() => void analyzeAllManuscript()}
            onRefresh={() => void refreshMemory(project.slug, memoryQuery)}
            onOpenSource={(path) => void openFile(project.slug, path)}
          />
        )}

        <details className="model-settings" open={!provider.model}>
          <summary>Local model</summary>
          <label>Provider</label>
          <select value={provider.provider} onChange={(event) => setProvider({ ...provider, provider: event.target.value as Provider['provider'] })}>
            <option value="ollama">Ollama</option>
            <option value="openai_compatible">OpenAI-compatible</option>
          </select>
          <label>Server</label>
          <input value={provider.base_url} onChange={(event) => setProvider({ ...provider, base_url: event.target.value })} />
          <label>Model</label>
          <div className="create-row">
            <input list="model-list" value={provider.model} onChange={(event) => setProvider({ ...provider, model: event.target.value })} placeholder="Choose or type model" />
            <button onClick={() => void refreshModels()} disabled={modelOccupied}>↻</button>
          </div>
          <datalist id="model-list">{models.map((model) => <option key={model} value={model} />)}</datalist>
          {provider.provider === 'openai_compatible' && <><label>API key (optional)</label><input type="password" value={provider.api_key || ''} onChange={(event) => setProvider({ ...provider, api_key: event.target.value })} /></>}
        </details>
      </aside>
    </div>
  )
}
