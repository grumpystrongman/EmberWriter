import { useEffect, useMemo, useState } from 'react'

import type { ProviderConfig, WorkspaceProject } from './workspace-types'
import type { VisualAsset } from './story-atlas-types'

type Props = {
  apiBase: string
  project: WorkspaceProject
}

type PromptResponse = {
  prompt: string
  negative_prompt: string
  continuity_notes: string[]
  context_sources: string[]
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
    const parsed = JSON.parse(localStorage.getItem('emberwriter.provider') || 'null') as ProviderConfig | null
    return parsed?.model?.trim() && parsed.base_url?.trim() ? parsed : null
  } catch {
    return null
  }
}

function slugify(value: string) {
  return value.toLowerCase().trim().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'visual'
}

export default function VisualStudioPanel({ apiBase, project }: Props) {
  const [assets, setAssets] = useState<VisualAsset[]>([])
  const [subject, setSubject] = useState('')
  const [kind, setKind] = useState('location')
  const [instruction, setInstruction] = useState('Create a faithful, cinematic reference image that is useful while writing scenes.')
  const [chapter, setChapter] = useState('0')
  const [prompt, setPrompt] = useState('')
  const [negativePrompt, setNegativePrompt] = useState('')
  const [notes, setNotes] = useState<string[]>([])
  const [sources, setSources] = useState<string[]>([])
  const [assetId, setAssetId] = useState('')
  const [sdUrl, setSdUrl] = useState(() => localStorage.getItem('emberwriter.sd_url') || 'http://127.0.0.1:7860')
  const [width, setWidth] = useState(1024)
  const [height, setHeight] = useState(768)
  const [steps, setSteps] = useState(30)
  const [referenceAssetId, setReferenceAssetId] = useState('')
  const [denoising, setDenoising] = useState(0.45)
  const [selectedAssetId, setSelectedAssetId] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const selectedAsset = assets.find((item) => item.asset_id === selectedAssetId) || null
  const canonicalAssets = useMemo(() => assets.filter((item) => item.canon_status === 'canonical'), [assets])

  useEffect(() => { void loadAssets() }, [project.slug])
  useEffect(() => {
    if (!assetId || assetId.startsWith('visual-')) setAssetId(slugify(subject || 'visual'))
  }, [subject])

  async function loadAssets() {
    setError('')
    try {
      const loaded = await request<VisualAsset[]>(`${apiBase}/projects/${project.slug}/visual-assets`)
      setAssets(loaded)
      setSelectedAssetId((current) => current && loaded.some((item) => item.asset_id === current) ? current : loaded[0]?.asset_id || '')
    } catch (cause) {
      setError((cause as Error).message)
    }
  }

  async function composePrompt() {
    const provider = currentProvider()
    if (!provider) {
      setError('Choose an AI model before composing a canon-aware image prompt.')
      return
    }
    if (!subject.trim()) {
      setError('Name the character, place, object, or scene you want to visualize.')
      return
    }
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const response = await request<PromptResponse>(`${apiBase}/projects/${project.slug}/visual-assets/compose-prompt`, {
        method: 'POST',
        body: JSON.stringify({
          subject: subject.trim(),
          kind,
          instruction,
          chapter: Math.max(0, Number.parseInt(chapter, 10) || 0),
          provider,
        }),
      })
      setPrompt(response.prompt)
      setNegativePrompt(response.negative_prompt)
      setNotes(response.continuity_notes)
      setSources(response.context_sources)
      setAssetId((current) => current.trim() || slugify(subject))
      setNotice(`Prompt grounded in ${response.context_sources.length} story source${response.context_sources.length === 1 ? '' : 's'}.`)
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function generateImage() {
    if (!prompt.trim() || !subject.trim()) {
      setError('Compose or enter an image prompt first.')
      return
    }
    const id = slugify(assetId || subject)
    localStorage.setItem('emberwriter.sd_url', sdUrl.trim())
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const created = await request<VisualAsset>(`${apiBase}/projects/${project.slug}/visual-assets/generate`, {
        method: 'POST',
        body: JSON.stringify({
          asset_id: id,
          title: subject.trim(),
          kind,
          prompt,
          negative_prompt: negativePrompt,
          base_url: sdUrl.trim(),
          width,
          height,
          steps,
          cfg_scale: 7,
          seed: -1,
          canon_status: 'concept',
          linked_entities: [subject.trim()],
          reference_asset_id: referenceAssetId || null,
          denoising_strength: denoising,
        }),
      })
      setAssets((current) => [created, ...current.filter((item) => item.asset_id !== created.asset_id)])
      setSelectedAssetId(created.asset_id)
      setNotice(referenceAssetId ? 'Generated from the selected visual reference. Review it before promoting to Canonical.' : 'Concept generated. Review it before promoting to Canonical.')
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function uploadReference(file: File) {
    const id = slugify(assetId || subject || file.name.replace(/\.[^.]+$/, ''))
    const body = new FormData()
    body.append('image', file)
    setBusy(true)
    setError('')
    try {
      const params = new URLSearchParams({ title: subject.trim() || file.name, kind })
      const response = await fetch(`${apiBase}/projects/${project.slug}/visual-assets/${id}/upload?${params}`, { method: 'POST', body })
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}))
        throw new Error(payload.detail || `${response.status} ${response.statusText}`)
      }
      const created = await response.json() as VisualAsset
      setAssets((current) => [created, ...current.filter((item) => item.asset_id !== created.asset_id)])
      setSelectedAssetId(created.asset_id)
      setReferenceAssetId(created.asset_id)
      setAssetId(created.asset_id)
      setNotice('Reference image added. You can now use it to anchor img2img generations.')
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function updateAsset(asset: VisualAsset, patch: Partial<Pick<VisualAsset, 'canon_status' | 'notes' | 'linked_entities' | 'title' | 'kind'>>) {
    setBusy(true)
    setError('')
    try {
      const updated = await request<VisualAsset>(`${apiBase}/projects/${project.slug}/visual-assets/${asset.asset_id}/metadata`, {
        method: 'PUT',
        body: JSON.stringify(patch),
      })
      setAssets((current) => current.map((item) => item.asset_id === updated.asset_id ? updated : item))
      setNotice(updated.canon_status === 'canonical' ? 'Canonical visual approved. Future canon-aware prompts can reuse its established visual details.' : 'Visual metadata updated.')
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function deleteAsset(asset: VisualAsset) {
    setBusy(true)
    setError('')
    try {
      const response = await fetch(`${apiBase}/projects/${project.slug}/visual-assets/${asset.asset_id}`, { method: 'DELETE' })
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}))
        throw new Error(payload.detail || `${response.status} ${response.statusText}`)
      }
      setAssets((current) => current.filter((item) => item.asset_id !== asset.asset_id))
      setSelectedAssetId('')
      if (referenceAssetId === asset.asset_id) setReferenceAssetId('')
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  function reuseAsset(asset: VisualAsset) {
    setSubject(asset.title)
    setKind(asset.kind)
    setPrompt(asset.prompt)
    setNegativePrompt(asset.negative_prompt)
    setReferenceAssetId(asset.asset_id)
    setAssetId(`${asset.asset_id}-variation`)
    setSelectedAssetId(asset.asset_id)
    setNotice('Reference loaded. Adjust the direction or prompt, then generate a controlled variation.')
  }

  return (
    <div className="visual-studio">
      <div className="visual-studio-grid">
        <section className="visual-composer atlas-panel">
          <div className="atlas-panel-heading"><div><strong>AI Visual Director</strong><small>Compose from canon first, then generate. The model receives relevant Story Memory, World Bible, Atlas geography, and approved canonical visual prompts.</small></div><button type="button" className="primary" onClick={() => void composePrompt()} disabled={busy}>✦ Compose from canon</button></div>
          <div className="visual-form-grid">
            <label className="visual-span-2">Subject <input value={subject} onChange={(event) => setSubject(event.target.value)} placeholder="Redwater Bridge, Sera, the ritual chamber…" /></label>
            <label>Type <select value={kind} onChange={(event) => setKind(event.target.value)}><option value="location">Location</option><option value="character">Character</option><option value="scene">Scene</option><option value="object">Object / relic</option><option value="faction">Faction</option><option value="map">Map / diagram</option><option value="reference">Reference</option></select></label>
            <label>Chapter <input type="number" min="0" value={chapter} onChange={(event) => setChapter(event.target.value)} /></label>
            <label className="visual-span-2">Direction <textarea value={instruction} onChange={(event) => setInstruction(event.target.value)} /></label>
          </div>
          <label>Positive prompt <textarea className="visual-prompt" value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder="AI-composed production prompt…" /></label>
          <label>Negative prompt <textarea value={negativePrompt} onChange={(event) => setNegativePrompt(event.target.value)} placeholder="Contradictions and unwanted visual elements…" /></label>
          {(notes.length > 0 || sources.length > 0) && <div className="visual-grounding"><div><strong>Continuity notes</strong>{notes.length ? notes.map((note) => <p key={note}>• {note}</p>) : <p>No continuity warnings.</p>}</div><div><strong>Grounding sources</strong>{sources.length ? sources.map((source) => <span key={source}>{source}</span>) : <p>No matching sources found; treat visual specifics as exploratory.</p>}</div></div>}
        </section>

        <aside className="visual-generator atlas-panel">
          <div className="atlas-panel-heading"><strong>Render</strong><span>Stable Diffusion WebUI</span></div>
          <label>Asset ID <input value={assetId} onChange={(event) => setAssetId(slugify(event.target.value))} /></label>
          <label>Server <input value={sdUrl} onChange={(event) => setSdUrl(event.target.value)} /></label>
          <div className="atlas-two"><label>Width <input type="number" min="256" max="2048" step="64" value={width} onChange={(event) => setWidth(Math.max(256, Math.min(2048, Number(event.target.value) || 1024)))} /></label><label>Height <input type="number" min="256" max="2048" step="64" value={height} onChange={(event) => setHeight(Math.max(256, Math.min(2048, Number(event.target.value) || 768)))} /></label></div>
          <label>Steps <input type="range" min="5" max="60" value={steps} onChange={(event) => setSteps(Number(event.target.value))} /><b>{steps}</b></label>
          <label>Visual reference <select value={referenceAssetId} onChange={(event) => setReferenceAssetId(event.target.value)}><option value="">None — text to image</option>{assets.map((asset) => <option key={asset.asset_id} value={asset.asset_id}>{asset.title} · {asset.canon_status}</option>)}</select></label>
          {referenceAssetId && <label>Reference strength <input type="range" min="0.1" max="0.85" step="0.05" value={denoising} onChange={(event) => setDenoising(Number(event.target.value))} /><b>{denoising.toFixed(2)}</b><small>Lower preserves more of the reference; higher allows larger changes.</small></label>}
          <button type="button" className="primary visual-generate" onClick={() => void generateImage()} disabled={busy || !prompt.trim()}>{busy ? 'Working…' : referenceAssetId ? 'Generate referenced variation' : 'Generate concept'}</button>
          <label className="visual-upload">Or add an existing reference<input type="file" accept="image/png,image/jpeg,image/webp" disabled={busy} onChange={(event) => { const file = event.target.files?.[0]; if (file) void uploadReference(file); event.currentTarget.value = '' }} /></label>
          <p className="visual-policy-note"><b>Promotion is deliberate.</b> Generated images start as Concept. Uploads start as Reference. Only you can mark an image Canonical.</p>
        </aside>
      </div>

      <section className="visual-library atlas-panel">
        <div className="atlas-panel-heading"><div><strong>Visual Canon Library</strong><small>{assets.length} assets · {canonicalAssets.length} canonical</small></div><button type="button" onClick={() => void loadAssets()} disabled={busy}>↻ Refresh</button></div>
        {!assets.length && <div className="atlas-empty visual-empty"><strong>No visual references yet.</strong><p>Compose a prompt from canon, generate a concept, or upload an existing reference.</p></div>}
        <div className="visual-card-grid">{assets.map((asset) => <article className={`visual-card ${selectedAssetId === asset.asset_id ? 'selected' : ''}`} key={asset.asset_id} onClick={() => setSelectedAssetId(asset.asset_id)}>
          <img src={`${apiBase}/projects/${project.slug}/visual-assets/${asset.asset_id}?v=${encodeURIComponent(asset.generated_at)}`} alt={asset.title} />
          <div className="visual-card-body"><div><strong>{asset.title}</strong><span className={`visual-status ${asset.canon_status}`}>{asset.canon_status}</span></div><small>{asset.kind} · {asset.width}×{asset.height}{asset.reference_asset_id ? ` · from ${asset.reference_asset_id}` : ''}</small><p>{asset.prompt || asset.notes || 'Uploaded reference image.'}</p><div className="visual-card-actions"><button type="button" onClick={(event) => { event.stopPropagation(); reuseAsset(asset) }}>Use as reference</button>{asset.canon_status !== 'canonical' ? <button type="button" onClick={(event) => { event.stopPropagation(); void updateAsset(asset, { canon_status: 'canonical' }) }}>Set Canonical</button> : <button type="button" onClick={(event) => { event.stopPropagation(); void updateAsset(asset, { canon_status: 'reference' }) }}>Unmark canon</button>}<button type="button" className="danger" onClick={(event) => { event.stopPropagation(); void deleteAsset(asset) }}>Delete</button></div></div>
        </article>)}</div>
      </section>

      {selectedAsset && <section className="visual-detail atlas-panel"><div className="atlas-panel-heading"><div><strong>{selectedAsset.title}</strong><small>{selectedAsset.asset_id}</small></div><span className={`visual-status ${selectedAsset.canon_status}`}>{selectedAsset.canon_status}</span></div><div className="visual-detail-grid"><img src={`${apiBase}/projects/${project.slug}/visual-assets/${selectedAsset.asset_id}?v=${encodeURIComponent(selectedAsset.generated_at)}`} alt={selectedAsset.title} /><div><label>Linked story entities <input value={selectedAsset.linked_entities.join(', ')} onChange={(event) => setAssets((current) => current.map((item) => item.asset_id === selectedAsset.asset_id ? { ...item, linked_entities: event.target.value.split(',').map((value) => value.trim()).filter(Boolean) } : item))} onBlur={() => { const current = assets.find((item) => item.asset_id === selectedAsset.asset_id); if (current) void updateAsset(current, { linked_entities: current.linked_entities }) }} /></label><label>Notes <textarea value={selectedAsset.notes} onChange={(event) => setAssets((current) => current.map((item) => item.asset_id === selectedAsset.asset_id ? { ...item, notes: event.target.value } : item))} onBlur={() => { const current = assets.find((item) => item.asset_id === selectedAsset.asset_id); if (current) void updateAsset(current, { notes: current.notes }) }} placeholder="What this image establishes visually…" /></label><p><b>Source:</b> {selectedAsset.source}</p>{selectedAsset.reference_asset_id && <p><b>Derived from:</b> {selectedAsset.reference_asset_id}</p>}</div></div></section>}

      {(error || notice) && <div className={error ? 'center-error' : 'atlas-notice'}>{error || notice}</div>}
    </div>
  )
}
