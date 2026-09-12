import { useState } from 'react'

import { resolveActiveProject } from './capture-store'
import type { VoiceProfile } from './CraftPanel'
import StyleFidelityEditor, { type StyleFidelity } from './StyleFidelityEditor'

const API = 'http://127.0.0.1:8000/api'

type Provider = { provider: 'ollama' | 'openai_compatible'; base_url: string; model: string; api_key?: string }
type Result = { profile: VoiceProfile; style_fidelity: StyleFidelity | null; saved_path: string; source_files: string[] }

export default function VoiceFingerprintOverlay() {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('Book voice')
  const [result, setResult] = useState<Result | null>(null)
  const [status, setStatus] = useState('')
  const [busy, setBusy] = useState(false)

  async function openLab() {
    setOpen(true)
    const project = await resolveActiveProject()
    if (!project) return
    try {
      const [voiceResponse, fidelityResponse] = await Promise.all([
        fetch(`${API}/projects/${project.slug}/voice-profile`),
        fetch(`${API}/projects/${project.slug}/style-fidelity`),
      ])
      const voice = voiceResponse.ok ? await voiceResponse.json() as VoiceProfile | null : null
      const fidelity = fidelityResponse.ok ? await fidelityResponse.json() as StyleFidelity | null : null
      if (voice) {
        setName(voice.name || 'Book voice')
        setResult({ profile: voice, style_fidelity: fidelity, saved_path: 'style/voice-profile.json', source_files: [] })
      }
    } catch {
      // A missing fingerprint is a valid first-use state.
    }
  }

  async function learn() {
    const project = await resolveActiveProject()
    if (!project) return setStatus('Open a story project first.')
    const raw = localStorage.getItem('emberwriter.provider')
    const provider = raw ? JSON.parse(raw) as Provider : null
    if (!provider?.model || !provider.base_url) return setStatus('Choose an AI model in Ember first.')
    setBusy(true)
    setStatus('Learning voice across the manuscript…')
    try {
      const response = await fetch(`${API}/projects/${project.slug}/voice/analyze-project`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider, profile_name: name.trim() || 'Book voice' }),
      })
      const body = await response.json()
      if (!response.ok) throw new Error(body.detail || `${response.status} ${response.statusText}`)
      setResult(body as Result)
      setStatus('Voice Fingerprint and Style Fidelity saved. Voice Lock will use both on the next generation.')
    } catch (cause) {
      setStatus((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function saveFidelity(next: StyleFidelity) {
    const project = await resolveActiveProject()
    if (!project) throw new Error('Open a story project first.')
    const response = await fetch(`${API}/projects/${project.slug}/style-fidelity`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(next),
    })
    const body = await response.json()
    if (!response.ok) throw new Error(body.detail || `${response.status} ${response.statusText}`)
    setResult((current) => current ? { ...current, style_fidelity: body as StyleFidelity } : current)
    setStatus('Author style rules saved. They now override learned defaults during Voice Lock.')
  }

  return <>
    <button type="button" className="voice-fingerprint-fab" onClick={() => void openLab()} title="Learn author voice">✍ Voice</button>
    {open && <div className="capture-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setOpen(false) }}>
      <section className="capture-modal voice-fingerprint-modal" role="dialog" aria-modal="true" aria-label="Voice Fingerprint">
        <header><div><small>VOICE LAB</small><h2>Learn the author, not “AI style”</h2><p>Samples across the manuscript, measures cadence, and saves author-owned Voice Lock rules.</p></div><button type="button" onClick={() => setOpen(false)}>×</button></header>
        <div className="voice-fingerprint-body">
          <label>Profile name<input value={name} onChange={(event) => setName(event.target.value)} /></label>
          <button type="button" className="primary" disabled={busy || !name.trim()} onClick={() => void learn()}>{busy ? 'Learning across manuscript…' : 'Learn from manuscript'}</button>
          <small>Ember samples multiple chapters and positions across the book, then learns cadence, diction, dialogue, interiority, POV distance, imagery, human quirks, and generic model habits to avoid.</small>
          {status && <div className="capture-status">{status}</div>}
          {result && <article className="voice-fingerprint-card"><h3>{result.profile.name}</h3><p>{result.profile.prose_directive}</p><div><b>Rhythm</b><span>{result.profile.sentence_rhythm}</span></div><div><b>Dialogue</b><span>{result.profile.dialogue}</span></div><div><b>Relationship voice</b><span>{result.profile.sensual_voice}</span></div><div><b>Signature</b><span>{result.profile.signature_traits.join(' · ')}</span></div><div><b>Avoid</b><span>{result.profile.avoidances.join(' · ')}</span></div>{result.source_files.length > 0 && <small>{result.source_files.length} manuscript sources sampled</small>}</article>}
          {result?.style_fidelity && <StyleFidelityEditor value={result.style_fidelity} disabled={busy} onSave={saveFidelity} />}
        </div>
      </section>
    </div>}
  </>
}
