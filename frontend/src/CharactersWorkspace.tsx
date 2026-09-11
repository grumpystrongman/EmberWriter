import { useEffect, useMemo, useState } from 'react'

import type { CharacterFact, CharacterProfile, RelationshipEdge, StoryIntelligence } from './StoryIntelligencePanel'
import type { ProviderConfig, WorkspaceProject } from './workspace-types'

type Props = {
  apiBase: string
  project: WorkspaceProject
  onOpenSource: (path: string, anchor?: string) => void
}

type ProjectDetail = { files: string[] }
type Depth = 'focused' | 'detailed' | 'exhaustive'

type PortraitMetadata = {
  character: string
  relative_path: string
  source: string
  prompt: string
  width: number
  height: number
  generated_at: string
}

type GenerationResponse = {
  text: string
}

type ImageSettings = {
  base_url: string
  width: number
  height: number
  steps: number
  cfg_scale: number
  negative_prompt: string
}

const defaultImageSettings: ImageSettings = {
  base_url: 'http://127.0.0.1:7860',
  width: 768,
  height: 1024,
  steps: 28,
  cfg_scale: 7,
  negative_prompt: 'low quality, blurry, distorted anatomy, extra fingers, extra limbs, text, watermark, logo, duplicate person',
}

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

function currentProvider(): ProviderConfig | null {
  try {
    const raw = localStorage.getItem('emberwriter.provider')
    if (!raw) return null
    const parsed = JSON.parse(raw) as ProviderConfig
    if (!parsed?.model?.trim() || !parsed.base_url?.trim()) return null
    return parsed
  } catch {
    return null
  }
}

function slugify(value: string) {
  return value.toLowerCase().trim().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'character'
}

function displayNameFromPath(path: string) {
  const filename = path.split('/').at(-1) || path
  return filename.replace(/\.(md|txt)$/i, '').replace(/[-_]+/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function dossierPath(name: string, profile?: CharacterProfile) {
  return profile?.dossier_path || `characters/${slugify(name)}.md`
}

function defaultDossier(name: string) {
  return `# ${name}\n\n## Role in the story\n\n\n## Appearance & presence\n\n\n## Voice & speech\n\n\n## Personality\n\n\n## History\n\n\n## Wants, needs & fears\n\n\n## Relationships\n\n\n## Knowledge & secrets\n\n\n## Character arc\n\n\n## Continuity notes\n\n`
}

function depthInstruction(depth: Depth) {
  if (depth === 'focused') return 'Keep the dossier concise and practical: about 700–1,000 words.'
  if (depth === 'exhaustive') return 'Be exhaustive and useful to a novelist: 2,500–4,000 words when the available evidence supports it. Cover appearance, embodiment, voice, habits, history, psychology, wants/needs, fears, wounds, skills, worldview, relationships, knowledge boundaries, secrets, contradictions, arc, scene behavior, sensory motifs, continuity risks, and adult romantic/intimacy dynamics only where supported by canon.'
  return 'Create a detailed novelist-facing dossier of roughly 1,300–2,000 words, prioritizing established evidence and practical scene-writing detail.'
}

function FactGroup({ title, facts, onOpenSource }: { title: string; facts: CharacterFact[]; onOpenSource: Props['onOpenSource'] }) {
  if (!facts.length) return null
  return (
    <section className="character-fact-section">
      <h3>{title}</h3>
      <div className="character-fact-list">
        {facts.map((fact, index) => (
          <button type="button" key={`${fact.source_path}-${fact.predicate}-${index}`} onClick={() => onOpenSource(fact.source_path, fact.object)}>
            <span><b>{fact.predicate}</b> {fact.object}</span>
            <small>ch {fact.chapter_order || '?'} · {Math.round(fact.confidence * 100)}% · importance {fact.importance}/5</small>
          </button>
        ))}
      </div>
    </section>
  )
}

export default function CharactersWorkspace({ apiBase, project, onOpenSource }: Props) {
  const [intelligence, setIntelligence] = useState<StoryIntelligence>({ characters: [], relationships: [] })
  const [files, setFiles] = useState<string[]>([])
  const [selected, setSelected] = useState('')
  const [dossier, setDossier] = useState('')
  const [dossierDirty, setDossierDirty] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [newName, setNewName] = useState('')
  const [depth, setDepth] = useState<Depth>('detailed')
  const [portrait, setPortrait] = useState<PortraitMetadata | null>(null)
  const [portraitVersion, setPortraitVersion] = useState(0)
  const [portraitPrompt, setPortraitPrompt] = useState('')
  const [imageSettings, setImageSettings] = useState<ImageSettings>(() => {
    try {
      return { ...defaultImageSettings, ...JSON.parse(localStorage.getItem('emberwriter.imageProvider') || '{}') }
    } catch {
      return defaultImageSettings
    }
  })

  const manualCharacterNames = useMemo(
    () => files
      .filter((path) => path.startsWith('characters/') && /\.(md|txt)$/i.test(path) && !path.endsWith('/README.md'))
      .map(displayNameFromPath),
    [files],
  )
  const characterNames = useMemo(
    () => [...new Set([...intelligence.characters.map((item) => item.name), ...manualCharacterNames])].sort((a, b) => a.localeCompare(b)),
    [intelligence.characters, manualCharacterNames],
  )
  const profile = useMemo(
    () => intelligence.characters.find((item) => item.name.toLowerCase() === selected.toLowerCase()),
    [intelligence.characters, selected],
  )
  const relationships = useMemo(
    () => intelligence.relationships.filter((edge) => edge.source.toLowerCase() === selected.toLowerCase() || edge.target.toLowerCase() === selected.toLowerCase()),
    [intelligence.relationships, selected],
  )
  const currentDossierPath = selected ? dossierPath(selected, profile) : ''

  useEffect(() => {
    localStorage.setItem('emberwriter.imageProvider', JSON.stringify(imageSettings))
  }, [imageSettings])

  useEffect(() => {
    void loadWorkspace()
  }, [project.slug])

  useEffect(() => {
    if (!selected) return
    void loadDossier(selected)
    void loadPortrait(selected)
  }, [selected, project.slug])

  async function loadWorkspace() {
    setError('')
    try {
      const [story, detail] = await Promise.all([
        request<StoryIntelligence>(`${apiBase}/projects/${project.slug}/story-intelligence`),
        request<ProjectDetail>(`${apiBase}/projects/${project.slug}`),
      ])
      setIntelligence(story)
      setFiles(detail.files)
      const names = [...new Set([...story.characters.map((item) => item.name), ...detail.files
        .filter((path) => path.startsWith('characters/') && /\.(md|txt)$/i.test(path) && !path.endsWith('/README.md'))
        .map(displayNameFromPath)])]
      setSelected((current) => current && names.includes(current) ? current : names[0] || '')
    } catch (cause) {
      setError((cause as Error).message)
    }
  }

  async function loadDossier(name: string) {
    const found = intelligence.characters.find((item) => item.name.toLowerCase() === name.toLowerCase())
    const path = dossierPath(name, found)
    try {
      const response = await request<{ content: string }>(`${apiBase}/projects/${project.slug}/file?path=${encodeURIComponent(path)}`)
      setDossier(response.content)
    } catch {
      setDossier(defaultDossier(name))
    }
    setDossierDirty(false)
  }

  async function loadPortrait(name: string) {
    try {
      setPortrait(await request<PortraitMetadata>(`${apiBase}/projects/${project.slug}/character-portraits/${encodeURIComponent(name)}/metadata`))
    } catch {
      setPortrait(null)
    }
  }

  async function saveDossier() {
    if (!selected || !currentDossierPath) return
    setBusy(true)
    setError('')
    try {
      await request(`${apiBase}/projects/${project.slug}/file?path=${encodeURIComponent(currentDossierPath)}`, {
        method: 'PUT',
        body: JSON.stringify({ content: dossier }),
      })
      setDossierDirty(false)
      const detail = await request<ProjectDetail>(`${apiBase}/projects/${project.slug}`)
      setFiles(detail.files)
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function createCharacter() {
    const name = newName.trim()
    if (!name) return
    const path = `characters/${slugify(name)}.md`
    setBusy(true)
    setError('')
    try {
      await request(`${apiBase}/projects/${project.slug}/file?path=${encodeURIComponent(path)}`, {
        method: 'PUT',
        body: JSON.stringify({ content: defaultDossier(name) }),
      })
      const detail = await request<ProjectDetail>(`${apiBase}/projects/${project.slug}`)
      setFiles(detail.files)
      setSelected(name)
      setDossier(defaultDossier(name))
      setDossierDirty(false)
      setNewName('')
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function generateDossier(expand: boolean) {
    if (!selected) return
    const provider = currentProvider()
    if (!provider) {
      setError('Choose an AI model in Ember model settings before generating a dossier.')
      return
    }
    setBusy(true)
    setError('')
    try {
      const existing = dossier.trim()
      const response = await request<GenerationResponse>(`${apiBase}/projects/${project.slug}/generate`, {
        method: 'POST',
        body: JSON.stringify({
          prompt: [
            `Create a character dossier for ${selected} in the novel “${project.name}”.`,
            depthInstruction(depth),
            'Use only manuscript/story-memory evidence as established fact. If useful details are not established, put them under a clearly labeled “Author decisions still open” section instead of inventing canon.',
            'Write in clean Markdown for a novelist. Preserve the character’s individuality, contradictions, voice, and current point in the arc.',
            expand && existing ? `Expand and improve this author-edited dossier without erasing deliberate author choices:\n\n${existing}` : 'Build the dossier from the current manuscript, story intelligence, and saved project files.',
          ].join('\n\n'),
          mode: 'brainstorm',
          active_file: project.activePath || null,
          selected_text: null,
          provider,
          craft: { voice_lock: false, quality_pass: false },
        }),
      })
      setDossier(response.text.trim() + '\n')
      setDossierDirty(true)
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function generatePortraitPrompt() {
    if (!selected) return
    const provider = currentProvider()
    if (!provider) {
      setError('Choose a text model first so Ember can build a grounded portrait prompt.')
      return
    }
    setBusy(true)
    setError('')
    try {
      const factText = profile
        ? [...profile.state, ...profile.other_facts].slice(0, 18).map((fact) => `${fact.predicate}: ${fact.object}`).join('\n')
        : ''
      const response = await request<GenerationResponse>(`${apiBase}/projects/${project.slug}/generate`, {
        method: 'POST',
        body: JSON.stringify({
          prompt: `Write one high-quality Stable Diffusion portrait prompt for the fictional character ${selected}. Ground physical details in canon and the author dossier. Do not add unestablished ethnicity, scars, body traits, age, clothing, or anatomy. Focus on recognizable face, expression, posture, wardrobe that is actually supported, lighting, genre atmosphere, camera/lens composition, and professional book-development concept art quality. Return only the image prompt, no explanation.\n\nKnown facts:\n${factText}\n\nAuthor dossier:\n${dossier.slice(0, 12000)}`,
          mode: 'brainstorm',
          active_file: project.activePath || null,
          selected_text: null,
          provider,
          craft: { voice_lock: false, quality_pass: false },
        }),
      })
      setPortraitPrompt(response.text.trim())
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function generatePortrait() {
    if (!selected || !portraitPrompt.trim()) return
    setBusy(true)
    setError('')
    try {
      const result = await request<PortraitMetadata>(`${apiBase}/projects/${project.slug}/character-portraits/generate`, {
        method: 'POST',
        body: JSON.stringify({
          character: selected,
          prompt: portraitPrompt.trim(),
          negative_prompt: imageSettings.negative_prompt,
          base_url: imageSettings.base_url,
          width: imageSettings.width,
          height: imageSettings.height,
          steps: imageSettings.steps,
          cfg_scale: imageSettings.cfg_scale,
        }),
      })
      setPortrait(result)
      setPortraitVersion((value) => value + 1)
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function uploadPortrait(file: File) {
    if (!selected) return
    setBusy(true)
    setError('')
    try {
      const form = new FormData()
      form.append('image', file)
      const response = await fetch(`${apiBase}/projects/${project.slug}/character-portraits/${encodeURIComponent(selected)}/upload`, {
        method: 'POST',
        body: form,
      })
      if (!response.ok) {
        const body = await response.json().catch(() => ({}))
        throw new Error(body.detail || `${response.status} ${response.statusText}`)
      }
      setPortrait(await response.json() as PortraitMetadata)
      setPortraitVersion((value) => value + 1)
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function deletePortrait() {
    if (!selected || !portrait) return
    setBusy(true)
    try {
      const response = await fetch(`${apiBase}/projects/${project.slug}/character-portraits/${encodeURIComponent(selected)}`, { method: 'DELETE' })
      if (!response.ok && response.status !== 404) throw new Error(`${response.status} ${response.statusText}`)
      setPortrait(null)
      setPortraitVersion((value) => value + 1)
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="center-tool characters-workspace">
      <header className="center-tool-header">
        <div>
          <small>CHARACTERS · {project.name}</small>
          <h1>Character Studio</h1>
          <p>Canon-aware dossiers, relationship history, knowledge boundaries, and visual references—with AI when you want it and direct author control everywhere.</p>
        </div>
        <div className="center-tool-actions">
          <button type="button" onClick={() => void loadWorkspace()} disabled={busy}>↻ Refresh story state</button>
          <select value={depth} onChange={(event) => setDepth(event.target.value as Depth)} aria-label="Character AI depth">
            <option value="focused">AI depth: Focused</option>
            <option value="detailed">AI depth: Detailed</option>
            <option value="exhaustive">AI depth: Exhaustive</option>
          </select>
        </div>
      </header>

      <div className="character-layout">
        <aside className="character-roster">
          <div className="character-roster-head"><strong>Cast</strong><span>{characterNames.length}</span></div>
          <div className="character-create-row">
            <input value={newName} onChange={(event) => setNewName(event.target.value)} placeholder="New character" />
            <button type="button" onClick={() => void createCharacter()} disabled={busy || !newName.trim()}>+</button>
          </div>
          <div className="character-roster-list">
            {characterNames.map((name) => (
              <button type="button" key={name} className={selected === name ? 'active' : ''} onClick={() => setSelected(name)}>
                <span className="character-avatar-mini">{name.split(/\s+/).map((part) => part[0]).slice(0, 2).join('').toUpperCase()}</span>
                <span><strong>{name}</strong><small>{intelligence.characters.some((item) => item.name === name) ? 'Story Memory + dossier' : 'Author dossier'}</small></span>
              </button>
            ))}
          </div>
        </aside>

        {!selected ? (
          <div className="center-empty character-empty">Create a character yourself or build Story Memory to discover characters from the manuscript.</div>
        ) : (
          <div className="character-main">
            <section className="character-hero">
              <div className="character-portrait-card">
                {portrait ? (
                  <img src={`${apiBase}/projects/${project.slug}/character-portraits/${encodeURIComponent(selected)}?v=${portraitVersion}`} alt={`Visual reference for ${selected}`} />
                ) : (
                  <div className="portrait-empty"><span>{selected.split(/\s+/).map((part) => part[0]).slice(0, 2).join('').toUpperCase()}</span><small>No portrait yet</small></div>
                )}
                <div className="portrait-actions">
                  <label className="button-like">Upload image<input type="file" accept="image/*" onChange={(event) => { const file = event.target.files?.[0]; if (file) void uploadPortrait(file); event.currentTarget.value = '' }} /></label>
                  {portrait && <button type="button" onClick={() => void deletePortrait()} disabled={busy}>Remove</button>}
                </div>
              </div>
              <div className="character-hero-copy">
                <small>CHARACTER DOSSIER</small>
                <h2>{selected}</h2>
                <p>{profile ? `Latest derived story state: chapter ${profile.latest_chapter || '?'}. ${profile.state.length} state facts · ${profile.knowledge.length} knowledge facts · ${relationships.length} relationship links.` : 'Author-created character. Story Memory has not derived a matching character profile yet.'}</p>
                <div className="character-hero-actions">
                  <button type="button" className="primary" onClick={() => void generateDossier(false)} disabled={busy}>{busy ? 'Working…' : 'AI generate full dossier'}</button>
                  <button type="button" onClick={() => void generateDossier(true)} disabled={busy || !dossier.trim()}>AI expand / deepen</button>
                  <button type="button" onClick={() => void saveDossier()} disabled={busy || !dossierDirty}>{dossierDirty ? 'Save dossier' : 'Saved'}</button>
                </div>
              </div>
            </section>

            <div className="character-work-grid">
              <section className="dossier-editor-card">
                <div className="center-section-heading"><div><h2>Author Dossier</h2><p>{currentDossierPath}</p></div></div>
                <textarea className="planning-document character-dossier-editor" value={dossier} onChange={(event) => { setDossier(event.target.value); setDossierDirty(true) }} spellCheck />
              </section>

              <aside className="character-canon-card">
                <FactGroup title="Current state" facts={profile?.state || []} onOpenSource={onOpenSource} />
                <FactGroup title="What they know" facts={profile?.knowledge || []} onOpenSource={onOpenSource} />
                <FactGroup title="Continuity" facts={profile?.other_facts || []} onOpenSource={onOpenSource} />
                {relationships.length > 0 && (
                  <section className="character-fact-section">
                    <h3>Relationships</h3>
                    <div className="relationship-center-list">
                      {relationships.map((edge: RelationshipEdge, index) => (
                        <button type="button" key={`${edge.source}-${edge.target}-${index}`} onClick={() => onOpenSource(edge.source_path, edge.detail || edge.state)}>
                          <strong>{edge.source} → {edge.target}</strong><span>{edge.state}{edge.detail ? ` · ${edge.detail}` : ''}</span><small>ch {edge.chapter_order || '?'}</small>
                        </button>
                      ))}
                    </div>
                  </section>
                )}
              </aside>
            </div>

            <section className="portrait-studio">
              <div className="center-section-heading"><div><h2>Portrait Studio</h2><p>Upload your own reference or generate locally through Stable Diffusion WebUI/AUTOMATIC1111.</p></div></div>
              <div className="portrait-studio-grid">
                <label className="wide">Image prompt<textarea rows={5} value={portraitPrompt} onChange={(event) => setPortraitPrompt(event.target.value)} placeholder="Describe the character as you want them visualized…" /></label>
                <label>Stable Diffusion server<input value={imageSettings.base_url} onChange={(event) => setImageSettings({ ...imageSettings, base_url: event.target.value })} /></label>
                <label>Steps<input type="number" min="5" max="100" value={imageSettings.steps} onChange={(event) => setImageSettings({ ...imageSettings, steps: Number(event.target.value) })} /></label>
                <label>Width<input type="number" min="256" max="1536" step="64" value={imageSettings.width} onChange={(event) => setImageSettings({ ...imageSettings, width: Number(event.target.value) })} /></label>
                <label>Height<input type="number" min="256" max="1536" step="64" value={imageSettings.height} onChange={(event) => setImageSettings({ ...imageSettings, height: Number(event.target.value) })} /></label>
                <label>CFG scale<input type="number" min="1" max="30" step="0.5" value={imageSettings.cfg_scale} onChange={(event) => setImageSettings({ ...imageSettings, cfg_scale: Number(event.target.value) })} /></label>
                <label className="wide">Negative prompt<textarea rows={3} value={imageSettings.negative_prompt} onChange={(event) => setImageSettings({ ...imageSettings, negative_prompt: event.target.value })} /></label>
              </div>
              <div className="portrait-studio-actions">
                <button type="button" onClick={() => void generatePortraitPrompt()} disabled={busy}>AI build prompt from canon</button>
                <button type="button" className="primary" onClick={() => void generatePortrait()} disabled={busy || !portraitPrompt.trim()}>{busy ? 'Working…' : 'Generate portrait locally'}</button>
              </div>
              {portrait && <small className="center-help">Current image: {portrait.width}×{portrait.height} · {portrait.source.replaceAll('_', ' ')} · saved inside the project at {portrait.relative_path}</small>}
            </section>
          </div>
        )}
      </div>

      {error && <div className="center-error">{error}</div>}
    </section>
  )
}
