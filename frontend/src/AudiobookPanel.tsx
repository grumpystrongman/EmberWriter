import { useEffect, useState } from 'react'
import './audiobook-panel.css'

type Chapter = { path: string; words: number; narratable: boolean }
type Rendered = { source_path: string; filename: string; voice: string; bytes: number; words: number }
type VoiceResult = { engine: string; voices: string[]; privacy: string; quality: string }
type Props = { apiBase: string; slug: string; disabled: boolean }

export default function AudiobookPanel({ apiBase, slug, disabled }: Props) {
  const endpoint = `${apiBase}/projects/${encodeURIComponent(slug)}/audiobook`
  const [chapters, setChapters] = useState<Chapter[]>([])
  const [voices, setVoices] = useState<string[]>([])
  const [renders, setRenders] = useState<Rendered[]>([])
  const [voice, setVoice] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [selected, setSelected] = useState('')

  async function getJson<T>(path: string, options?: RequestInit): Promise<T> {
    const response = await fetch(endpoint + path, {
      ...options, headers: { 'Content-Type': 'application/json', ...(options?.headers ?? {}) },
    })
    if (!response.ok) {
      const detail = await response.json().catch(() => ({}))
      throw new Error(detail.detail || `Request failed: ${response.status}`)
    }
    return response.json() as Promise<T>
  }

  async function reload() {
    const [files, tracks] = await Promise.all([
      getJson<Chapter[]>('/chapters'), getJson<Rendered[]>('/renders'),
    ])
    setChapters(files)
    setRenders(tracks)
    if (!files.some(ch => ch.path === selected)) {
      setSelected(files.find(ch => ch.narratable)?.path || '')
    }
  }
  useEffect(() => {
    let live = true
    setChapters([]); setRenders([]); setVoices([]); setMessage(''); setError('')
    void Promise.all([getJson<Chapter[]>('/chapters'), getJson<Rendered[]>('/renders'), getJson<VoiceResult>('/voices')])
      .then(([files, tracks, speech]) => {
        if (live) {
          setChapters(files); setRenders(tracks); setVoices(speech.voices)
          setSelected(files.find(ch => ch.narratable)?.path || '')
          setVoice(speech.voices[0] || '')
        }
      }).catch(e => { if (live) setError(String(e)) })
    return () => { live = false }
  }, [endpoint])

  async function render() {
    setBusy(true); setError(''); setMessage('')
    try {
      const result = await getJson<Rendered>('/renders', {
        method: 'POST', body: JSON.stringify({ path: selected, voice }),
      })
      setMessage(`Narrated ${selected}. Your offline audio file is ready to download.`)
      await reload()
      setSelected(result.source_path)
    } catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }

  return <details className="authoring-panel audiobook-panel">
    <summary>Audiobook Workshop <small>OFFLINE · LOCAL NARRATION · MP3/WAV</small></summary>
    <div className="authoring-panel-body">
      <div className="audiobook-intro">
        <strong>Hear your story come alive.</strong>
        <p>Generate narrated chapter audio using installed Windows voices without sending manuscript text to a cloud service. This is a first-pass audiobook studio; voice acting, sound mastering and multi-actor dialogue are future production enhancements.</p>
      </div>
      {error && <p role="alert" className="audiobook-alert">{error}</p>}
      {message && <p role="status" className="audiobook-success">{message}</p>}
      <label htmlFor="audio-source">Manuscript chapter</label>
      <select id="audio-source" value={selected} disabled={disabled || busy} onChange={e => setSelected(e.target.value)}>
        <option value="">Select a chapter</option>
        {chapters.map(ch => <option key={ch.path} value={ch.path} disabled={!ch.narratable}>{ch.path} ({ch.words} words)</option>)}
      </select>
      <label htmlFor="audio-voice">Installed offline voice</label>
      <select id="audio-voice" value={voice} disabled={disabled || busy} onChange={e => setVoice(e.target.value)}>
        {voices.length === 0 && <option value="">System default voice</option>}
        {voices.map(v => <option key={v} value={v}>{v}</option>)}
      </select>
      <div className="audiobook-toolbar">
        <button type="button" disabled={disabled || busy || !selected} onClick={() => void render()}>{busy ? 'Narrating chapter…' : 'Render selected chapter'}</button>
        <button type="button" disabled={disabled || busy} onClick={() => void reload().catch(e => setError(String(e)))}>Refresh chapters</button>
        {renders.length > 0 && <a href={endpoint + '/export'} download>Download chapter audiobook ZIP</a>}
      </div>
      {renders.length > 0 && <div className="audiobook-tracks">
        <h3>Narrated chapters</h3>
        {renders.map(track => <div className="audiobook-track" key={track.source_path}>
          <div><strong>{track.source_path}</strong><small>{track.voice} · {(track.bytes / 1024 / 1024).toFixed(1)} MB</small></div>
          <audio controls preload="none" src={endpoint + '/files/' + encodeURIComponent(track.filename)} aria-label={track.source_path} />
          <a href={endpoint + '/files/' + encodeURIComponent(track.filename)} download>Download</a>
        </div>)}
      </div>}
      <p className="audiobook-note">Each track stays inside this project. MP3 is produced when FFmpeg is installed; otherwise EmberWriter delivers WAV. The exported ZIP contains chapter audio and a manifest, not a mastered M4B retail audiobook.</p>
    </div>
  </details>
}
