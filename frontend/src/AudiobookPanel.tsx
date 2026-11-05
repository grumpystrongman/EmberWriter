import { useEffect, useRef, useState } from 'react'
import './audiobook-panel.css'
import NeuralVoicePanel from './NeuralVoicePanel'
import AuthorProductionDesk from './AuthorProductionDesk'
import LocalKokoroPanel from './LocalKokoroPanel'

type Chapter = { path: string; words: number; narratable: boolean }
type Rendered = { source_path: string; filename: string; voice: string; bytes: number; words: number }
type VoiceResult = { engine: string; voices: string[]; privacy: string; quality: string }
type AudioMastering = {status:string; tracks: {path:string;title:string;integrated_lufs:number|null;true_peak_dbtp:number|null;loudness_range_lu:number|null;rms_dbfs?:number|null;longest_quiet_seconds?:number}[];warnings:{path:string;detail:string}[];target_lufs:number;true_peak_target_dbtp:number;disclaimer:string}
type AudioQuality = { status: string; ready: boolean; m4b_available: boolean; total_tracks: number; verified_tracks: number; duration_seconds: number; issues: {path:string; detail:string}[]; tracks: {path:string; seconds: number | null; format?:string; checks:string[]}[]; disclaimer:string }
type M4BJob = { exists: boolean; status: string; active: boolean; mode?: string; filename?: string; downloadable?: boolean; message?: string }
type AudioJob = { exists: boolean; status: string; active: boolean; total?: number; completed?: number; current?: string | null; message?: string; chapters?: { path: string; title: string; status: string; words: number }[] }
type AudioRule = { written: string; spoken: string }
type AudioProof = { id: string; path: string; seconds: number; note: string; status: string; filename: string }
type CastSpan = { start:number; end:number; text:string; voice:string; character?:string; rate?:number }
type SuggestedCast = {path:string;start:number;end:number;text:string;character:string;confidence:string}
type ProofApproval = { filename:string; source_sha256:string; audio_sha256:string; duration_seconds:number; approved_at:string }
type AcxReport = {technical_preflight_passed:boolean; submission_eligible:boolean; submission_blocker:string; profile:{name:string;source:string}; tracks:{filename:string;issues:string[];technical_preflight_passed:boolean}[];disclaimer:string;manual_requirements:string[]}

type AudioProduction = {
  pronunciations: AudioRule[]
  chapter_profiles: Record<string, {voice:string; rate:number}>
  proof_notes: AudioProof[]
  chapter_casts?: Record<string, CastSpan[]>
  character_voices?: Record<string, {voice:string; rate:number}>
  proof_approvals?: Record<string, ProofApproval>
}
type Props = { apiBase: string; slug: string; disabled: boolean }

export default function AudiobookPanel({ apiBase, slug, disabled }: Props) {
  const endpoint = `${apiBase}/projects/${encodeURIComponent(slug)}/audiobook`
  const jobEndpoint = `${apiBase}/projects/${encodeURIComponent(slug)}/audiobook-jobs`
  const m4bEndpoint = `${apiBase}/projects/${encodeURIComponent(slug)}/m4b-jobs`
  const productionEndpoint = `${apiBase}/projects/${encodeURIComponent(slug)}/audiobook-production`
  const [chapters, setChapters] = useState<Chapter[]>([])
  const [voices, setVoices] = useState<string[]>([])
  const [renders, setRenders] = useState<Rendered[]>([])
  const [job, setJob] = useState<AudioJob | null>(null)
  const [voice, setVoice] = useState('')
  const [rate, setRate] = useState(-1)
  const [quality, setQuality] = useState<AudioQuality | null>(null)
  const [mastering, setMastering] = useState<AudioMastering | null>(null)
  const [masteringBusy, setMasteringBusy] = useState(false)
  const [m4b, setM4b] = useState<M4BJob | null>(null)
  const [encodeBusy, setEncodeBusy] = useState(false)
  const [showTracks, setShowTracks] = useState(false)
  const [showAudioChapters, setShowAudioChapters] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [selected, setSelected] = useState('')
  const [production, setProduction] = useState<AudioProduction | null>(null)
  const [termWritten, setTermWritten] = useState('')
  const [termSpoken, setTermSpoken] = useState('')
  const [profileVoice, setProfileVoice] = useState('')
  const [profileRate, setProfileRate] = useState(-1)
  const [noteSeconds, setNoteSeconds] = useState('0')
  const [proofText, setProofText] = useState('')
  const [notesShown, setNotesShown] = useState(12)
  const [castingText, setCastingText] = useState('')
  const [castSuggestions, setCastSuggestions] = useState<SuggestedCast[]>([])
  const [castUnassigned, setCastUnassigned] = useState(0)
  const [castingStart, setCastingStart] = useState(0)
  const [castingEnd, setCastingEnd] = useState(0)
  const [castingVoice, setCastingVoice] = useState('')
  const [castingCharacter, setCastingCharacter] = useState('')
  const [newCharacter, setNewCharacter] = useState('')
  const [newCharacterVoice, setNewCharacterVoice] = useState('')
  const [newCharacterRate, setNewCharacterRate] = useState(-1)
  const [listenedSeconds, setListenedSeconds] = useState('')
  const [confirmedComplete, setConfirmedComplete] = useState(false)
  const [confirmedAligned, setConfirmedAligned] = useState(false)
  const [retailer, setRetailer] = useState<AcxReport | null>(null)
  const [retailerBusy, setRetailerBusy] = useState(false)
  const [seek, setSeek] = useState<{path:string;seconds:number} | null>(null)
  const audioRefs = useRef<Record<string, HTMLAudioElement | null>>({})
  const castingRef = useRef<HTMLTextAreaElement | null>(null)
  useEffect(() => {
    let cancelled = false
    setCastingText(''); setCastingStart(0); setCastingEnd(0); setConfirmedComplete(false); setConfirmedAligned(false)
    setCastSuggestions([]); setCastUnassigned(0)
    if (!selected) return
    void getJson<{text:string}>('/casting-text?path=' + encodeURIComponent(selected))
      .then(result => {if (!cancelled) setCastingText(result.text)}).catch(() => {})
    return () => {cancelled = true}
  }, [selected, endpoint])
  useEffect(() => {
    const override = production?.chapter_profiles[selected]
    setProfileVoice(override?.voice || '')
    setProfileRate(override?.rate ?? -1)
  }, [selected, production])
  useEffect(() => {
    if (!showTracks || !seek) return
    const player = audioRefs.current[seek.path]
    if (!player) return
    player.currentTime = seek.seconds
    player.scrollIntoView({behavior:'smooth',block:'center'})
    setSeek(null)
  }, [showTracks, seek, renders])

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
      setQuality(null)
      setMastering(null)
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
    setChapters([]); setRenders([]); setVoices([]); setJob(null); setM4b(null); setMessage(''); setError(''); setQuality(null); setShowAudioChapters(false); setProduction(null); setNotesShown(12)
    void Promise.all([getJson<Chapter[]>('/chapters'), getJson<Rendered[]>('/renders'), getJson<VoiceResult>('/voices')])
      .then(([files, tracks, speech]) => {
        if (live) {
          setChapters(files); setRenders(tracks); setVoices(speech.voices)
          setSelected(files.find(ch => ch.narratable)?.path || '')
          setVoice(speech.voices[0] || '')
        }
      }).catch(e => { if (live) setError(String(e)) })
    void getJob().then(value => { if (live) setJob(value) }).catch(() => {})
    void fetch(m4bEndpoint).then(r => r.ok ? r.json() : null)
      .then(value => { if (live && value) setM4b(value as M4BJob) }).catch(() => {})
    void fetch(productionEndpoint).then(r => {
      if (!r.ok) throw new Error('Narration direction unavailable')
      return r.json() as Promise<AudioProduction>
    }).then(value => { if (live) setProduction(value) }).catch(e => { if (live) setError(String(e)) })
    const timer = window.setInterval(() => {
      void Promise.all([getJob(), getJson<Rendered[]>('/renders'), fetch(m4bEndpoint).then(r => r.ok ? r.json() : null)])
        .then(([nextJob, tracks, encoding]) => {
          if (live) { setJob(nextJob); setRenders(tracks); if (encoding) setM4b(encoding as M4BJob) }
        }).catch(() => {})
    }, 3000)
    return () => { live = false; window.clearInterval(timer) }
  }, [endpoint])

  async function editProduction(suffix: string, method: string, payload?: unknown) {
    if (job?.active || job?.status === 'queued' || job?.status === 'running') {
      setError('Finish or pause the current narration batch before changing its direction.')
      return
    }
    setBusy(true); setError(''); setMessage('')
    try {
      const response = await fetch(productionEndpoint + suffix, {
        method,
        headers: { 'Content-Type': 'application/json' },
        ...(payload === undefined ? {} : {body: JSON.stringify(payload)}),
      })
      if (!response.ok) {
        const detail = await response.json().catch(() => ({}))
        throw new Error(detail.detail || `Narration settings request failed: ${response.status}`)
      }
      setProduction(await fetch(productionEndpoint).then(r => r.json()) as AudioProduction)
      if (suffix === '/pronunciations' && method === 'PUT') {
        setTermWritten(''); setTermSpoken('')
      }
      setQuality(null)
      setMessage('Narration direction updated. Existing recordings may need to be re-rendered.')
    } catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }

  function jumpToNote(note: AudioProof) {
    const current = renders.find(track => track.source_path === note.path)
    if (!current || current.filename !== note.filename) {
      setError('The note refers to an earlier recording. Open the historical note, then listen to the current chapter separately.')
      return
    }
    setError('')
    setSelected(note.path)
    setSeek({path:note.path,seconds:note.seconds})
    setShowTracks(true)
  }

  async function suggestDialogue() {
    if (!selected) return
    setBusy(true); setError('')
    try {
      const response = await fetch(productionEndpoint + '/casting-suggestions?path=' + encodeURIComponent(selected))
      if (!response.ok) throw new Error('Could not identify explicit dialogue speakers')
      const result = await response.json() as {suggestions:SuggestedCast[];unassigned_or_ambiguous:number}
      setCastSuggestions(result.suggestions)
      setCastUnassigned(result.unassigned_or_ambiguous)
    } catch (e) {setError(String(e))}
    finally {setBusy(false)}
  }

  async function saveCharacterCast() {
    if (!selected || castingEnd <= castingStart || (!castingVoice && !castingCharacter)) {
      setError('Select a dialogue passage in the text and choose an installed character voice.')
      return
    }
    await editProduction('/casting', 'PUT', {
      path:selected, start:castingStart, end:castingEnd,
      text:castingText.slice(castingStart, castingEnd), voice:castingCharacter ? '' : castingVoice,
      character:castingCharacter,
    })
  }

  async function approveCompleteListen() {
    setBusy(true); setError(''); setMessage('')
    try {
      const response = await fetch(productionEndpoint + '/proof-approvals', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({
          path:selected, listened_seconds:Number(listenedSeconds),
          source_aligned:confirmedAligned, full_listen:confirmedComplete,
        }),
      })
      if (!response.ok) {
        const detail = await response.json().catch(() => ({}))
        throw new Error(detail.detail || 'Proof approval failed')
      }
      setProduction(await fetch(productionEndpoint).then(r => r.json()) as AudioProduction)
      setQuality(null); setMessage('Full-chapter proof approval saved for this exact recording and manuscript.')
    } catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }

  async function runRetailerPreflight() {
    setRetailerBusy(true); setError(''); setRetailer(null)
    try {
      const response = await fetch(jobEndpoint + '/retailer/acx-preflight', {method:'POST'})
      if (!response.ok) {
        const detail = await response.json().catch(() => ({}))
        throw new Error(detail.detail || 'ACX preflight failed')
      }
      setRetailer(await response.json() as AcxReport)
    } catch (e) { setError(String(e)) }
    finally { setRetailerBusy(false) }
  }

  async function saveProofNote() {
    setBusy(true); setError('')
    try {
      const response = await fetch(productionEndpoint + '/notes', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({path:selected,seconds:Number(noteSeconds),note:proofText}),
      })
      if (!response.ok) {
        const detail = await response.json().catch(() => ({}))
        throw new Error(detail.detail || `Proof note failed: ${response.status}`)
      }
      setProduction(await fetch(productionEndpoint).then(r => r.json()) as AudioProduction)
      setProofText(''); setQuality(null)
      setMessage('Timed proof-listening note recorded.')
    } catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }

  async function encodeM4B(action: 'start' | 'pause' | 'resume', mode: 'original' | 'leveled' = 'original') {
    setEncodeBusy(true); setError(''); setMessage('')
    try {
      const response = await fetch(m4bEndpoint + '/' + action, {
        method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify(action === 'start' ? {mode} : {}),
      })
      if (!response.ok) {
        const detail = await response.json().catch(() => ({}))
        throw new Error(detail.detail || `M4B encoding request failed: ${response.status}`)
      }
      const next = await response.json() as M4BJob
      setM4b(next)
      setMessage(next.message || 'M4B encoding updated.')
    } catch (e) { setError(String(e)) }
    finally { setEncodeBusy(false) }
  }

  async function measureLoudness() {
    setMasteringBusy(true); setError('')
    try {
      const response = await fetch(jobEndpoint + '/mastering', {method:'POST'})
      if (!response.ok) {
        const detail = await response.json().catch(() => ({}))
        throw new Error(detail.detail || `Loudness analysis failed: ${response.status}`)
      }
      setMastering(await response.json() as AudioMastering)
    } catch (e) { setError(String(e)) }
    finally { setMasteringBusy(false) }
  }

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
      <details className="audiobook-intro">
        <summary>About offline narration and current limitations</summary>
        <p>Generate narrated chapters using installed Windows voices without uploading manuscript text. Select explicit character dialogue spans and assign installed Windows voices. Automated speaker inference and professional acting remain unavailable; ACX is an advisory technical preflight, not retail approval.</p>
      </details>
      <AuthorProductionDesk endpoint={productionEndpoint} />
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
          <progress aria-label="Whole-book audiobook narration progress" max={Math.max(1, job.total ?? 1)} value={job.completed ?? 0} />
          <p>{job.message} {job.current ? `(Now narrating ${job.current})` : ''}</p>
          {!!job.chapters?.length && <details className="audiobook-chapter-ledger">
            <summary>Chapter narration ledger ({job.chapters.length})</summary>
            {job.chapters.slice(0, showAudioChapters ? undefined : 12).map((chapter, index) => <div key={chapter.path} className="audiobook-job-chapter"><small>{index + 1}. {chapter.title}</small><span>{chapter.status}</span></div>)}
            {!showAudioChapters && job.chapters.length > 12 && <button type="button" onClick={() => setShowAudioChapters(true)}>Show all {job.chapters.length} chapters</button>}
          </details>}
        </div>}
      </div>
      <details className="audiobook-direction">
        <summary>Advanced: pronunciation and chapter narrator direction ({production?.pronunciations.length || 0} terms)</summary>
        <p>Replace unusual names with natural spoken spellings in local TTS only. The manuscript is never edited. Review the result by listening.</p>
        <div className="audiobook-editor-row">
          <label>Written term<input value={termWritten} maxLength={90} placeholder="Aster Vale"
            onChange={e => setTermWritten(e.target.value)} /></label>
          <label>Speak as<input value={termSpoken} maxLength={140} placeholder="AS-ter VAYL"
            onChange={e => setTermSpoken(e.target.value)} /></label>
          <button disabled={disabled || busy || !!job?.active || !termWritten.trim() || !termSpoken.trim()}
            onClick={() => void editProduction('/pronunciations', 'PUT', {written:termWritten,spoken:termSpoken})}>
            Save pronunciation</button>
        </div>
        {!!production?.pronunciations.length && <div className="audiobook-rule-list">
          {production.pronunciations.slice(0, 35).map(rule => <div key={rule.written}>
            <span><strong>{rule.written}</strong> → {rule.spoken}</span>
            <button disabled={disabled || busy || !!job?.active} aria-label={'Delete pronunciation for '+rule.written}
              onClick={() => void editProduction('/pronunciations/' + encodeURIComponent(rule.written),'DELETE')}>Remove</button>
          </div>)}
          {production.pronunciations.length > 35 && <p>Showing first 35 terms; update existing terms by entering the same written spelling.</p>}
        </div>}
        <h4>Chapter narrator override</h4>
        <p>Choose a voice and pace for this entire chapter. Choose a narrator for the chapter; below you can explicitly cast dialogue by highlighting the exact passage in spoken-text preview.</p>
        <div className="audiobook-editor-row">
          <label>Chapter<select value={selected} onChange={e => {
            const next = e.target.value; setSelected(next)
            const profile = production?.chapter_profiles[next]
            setProfileVoice(profile?.voice || '')
            setProfileRate(profile?.rate ?? -1)
          }}>
            {chapters.map(ch => <option key={ch.path} value={ch.path}>{ch.path}</option>)}
          </select></label>
          <label>Voice<select value={profileVoice} onChange={e => setProfileVoice(e.target.value)}>
            <option value="">Use batch narrator</option>
            {voices.map(v => <option key={v} value={v}>{v}</option>)}
          </select></label>
          <label>Pace<select value={profileRate} onChange={e => setProfileRate(Number(e.target.value))}>
            {Array.from({length:11},(_,i)=>i-5).map(n => <option key={n} value={n}>{n}</option>)}
          </select></label>
          <button disabled={disabled || busy || !selected || !!job?.active}
            onClick={() => void editProduction('/profiles', 'PUT', {path:selected,voice:profileVoice,rate:profileRate})}>Save chapter override</button>
          {!!production?.chapter_profiles[selected] && <button disabled={disabled || busy || !!job?.active}
            onClick={() => void editProduction('/profiles?path='+encodeURIComponent(selected),'DELETE')}>Remove override</button>}
        </div>
        <p>{Object.keys(production?.chapter_profiles || {}).length} chapter overrides saved. Changing these settings after a batch is complete requires new narration for a current edition.</p>
        <h4>Reusable character voice library</h4>
        <p>Save a character identity once, with an optional Windows voice and pace. Characters can be neural-only; add their Fish voice reference in Neural Voice Studio below before casting their dialogue. A neural-only cast cannot be rendered with the Windows SAPI engine. Updating identities also recasts previously tagged passages and requires a new narration batch.</p>
        <div className="audiobook-editor-row">
          <label>Character name<input maxLength={100} value={newCharacter} onChange={e=>setNewCharacter(e.target.value)} placeholder="Mira" /></label>
          <label>Optional Windows character voice<select value={newCharacterVoice} onChange={e=>setNewCharacterVoice(e.target.value)}>
            <option value="">Neural only — no Windows voice</option>
            {voices.map(v=><option key={v} value={v}>{v}</option>)}
          </select></label>
          <label>Character pace<select value={newCharacterRate} onChange={e=>setNewCharacterRate(Number(e.target.value))}>
            {Array.from({length:11},(_,i)=>i-5).map(n=><option key={n} value={n}>{n}</option>)}
          </select></label>
          <button disabled={disabled || busy || !!job?.active || !newCharacter.trim()} onClick={()=>void editProduction('/characters','PUT',{character:newCharacter,voice:newCharacterVoice,rate:newCharacterRate})}>Save character identity</button>
        </div>
        {Object.entries(production?.character_voices || {}).map(([character, preset])=><div className="audiobook-editor-row" key={character}>
          <span><strong>{character}</strong> · {preset.voice} · pace {preset.rate}</span>
          <button type="button" disabled={disabled || busy || !!job?.active} onClick={()=>{setNewCharacter(character);setNewCharacterVoice(preset.voice);setNewCharacterRate(preset.rate)}}>Edit voice</button>
          <button type="button" disabled={disabled || busy || !!job?.active} onClick={()=>void editProduction('/characters?character='+encodeURIComponent(character),'DELETE')}>Remove</button>
        </div>)}
        <h4>Character dialogue casting within the chapter</h4>
        <p>Highlight a dialogue span in the read-only spoken text, then choose a saved character or one-off installed voice. Named character voice and pace persist across chapters, but dialogue must still be assigned manually in each chapter. Unselected text uses the narrator. The manuscript is never edited.</p>
        <label htmlFor="casting-preview">Spoken chapter preview (select text to cast)</label>
        <textarea id="casting-preview" ref={castingRef} readOnly rows={6} value={castingText}
          onSelect={event => {setCastingStart(event.currentTarget.selectionStart);setCastingEnd(event.currentTarget.selectionEnd)}} />
        <p>Selected characters: {castingStart}–{castingEnd}. {castingEnd > castingStart ? castingText.slice(castingStart, Math.min(castingEnd, castingStart+120)) : 'Highlight dialogue above.'}</p>
        <div className="audiobook-editor-row">
          <label>Saved character<select value={castingCharacter} onChange={event => setCastingCharacter(event.target.value)}>
            <option value="">None · choose an individual voice</option>
            {Object.keys(production?.character_voices || {}).map(name=><option key={name} value={name}>{name}</option>)}
          </select></label>
          <label>Individual voice<select value={castingVoice} disabled={!!castingCharacter} onChange={event => setCastingVoice(event.target.value)}>
            <option value="">Choose a voice</option>
            {voices.map(v => <option key={v} value={v}>{v}</option>)}
          </select></label>
          <button disabled={disabled || busy || !selected || (!castingVoice && !castingCharacter) || castingEnd <= castingStart || !!job?.active}
            onClick={() => void saveCharacterCast()}>Cast selected dialogue</button>
          <button disabled={disabled || busy || !(production?.chapter_casts?.[selected]?.length) || !!job?.active}
            onClick={() => void editProduction('/casting?path='+encodeURIComponent(selected), 'DELETE')}>Clear chapter casting</button>
        </div>
        <div className="audiobook-rule-list">
          {(production?.chapter_casts?.[selected] || []).map((span, index) => <p key={span.start+':'+index}>
            <strong>{span.character || span.voice}</strong> · {span.voice}{span.rate !== undefined ? ' · pace '+span.rate : ''} · {span.start}–{span.end} · {span.text.slice(0,120)}
          </p>)}
        </div>
        <h4>Review explicit speaker suggestions</h4>
        <p>Find dialogue with directly stated speaker tags, such as “Mira said” or “said Mira.” These are suggestions only; ambiguous lines are never assigned automatically.</p>
        <button type="button" disabled={disabled || busy || !selected || !!job?.active} onClick={()=>void suggestDialogue()}>Find speaker suggestions in this chapter</button>
        {castSuggestions.length > 0 && <div className="audiobook-rule-list">
          {castSuggestions.filter(item=>!(production?.chapter_casts?.[selected] || []).some(span=>span.start < item.end && item.start < span.end)).slice(0,30).map(item=><div key={item.start} className="audiobook-editor-row">
            <span><strong>{item.character}</strong>: {item.text.slice(0,140)}</span>
            <button type="button" disabled={disabled || busy || !!job?.active} onClick={()=>void editProduction('/casting','PUT',{
              path:item.path,start:item.start,end:item.end,text:item.text,voice:'',character:item.character,
            })}>Approve casting</button>
          </div>)}
          {castSuggestions.length > 30 && <p>Showing up to 30 suggested lines. Review the rest in the manuscript.</p>}
        </div>}
        {(castSuggestions.length > 0 || castUnassigned > 0) && <p role="status">{castSuggestions.length} explicit attributions suggested · {castUnassigned} quotations ambiguous or not attributed.</p>}
      </details>
      <LocalKokoroPanel endpoint={productionEndpoint} selected={selected}
        selectionStart={castingStart} selectionEnd={castingEnd}
        characters={Object.keys(production?.character_voices || {})}
        disabled={disabled || busy || !!job?.active} />
      <NeuralVoicePanel productionEndpoint={productionEndpoint} selected={selected}
        casts={production?.chapter_casts?.[selected] || []}
        characters={Object.keys(production?.character_voices || {})}
        disabled={disabled || busy || !!job?.active} />
      <details className="audiobook-direction">
        <summary>Proof listening & correction notes ({production?.proof_notes.filter(n=>n.status==='open').length || 0} open)</summary>
        <p>Play a chapter below, record the approximate time and what the narrator should correct. Open notes prevent the audiobook from passing technical readiness until resolved.</p>
        <div className="audiobook-editor-row">
          <label>Chapter<select value={selected} onChange={e => setSelected(e.target.value)}>
            {chapters.map(ch => <option key={ch.path} value={ch.path}>{ch.path}</option>)}
          </select></label>
          <label>Time (seconds)<input type="number" min="0" max="200000" step=".5" value={noteSeconds}
            onChange={e => setNoteSeconds(e.target.value)} /></label>
          <label>Issue or correction<input maxLength={1000} value={proofText} placeholder="Check pronunciation at this point"
            onChange={e => setProofText(e.target.value)} /></label>
          <button disabled={disabled || busy || !selected || proofText.trim().length < 4}
            onClick={() => void saveProofNote()}>Add proof note</button>
        </div>
        <div className="audiobook-rule-list">
          {(production?.proof_notes || []).slice(-notesShown).reverse().map(note => <div key={note.id}>
            <span><strong>{note.path}</strong> · {note.seconds}s · {note.status}<small>{note.note}</small></span>
            <button disabled={disabled || busy} onClick={() => jumpToNote(note)}>Jump to audio</button>
            <button disabled={disabled || busy}
              onClick={() => void editProduction('/notes/'+note.id,'POST',{resolved:note.status !== 'resolved'})}>
              {note.status === 'resolved' ? 'Reopen' : 'Resolve'}</button>
          </div>)}
          {(production?.proof_notes.length || 0) > notesShown &&
            <button onClick={() => setNotesShown(value=>value+12)}>Show older proof notes</button>}
        </div>
        <h4>Approve the entire recording after proof-listening</h4>
        <p>Listen to the full chapter and compare the narration against the source manuscript. This approval is an author attestation, not automated transcript alignment. Any change to the source or recording invalidates it.</p>
        <p>Current take: {renders.find(track => track.source_path === selected)?.filename || 'None'} ·
          {production?.proof_approvals?.[selected]?.filename === renders.find(track => track.source_path === selected)?.filename
            ? ' prior approval recorded (recheck readiness for source/audio changes)' : ' not approved'}</p>
        <div className="audiobook-editor-row">
          <label>Seconds listened<input type="number" min="0" step=".5" value={listenedSeconds}
            placeholder={String(quality?.tracks.find(track => track.path === selected)?.seconds ?? '')}
            onChange={event=>setListenedSeconds(event.target.value)} /></label>
          <label><input type="checkbox" checked={confirmedComplete} onChange={event=>setConfirmedComplete(event.target.checked)} /> I listened to the entire recording</label>
          <label><input type="checkbox" checked={confirmedAligned} onChange={event=>setConfirmedAligned(event.target.checked)} /> I compared narration with the chapter source and found it aligned</label>
          <button disabled={disabled || busy || !selected || !confirmedComplete || !confirmedAligned || !Number(listenedSeconds)}
            onClick={() => void approveCompleteListen()}>Approve exact chapter recording</button>
          {!!production?.proof_approvals?.[selected] && <button disabled={disabled || busy}
            onClick={() => void editProduction('/proof-approvals?path='+encodeURIComponent(selected), 'DELETE')}>Revoke approval</button>}
        </div>
      </details>
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
        {quality.ready && quality.m4b_available && job?.status === "completed" && <button className="audiobook-m4b-download"
          disabled={busy || encodeBusy || !!m4b?.active || m4b?.status === 'queued'}
          onClick={() => void encodeM4B('start', 'original')}>Queue chapter-marked M4B (offline AAC)</button>}
        {m4b?.exists && <section className="audiobook-encode-status" aria-live="polite">
          <strong>M4B encoding: {m4b.status} {m4b.mode === 'leveled' ? '(leveled)' : '(original)'}</strong>
          <p>{m4b.message}</p>
          <div className="audiobook-job-buttons">
            {m4b.status === 'queued' && <button disabled={encodeBusy || busy} onClick={() => void encodeM4B('pause')}>Pause queued encode</button>}
            {['paused','interrupted','needs_attention'].includes(m4b.status) && <button disabled={encodeBusy || busy || !!m4b.active}
              onClick={() => void encodeM4B('resume')}>Retry M4B encoding</button>}
            {m4b.downloadable && <a href={m4bEndpoint + '/download'} download>Download completed M4B</a>}
          </div>
          <small>Saved job status; an interrupted encode restarts from verified chapter audio.</small>
        </section>}
        {!quality.m4b_available && <p>Install FFmpeg and FFprobe locally to enable a single chapter-marked M4B.</p>}
        {quality.issues.length > 0 && <div className="audiobook-quality-warnings">{quality.issues.slice(0, 35).map((issue, i) =>
          <p key={i}><strong>{issue.path || 'Whole book'}:</strong> {issue.detail}</p>)}</div>}
        {quality.issues.length > 35 && <p>Additional issues not shown. Recheck after addressing the first 35.</p>}
        <p>{quality.disclaimer}</p>
      </section>}
      {quality?.ready && quality.m4b_available && <details className="audiobook-direction">
        <summary>Advanced: loudness, true peak and optional M4B leveling</summary>
        <p>Measure integrated LUFS, true peak, residual quiet-window noise and dynamic range locally with FFmpeg. Results are engineering observations, not retailer certification.</p>
        <button type="button" disabled={disabled || busy || retailerBusy} onClick={() => void runRetailerPreflight()}>
          {retailerBusy ? 'Checking ACX audio…' : 'Run ACX/Audible technical preflight'}
        </button>
        {retailer && <section className="audiobook-mastering" aria-live="polite">
          <strong>ACX technical preflight: {retailer.technical_preflight_passed ? 'Measured checks passed' : 'Action needed / unverified'}</strong>
          <p role="alert"><strong>Retailer submission blocked:</strong> {retailer.submission_blocker}</p>
          <p>{retailer.disclaimer}</p>
          <details><summary>Retailer track observations ({retailer.tracks.length})</summary>
            {retailer.tracks.map((track,index)=><p key={index}>{track.filename}: {track.technical_preflight_passed ? 'measured checks passed' : track.issues.join(', ')}</p>)}
          </details>
          <details><summary>Human submission checklist</summary>
            {retailer.manual_requirements.map((requirement,index)=><p key={index}>{requirement}</p>)}
          </details>
        </section>}
        <button type="button" disabled={disabled || busy || masteringBusy} onClick={() => void measureLoudness()}>
          {masteringBusy ? 'Measuring local audio…' : 'Analyze audiobook loudness'}
        </button>
        {mastering && <section className="audiobook-mastering" aria-live="polite">
          <strong>Listening target: {mastering.target_lufs} LUFS / {mastering.true_peak_target_dbtp} dBTP</strong>
          <p>{mastering.disclaimer}</p>
          {!!mastering.warnings.length && <p>{mastering.warnings.length} potential loudness or peak concerns. Inspect chapters below before distributing.</p>}
          <details><summary>Measured chapters ({mastering.tracks.length})</summary>
            <div className="audiobook-mastering-tracks">{mastering.tracks.slice(0,120).map(track => <p key={track.path}>
              <strong>{track.title}</strong> · {track.integrated_lufs ?? 'Unknown'} LUFS · {track.true_peak_dbtp ?? 'Unknown'} dBTP · RMS {track.rms_dbfs ?? 'Unknown'} dBFS · LRA {track.loudness_range_lu ?? 'Unknown'} · longest quiet {track.longest_quiet_seconds ?? 0}s</p>)}</div>
          </details>
          <button className="audiobook-m4b-download" disabled={encodeBusy || busy || !!m4b?.active || m4b?.status === 'queued'}
            onClick={() => void encodeM4B('start','leveled')}>
            Queue optional leveled chapter-marked M4B
          </button>
          <p>Leveling creates a separate AAC file. Existing narration and unmodified M4B stay untouched.</p>
        </section>}
      </details>}
      {renders.length > 0 && <details className="audiobook-tracks" open={showTracks} onToggle={e => setShowTracks(e.currentTarget.open)}>
        <summary>Narrated chapter playback and downloads ({renders.length})</summary>
        {renders.map(track => <div className="audiobook-track" key={track.source_path}>
          <div><strong>{track.source_path}</strong><small>{track.voice} · {(track.bytes / 1024 / 1024).toFixed(1)} MB</small></div>
          <audio ref={element => { audioRefs.current[track.source_path] = element }} controls preload="none" src={endpoint + '/files/' + encodeURIComponent(track.filename)} aria-label={track.source_path} />
          <a href={endpoint + '/files/' + encodeURIComponent(track.filename)} download>Download</a>
        </div>)}
      </details>}
      <p className="audiobook-note">Each track stays inside this project. MP3 is produced when FFmpeg is installed; otherwise EmberWriter delivers WAV. The exported ZIP contains chapter audio and a manifest, not a mastered M4B retail audiobook.</p>
    </div>
  </section>
}
