import { useEffect, useMemo, useRef, useState } from 'react'

import MemoryPanel, { type MemoryFact, type MemoryStats } from './MemoryPanel'

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

type Mode = 'write' | 'continue' | 'rewrite' | 'brainstorm' | 'critic' | 'continuity'

const defaultProvider: Provider = {
  provider: 'ollama',
  base_url: 'http://localhost:11434',
  model: '',
  api_key: '',
}

const emptyMemoryStats: MemoryStats = { facts: 0, documents: 0, by_kind: {} }

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

function App() {
  const [projects, setProjects] = useState<ProjectSummary[]>([])
  const [project, setProject] = useState<ProjectDetail | null>(null)
  const [activeFile, setActiveFile] = useState('')
  const [content, setContent] = useState('')
  const [dirty, setDirty] = useState(false)
  const [newProjectName, setNewProjectName] = useState('')
  const [newFilePath, setNewFilePath] = useState('')
  const [prompt, setPrompt] = useState('')
  const [mode, setMode] = useState<Mode>('continue')
  const [output, setOutput] = useState('')
  const [contextFiles, setContextFiles] = useState<string[]>([])
  const [models, setModels] = useState<string[]>([])
  const [busy, setBusy] = useState(false)
  const [memoryBusy, setMemoryBusy] = useState(false)
  const [memoryFacts, setMemoryFacts] = useState<MemoryFact[]>([])
  const [memoryStats, setMemoryStats] = useState<MemoryStats>(emptyMemoryStats)
  const [memoryQuery, setMemoryQuery] = useState('')
  const [status, setStatus] = useState('Ready')
  const [provider, setProvider] = useState<Provider>(() => {
    const stored = localStorage.getItem('emberwriter.provider')
    return stored ? { ...defaultProvider, ...JSON.parse(stored) } : defaultProvider
  })
  const [autoMemory, setAutoMemory] = useState(() => {
    const stored = localStorage.getItem('emberwriter.autoMemory')
    return stored === null ? true : stored === 'true'
  })
  const editorRef = useRef<HTMLTextAreaElement>(null)
  const lastAutoMemoryRef = useRef('')

  const manuscriptFiles = useMemo(
    () => project?.files.filter((file) => file.startsWith('manuscript/')) ?? [],
    [project],
  )
  const referenceFiles = useMemo(
    () => project?.files.filter((file) => !file.startsWith('manuscript/') && file !== 'project.json') ?? [],
    [project],
  )

  useEffect(() => {
    void refreshProjects()
  }, [])

  useEffect(() => {
    localStorage.setItem('emberwriter.provider', JSON.stringify(provider))
  }, [provider])

  useEffect(() => {
    localStorage.setItem('emberwriter.autoMemory', String(autoMemory))
  }, [autoMemory])

  useEffect(() => {
    if (!dirty || !project || !activeFile) return
    const timer = window.setTimeout(() => void saveActiveFile(), 750)
    return () => window.clearTimeout(timer)
  }, [content, dirty, project?.slug, activeFile])

  useEffect(() => {
    if (!project) return
    const timer = window.setTimeout(() => void refreshMemory(project.slug, memoryQuery), 250)
    return () => window.clearTimeout(timer)
  }, [memoryQuery, project?.slug])

  useEffect(() => {
    if (
      !autoMemory || !project || !activeFile.startsWith('manuscript/') || !provider.model ||
      dirty || busy || memoryBusy
    ) return

    const key = `${project.slug}\u0000${activeFile}\u0000${content}`
    if (lastAutoMemoryRef.current === key) return

    const timer = window.setTimeout(() => {
      lastAutoMemoryRef.current = key
      void analyzeActiveFile(false)
    }, 4500)
    return () => window.clearTimeout(timer)
  }, [
    autoMemory,
    project?.slug,
    activeFile,
    content,
    provider.model,
    provider.provider,
    provider.base_url,
    dirty,
    busy,
    memoryBusy,
  ])

  async function refreshProjects() {
    try {
      const data = await jsonFetch<ProjectSummary[]>(`${API}/projects`)
      setProjects(data)
    } catch (error) {
      setStatus(`API offline: ${(error as Error).message}`)
    }
  }

  async function refreshMemory(slug = project?.slug, query = memoryQuery) {
    if (!slug) return
    try {
      const suffix = query.trim() ? `?query=${encodeURIComponent(query.trim())}` : ''
      const [facts, stats] = await Promise.all([
        jsonFetch<MemoryFact[]>(`${API}/projects/${slug}/memory${suffix}`),
        jsonFetch<MemoryStats>(`${API}/projects/${slug}/memory/stats`),
      ])
      setMemoryFacts(facts)
      setMemoryStats(stats)
    } catch (error) {
      setStatus(`Memory unavailable: ${(error as Error).message}`)
    }
  }

  async function openProject(slug: string) {
    setStatus('Opening project…')
    try {
      const detail = await jsonFetch<ProjectDetail>(`${API}/projects/${slug}`)
      setProject(detail)
      setMemoryQuery('')
      const first = detail.files.find((file) => file.startsWith('manuscript/')) || detail.files[0] || ''
      if (first) await openFile(detail.slug, first)
      await refreshMemory(detail.slug, '')
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
      const data = await jsonFetch<{ path: string; content: string }>(
        `${API}/projects/${slug}/file?path=${encodeURIComponent(path)}`,
      )
      setActiveFile(path)
      setContent(data.content)
      setDirty(false)
      lastAutoMemoryRef.current = ''
      setStatus(path)
    } catch (error) {
      setStatus((error as Error).message)
    }
  }

  async function saveActiveFile() {
    if (!project || !activeFile) return
    try {
      await jsonFetch(`${API}/projects/${project.slug}/file?path=${encodeURIComponent(activeFile)}`, {
        method: 'PUT',
        body: JSON.stringify({ content }),
      })
      setDirty(false)
      setStatus(`Saved ${activeFile}`)
    } catch (error) {
      setStatus(`Save failed: ${(error as Error).message}`)
    }
  }

  async function createFile() {
    if (!project || !newFilePath.trim()) return
    let path = newFilePath.trim().replaceAll('\\', '/')
    if (!path.includes('/')) path = `manuscript/${path}`
    if (!/\.(md|txt|json|ya?ml)$/i.test(path)) path += '.md'
    try {
      await jsonFetch(`${API}/projects/${project.slug}/file?path=${encodeURIComponent(path)}`, {
        method: 'PUT',
        body: JSON.stringify({ content: `# ${path.split('/').pop()?.replace(/\.md$/i, '') || 'Untitled'}\n\n` }),
      })
      const refreshed = await jsonFetch<ProjectDetail>(`${API}/projects/${project.slug}`)
      setProject(refreshed)
      setNewFilePath('')
      await openFile(project.slug, path)
    } catch (error) {
      setStatus((error as Error).message)
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
    if (!project || !activeFile.startsWith('manuscript/') || !provider.model || memoryBusy) return
    setMemoryBusy(true)
    setStatus(`Analyzing ${activeFile} for story memory…`)
    try {
      if (dirty) await saveActiveFile()
      const result = await jsonFetch<AnalyzeResult>(
        `${API}/projects/${project.slug}/memory/analyze`,
        {
          method: 'POST',
          body: JSON.stringify({ path: activeFile, provider, force }),
        },
      )
      await refreshMemory(project.slug, memoryQuery)
      setStatus(
        result.skipped
          ? `Memory already current for ${activeFile}`
          : `Remembered ${result.facts_written} story facts from ${activeFile}`,
      )
    } catch (error) {
      setStatus(`Memory analysis failed: ${(error as Error).message}`)
    } finally {
      setMemoryBusy(false)
    }
  }

  async function analyzeAllManuscript() {
    if (!project || !provider.model || manuscriptFiles.length === 0 || memoryBusy) return
    setMemoryBusy(true)
    let learned = 0
    let analyzed = 0
    let skipped = 0
    try {
      if (dirty) await saveActiveFile()
      for (const [index, path] of manuscriptFiles.entries()) {
        setStatus(`Building story memory ${index + 1}/${manuscriptFiles.length}: ${path}`)
        const result = await jsonFetch<AnalyzeResult>(
          `${API}/projects/${project.slug}/memory/analyze`,
          {
            method: 'POST',
            body: JSON.stringify({ path, provider, force: false }),
          },
        )
        if (result.skipped) {
          skipped += 1
        } else {
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
    const el = editorRef.current
    if (!el) return ''
    return content.slice(el.selectionStart, el.selectionEnd)
  }

  async function runGeneration() {
    if (!project || !prompt.trim() || memoryBusy) return
    setBusy(true)
    setOutput('')
    setStatus(`Running ${mode}…`)
    try {
      const result = await jsonFetch<{ text: string; context_files: string[] }>(
        `${API}/projects/${project.slug}/generate`,
        {
          method: 'POST',
          body: JSON.stringify({
            prompt: prompt.trim(),
            mode,
            active_file: activeFile || null,
            selected_text: selectionText() || null,
            provider,
          }),
        },
      )
      setOutput(result.text)
      setContextFiles(result.context_files)
      setStatus('Generation complete')
    } catch (error) {
      setStatus((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  function insertOutput(replaceSelection: boolean) {
    if (!output) return
    const el = editorRef.current
    const start = el?.selectionStart ?? content.length
    const end = el?.selectionEnd ?? content.length
    if (replaceSelection && end > start) {
      setContent(content.slice(0, start) + output + content.slice(end))
    } else {
      const separator = content.endsWith('\n\n') || !content ? '' : '\n\n'
      setContent(content + separator + output)
    }
    setDirty(true)
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
          <input value={newProjectName} onChange={(e) => setNewProjectName(e.target.value)} placeholder="New story project" />
          <button onClick={() => void createProject()} disabled={busy || !newProjectName.trim()}>+</button>
        </div>
        <div className="project-list">
          {projects.map((item) => (
            <button key={item.slug} className={`project-card ${project?.slug === item.slug ? 'active' : ''}`} onClick={() => void openProject(item.slug)}>
              <strong>{item.name}</strong><small>{item.description || 'Local story project'}</small>
            </button>
          ))}
        </div>

        {project && <>
          <div className="section-title">Manuscript</div>
          <nav className="file-list">
            {manuscriptFiles.map((file) => <button key={file} className={activeFile === file ? 'active' : ''} onClick={() => void openFile(project.slug, file)}>{file.replace('manuscript/', '')}</button>)}
          </nav>
          <div className="section-title">Story Bible</div>
          <nav className="file-list secondary">
            {referenceFiles.map((file) => <button key={file} className={activeFile === file ? 'active' : ''} onClick={() => void openFile(project.slug, file)}>{file}</button>)}
          </nav>
          <div className="create-row file-create">
            <input value={newFilePath} onChange={(e) => setNewFilePath(e.target.value)} placeholder="characters/name.md" />
            <button onClick={() => void createFile()}>+</button>
          </div>
        </>}
      </aside>

      <main className="editor-panel">
        {project ? <>
          <div className="editor-header">
            <div><small>{project.name}</small><h1>{activeFile || 'Select a file'}</h1></div>
            <span className="word-count">{content.trim() ? content.trim().split(/\s+/).length : 0} words</span>
          </div>
          <textarea
            ref={editorRef}
            className="manuscript"
            value={content}
            onChange={(e) => { setContent(e.target.value); setDirty(true) }}
            spellCheck
            placeholder="Start writing…"
          />
        </> : <div className="empty-state"><span className="ember-mark">◆</span><h1>Your stories stay yours.</h1><p>Create a project or open one from the library. EmberWriter stores readable files on your machine and builds memory around them.</p></div>}
      </main>

      <aside className="assistant panel">
        <div className="assistant-title"><span className="ember">◆</span><div><h2>Ember</h2><small>Story-aware writing partner</small></div></div>

        <label>Mode</label>
        <div className="mode-grid">
          {(['continue', 'write', 'rewrite', 'brainstorm', 'critic', 'continuity'] as Mode[]).map((item) => (
            <button key={item} className={mode === item ? 'active' : ''} onClick={() => setMode(item)}>{item}</button>
          ))}
        </div>

        <textarea className="prompt" value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder="Tell Ember what you want from this scene…" />
        <button className="primary" onClick={() => void runGeneration()} disabled={busy || memoryBusy || !project || !prompt.trim() || !provider.model}>{busy ? 'Working…' : memoryBusy ? 'Memory busy…' : 'Generate'}</button>

        {output && <div className="result-card">
          <div className="result-actions"><strong>Result</strong><span><button onClick={() => insertOutput(false)}>Append</button><button onClick={() => insertOutput(true)}>Replace selection</button></span></div>
          <div className="result-text">{output}</div>
          {contextFiles.length > 0 && <details><summary>Context used ({contextFiles.length})</summary>{contextFiles.map((file) => <div className="context-file" key={file}>{file}</div>)}</details>}
        </div>}

        {project && (
          <MemoryPanel
            facts={memoryFacts}
            stats={memoryStats}
            query={memoryQuery}
            autoMemory={autoMemory}
            busy={memoryBusy}
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
          <select value={provider.provider} onChange={(e) => setProvider({ ...provider, provider: e.target.value as Provider['provider'] })}>
            <option value="ollama">Ollama</option>
            <option value="openai_compatible">OpenAI-compatible</option>
          </select>
          <label>Server</label>
          <input value={provider.base_url} onChange={(e) => setProvider({ ...provider, base_url: e.target.value })} />
          <label>Model</label>
          <div className="create-row">
            <input list="model-list" value={provider.model} onChange={(e) => setProvider({ ...provider, model: e.target.value })} placeholder="Choose or type model" />
            <button onClick={() => void refreshModels()} disabled={busy || memoryBusy}>↻</button>
          </div>
          <datalist id="model-list">{models.map((model) => <option key={model} value={model} />)}</datalist>
          {provider.provider === 'openai_compatible' && <><label>API key (optional)</label><input type="password" value={provider.api_key || ''} onChange={(e) => setProvider({ ...provider, api_key: e.target.value })} /></>}
        </details>
      </aside>
    </div>
  )
}

export default App
