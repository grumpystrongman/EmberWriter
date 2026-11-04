import { useEffect, useState } from 'react'
import './audiobook-panel.css'

type Chapter = { path: string; words: number; narratable: boolean }
type Rendered = { source_path: string; filename: string; voice: string; bytes: number; words: number }
type VoiceResult = { engine: string; voices: string[]; privacy: string; quality: string }
type AudioQuality = { status: string; ready: boolean; m4b_available: boolean; total_tracks: number; verified_tracks: number; duration_seconds: number; issues: {path:string; detail:string}[]; tracks: {path:string; seconds: number | null; format?:string; checks:string[]}[]; disclaimer:string }
type AudioJob = { exists: boolean; status: string; active: boolean; total?: number; completed?: number; current?: string | null; message?: string; chapters?: { path: string; title: string; status: string; words: number }[] }
type Props = { apiBase: string; slug: string; disabled: boolean }

export default function AudiobookPanel({ apiBase, slug, disabled }: Props) {
  const endpoint = `${apiBase}/projects/${encodeURIComponent(slug)}/audiobook`
  const jobEndpoint = `${apiBase}/projects/${encodeURIComponent(slug)}/audiobook-jobs`
  const [chapters, setChapters] = useState<Chapter[]>([])
  const [voices, setVoices] = useState<string[]>([])
  const [renders, setRenders] = useState<Rendered[]>([])
  const [job, setJob] = useState<AudioJob | null>(null)
  const [voice, setVoice] = useState('')
  const [rate, setRate] = useState(-1)
  const [quality, setQuality] = useState<AudioQuality | null>(null)
  const [showTracks, setShowTracks] = useState(false)
  const [showAudioChapters, setShowAudioChapters] = useState(false)
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

  async function getJob(): Promise<AudioJob> {
    const response = await fetch(jobEndpoint)
    if (!response.ok) throw new Error(`Audiobook job status: ${response.status}`)
    return response.json() as Promise<AudioJob>
  }
  async function jobAction(action: 'start' | 'pause' | 'resume') {
    setBusy(true); setError(''); setMessage('')
    try {
      const response = await fetch(jobEndpoint + '/' + action, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(action === 'start' ? { voice, rate } : {}),
      })
      if (!response.ok) {
        const body = await response.json().catch(() => ({}))
        throw new Error(body.detail || `Audio job error: ${response.status}`)
      }
      const next = await response.json() as AudioJob
      setJob(next)
      setMessage(next.message || 'Audiobook job updated.')
    } catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }
  async function reload() {
    const [files, tracks] = await Promise.all([
      getJson<Chapter[]>('/chapters'), getJson<Rendered[]>('/renders'),
    ])
    setChapters(files)
    setRenders(tracks)
    setJob(await getJob())
    if (!files.some(ch => ch.path === selected)) {
      setSelected(files.find(ch => ch.narratable)?.path || '')
    }
  }
  useEffect(() => {
    let live = true
    setChapters([]); setRenders([]); setVoices([]); setJob(null); setMessage(''); setError(''); setQuality(null); setShowAudioChapters(false)
    void Promise.all([getJson<Chapter[]>('/chapters'), getJson<Rendered[]>('/renders'), getJson<VoiceResult>('/voices')])
      .then(([files, tracks, speech]) => {
        if (live) {
          setChapters(files); setRenders(tracks); setVoices(speech.voices)
          setSelected(files.find(ch => ch.narratable)?.path || '')
          setVoice(speech.voices[0] || '')
        }
      }).catch(e => { if (live) setError(String(e)) })
    void getJob().then(value => { if (live) setJob(value) }).catch(() => {})
    const timer = window.setInterval(() => {
      void Promise.all([getJob(), getJson<Rendered[]>('/renders')]).then(([nextJob, tracks]) => {
        if (live) { setJob(nextJob); setRenders(tracks) }
      }).catch(() => {})
    }, 3000)
    return () => { live = false; window.clearInterval(timer) }
  }, [endpoint])

  async function inspectAudio() {
    setBusy(true); setError('')
    try {
      const response = await fetch(jobEndpoint + '/quality')
      if (!response.ok) throw new Error('Audiobook quality scan failed: ' + response.status)
      setQuality(await response.json() as AudioQuality)
    } catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }

  async function render() {
    setBusy(true); setError(''); setMessage('')
    try {
      const result = await getJson<Rendered>('/renders', {
        method: 'POST', body: JSON.stringify({ path: selected, voice, rate }),
      })
      setMessage(`Narrated ${selected}. Your offline audio file is ready to download.`)
      await reload()
      setQuality(null)
      setSelected(result.source_path)
    } catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }

  return <section className="authoring-panel audiobook-panel">
    <header className="audiobook-heading"><h2>Audiobook Workshop</h2><small>OFFLINE · LOCAL NARRATION · MP3/WAV</small></header>
    <div className="authoring-panel-body">
      <div className="audiobook-intro">
        <strong>Hear your story come alive.</strong>
        <p>Generate narrated chapter audio using installed Windows voices without sending manuscript text to a cloud service. This is a first-pass audiobook studio; voice acting, sound mastering and multi-actor dialogue are future production enhancements.</p>
      </div>
      {error && <p role="alert" className="audiobook-alert">{error}</p>}
      {message && <p role="status" className="audiobook-success">{message}</p>}
      <label htmlFor="audio-voice">Installed offline voice</label>
      <select id="audio-voice" value={voice} disabled={disabled || busy} onChange={e => setVoice(e.target.value)}>
        {voices.length === 0 && <option value="">System default voice</option>}
        {voices.map(v => <option key={v} value={v}>{v}</option>)}
      </select>
      <label htmlFor="audio-rate">Narration pacing (Windows SAPI rate: {rate > 0 ? '+' : ''}{rate})</label>
      <input id="audio-rate" type="range" min="-5" max="5" step="1" value={rate}
        disabled={disabled || busy || !!job?.active} onChange={e => setRate(Number(e.target.value))} />
      <p className="audiobook-rate-hint">Slower −5 · default −1 · faster +5. Changing speed creates a new track; existing audio is not altered.</p>
      <div className="audiobook-job-panel">
        <div><h3>Whole-book narration queue</h3>
          <p>Use the current Binder Draft order to narrate all selected manuscript chapters. This offline job persists while you close the browser, and can pause or recover after restarting the app.</p></div>
        <div className="audiobook-job-buttons">
          <button type="button" disabled={disabled || busy || !!job?.active || job?.status === 'queued' || job?.status === 'running'} onClick={() => void jobAction('start')}>Narrate entire book</button>
          {(job?.status === 'queued' || job?.status === 'running') && <button type="button" disabled={disabled || busy} onClick={() => void jobAction('pause')}>Pause after chapter</button>}
          {(job?.status === 'paused' || job?.status === 'interrupted' || job?.status === 'needs_attention') && <button type="button" disabled={disabled || busy || !!job.active} onClick={() => void jobAction('resume')}>Resume saved batch</button>}
          {job?.status === 'completed' && <a href={jobEndpoint + '/export'} download="emberwriter-whole-book-audiobook.zip">Download Binder-ordered audiobook ZIP</a>}
          <button type="button" disabled={busy || disabled} onClick={() => void inspectAudio()}>Check audio readiness</button>
        </div>
        {job?.exists && <div className="audiobook-job-progress" role="status" aria-live="polite">
          <strong>{job.status}: {job.completed ?? 0} / {job.total ?? 0} chapters</strong>
          <progress max={Math.max(1, job.total ?? 1)} value={job.completed ?? 0} />
          <p>{job.message} {job.current ? `(Now narrating ${job.current})` : ''}</p>
          {!!job.chapters?.length && <details className="audiobook-chapter-ledger">
            <summary>Chapter narration ledger ({job.chapters.length})</summary>
            {job.chapters.slice(0, showAudioChapters ? undefined : 12).map((chapter, index) => <div key={chapter.path} className="audiobook-job-chapter"><small>{index + 1}. {chapter.title}</small><span>{chapter.status}</span></div>)}
            {!showAudioChapters && job.chapters.length > 12 && <button type="button" onClick={() => setShowAudioChapters(true)}>Show all {job.chapters.length} chapters</button>}
          </details>}
        </div>}
      </div>
      <details className="audiobook-single-chapter">
        <summary>Render or replace an individual chapter</summary>
      <label htmlFor="audio-source">Manuscript chapter</label>
      <select id="audio-source" value={selected} disabled={disabled || busy} onChange={e => setSelected(e.target.value)}>
        <option value="">Select a chapter</option>
        {chapters.map(ch => <option key={ch.path} value={ch.path} disabled={!ch.narratable}>{ch.path} ({ch.words} words)</option>)}
      </select>
      <div className="audiobook-toolbar">
        <button type="button" disabled={disabled || busy || !!job?.active || !selected} onClick={() => void render()}>{busy ? 'Narrating chapter…' : 'Render selected chapter'}</button>
        <button type="button" disabled={disabled || busy} onClick={() => void reload().catch(e => setError(String(e)))}>Refresh chapters</button>
        {renders.length > 0 && <a href={endpoint + '/export'} download>Download chapter audiobook ZIP</a>}
      </div>
      </details>
      {quality && <section className="audiobook-quality" aria-live="polite">
        <h3>{quality.ready ? 'Audio technical checks passed' : 'Audio needs review'}</h3>
        <p>{quality.verified_tracks}/{quality.total_tracks} verified tracks · {Math.round(quality.duration_seconds / 60)} minutes detected</p>
        {quality.ready && quality.m4b_available && job?.status === "completed" && <a className="audiobook-m4b-download"
          href={jobEndpoint + "/export.m4b"} download="emberwriter-whole-book-audiobook.m4b">Build chapter-marked M4B (offline AAC)</a>}
        {!quality.m4b_available && <p>Install FFmpeg and FFprobe locally to enable a single chapter-marked M4B.</p>}
        {quality.issues.length > 0 && <div className="audiobook-quality-warnings">{quality.issues.slice(0, 35).map((issue, i) =>
          <p key={i}><strong>{issue.path || 'Whole book'}:</strong> {issue.detail}</p>)}</div>}
        {quality.issues.length > 35 && <p>Additional issues not shown. Recheck after addressing the first 35.</p>}
        <p>{quality.disclaimer}</p>
      </section>}
      {renders.length > 0 && <details className="audiobook-tracks" open={showTracks} onToggle={e => setShowTracks(e.currentTarget.open)}>
        <summary>Narrated chapter playback and downloads ({renders.length})</summary>
        {renders.map(track => <div className="audiobook-track" key={track.source_path}>
          <div><strong>{track.source_path}</strong><small>{track.voice} · {(track.bytes / 1024 / 1024).toFixed(1)} MB</small></div>
          <audio controls preload="none" src={endpoint + '/files/' + encodeURIComponent(track.filename)} aria-label={track.source_path} />
          <a href={endpoint + '/files/' + encodeURIComponent(track.filename)} download>Download</a>
        </div>)}
      </details>}
      <p className="audiobook-note">Each track stays inside this project. MP3 is produced when FFmpeg is installed; otherwise EmberWriter delivers WAV. The exported ZIP contains chapter audio and a manifest, not a mastered M4B retail audiobook.</p>
    </div>
  </section>
}
