import { useEffect, useState } from 'react'

type Cue = {
  start: number
  end: number
  kind: 'dialogue' | 'narration'
  text: string
  speaker: string | null
  attribution?: string
  performance?: { emotion: string; delivery: string; energy?: number; confidence: string }
}
type Performance = {
  source_sha256: string
  spans: Cue[]
  unresolved_count: number
  render_ready: boolean
  warnings: string[]
}
type SpeakerLibrary = {
  kokoro_voices?: Record<string, unknown>
  neural_voices?: Record<string, unknown>
  character_voices?: Record<string, unknown>
  kitten_voices?: Record<string, unknown>
}
type Props = { apiBase: string; slug: string; path: string; disabled: boolean }

export default function AudioDirectorPanel({ apiBase, slug, path, disabled }: Props) {
  const endpoint = `${apiBase}/projects/${encodeURIComponent(slug)}/audiobook-production`
  const [script, setScript] = useState<Performance | null>(null)
  const [names, setNames] = useState<string[]>([])
  const [edit, setEdit] = useState<Record<number, {emotion: string; delivery: string; energy: number}>>({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [showAll, setShowAll] = useState(false)
  const [fishTakes, setFishTakes] = useState<Record<number, string>>({})
  const [fishSpeakers, setFishSpeakers] = useState<string[]>([])
  const [kokoroSpeakers, setKokoroSpeakers] = useState<string[]>([])
  const [kokoroTakes, setKokoroTakes] = useState<Record<number, string>>({})
  const [kittenTakes, setKittenTakes] = useState<Record<number, string>>({})
  const [kittenInstalled, setKittenInstalled] = useState(false)
  const [kittenVoiceIds, setKittenVoiceIds] = useState<string[]>([])
  const [kittenProfiles, setKittenProfiles] = useState<Record<string, {voice_id: string}>>({})
  const [kittenSelected, setKittenSelected] = useState<Record<string, string>>({})
  const [kittenLoading, setKittenLoading] = useState(false)
  const [capabilities, setCapabilities] = useState<{expressions: string[]; pitch_processing: string; native_emotion_conditioning: boolean} | null>(null)

  useEffect(() => {
    let alive = true
    setScript(null); setError(''); setEdit({}); setShowAll(false); setFishTakes({}); setFishSpeakers([]); setKokoroTakes({}); setKokoroSpeakers([]); setKittenTakes({}); setKittenProfiles({}); setKittenVoiceIds([])
    if (!path) return
    void Promise.all([
      fetch(endpoint + '/performance?path=' + encodeURIComponent(path)),
      fetch(endpoint),
      fetch(endpoint + '/kokoro/expression-capabilities'),
      fetch(endpoint + '/kitten/status'),
      fetch(endpoint + '/kitten/profiles'),
    ]).then(async ([performance, library, expressive, kittenStatus, kittenProfilesResponse]) => {
      if (!performance.ok || !library.ok) throw new Error('Could not open the audiobook performance manuscript.')
      return [await performance.json() as Performance, await library.json() as SpeakerLibrary,
        expressive.ok ? await expressive.json() as {expressions: string[]; pitch_processing: string; native_emotion_conditioning: boolean} : null,
        kittenStatus.ok ? await kittenStatus.json() as {installed: boolean} : {installed: false},
        kittenProfilesResponse.ok ? await kittenProfilesResponse.json() as Record<string, {voice_id: string}> : {}] as const
    }).then(([performance, library, expressive, kittenStatus, kittenProfilesResponse]) => {
      if (!alive) return
      setScript(performance)
      setCapabilities(expressive)
      setKittenInstalled(kittenStatus.installed)
      setKittenProfiles(kittenProfilesResponse)
      setKokoroSpeakers(Object.keys(library.kokoro_voices || {}))
      setFishSpeakers(Object.keys(library.neural_voices || {}))
      setNames(Array.from(new Set(['Narrator', ...Object.keys(library.character_voices || {}),
        ...Object.keys(library.kokoro_voices || {}), ...Object.keys(library.neural_voices || {}),
        ...Object.keys(kittenProfilesResponse || {})])).sort())
    }).catch(e => { if (alive) setError(String(e)) })
    return () => { alive = false }
  }, [endpoint, path])

  async function save(suffix: string, payload: object) {
    setBusy(true); setError(''); setMessage('')
    try {
      const response = await fetch(endpoint + suffix, {
        method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({path, ...payload}),
      })
      if (!response.ok) {
        const detail = await response.json().catch(() => ({}))
        throw new Error(detail.detail || 'Performance direction could not be saved.')
      }
      const changed = await response.json() as Performance
      setScript(changed)
      setMessage('Saved to the audiobook-only performance manuscript. The novel was not changed.')
    } catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }

  async function fishPreview(start: number) {
    setBusy(true); setError(''); setMessage('')
    try {
      const response = await fetch(endpoint + '/neural-takes', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({path,start,port:8080}),
      })
      if (!response.ok) {
        const detail = await response.json().catch(() => ({}))
        throw new Error(detail.detail || 'Fish rehearsal server unavailable.')
      }
      const take = await response.json() as {filename:string}
      setFishTakes(prev => ({...prev,[start]: endpoint + '/neural-takes/' + encodeURIComponent(take.filename)}))
      setMessage('Fish rehearsal recorded. This is a proof take, not approved book audio.')
    } catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }

  async function kokoroPreview(start: number, end: number) {
    setBusy(true); setError(''); setMessage('')
    try {
      const response = await fetch(endpoint + '/kokoro/rehearsals', {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({path, start, end}),
      })
      if (!response.ok) {
        const detail = await response.json().catch(() => ({}))
        throw new Error(detail.detail || 'CPU rehearsal unavailable. Install Kokoro and assign a local voice.')
      }
      const take = await response.json() as { filename: string }
      setKokoroTakes(prev => ({...prev, [start]: endpoint + '/kokoro/rehearsals/' + encodeURIComponent(take.filename)}))
      setMessage('CPU expression rehearsal recorded. Listen alongside any Fish take. Neither is approved book audio.')
    } catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }

  async function discoverKittenVoices() {
    setKittenLoading(true); setError('')
    try {
      const response = await fetch(endpoint + '/kitten/voices')
      if (!response.ok) {
        const detail = await response.json().catch(() => ({}))
        throw new Error(detail.detail || 'Local Kitten model is not ready')
      }
      const result = await response.json() as { voices: string[] }
      setKittenVoiceIds(result.voices)
      setMessage(`Loaded ${result.voices.length} built-in Kitten voice choices. Choose one per character.`)
    } catch (error) { setError(String(error)) }
    finally { setKittenLoading(false) }
  }

  async function assignKittenVoice(character: string, voice: string) {
    setBusy(true); setError('')
    try {
      const response = await fetch(endpoint + '/kitten/profiles', {
        method: 'PUT', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({character, voice_id: voice}),
      })
      if (!response.ok) {
        const detail = await response.json().catch(() => ({}))
        throw new Error(detail.detail || 'Could not save Kitten voice')
      }
      setKittenProfiles(prev => ({...prev,[character]:{voice_id:voice}}))
      setMessage(`Saved Kitten voice for ${character}. This only changes the audiobook performance cast.`)
    } catch (error) { setError(String(error)) }
    finally { setBusy(false) }
  }

  async function kittenPreview(start: number) {
    setBusy(true); setError(''); setMessage('')
    try {
      const response = await fetch(endpoint + '/kitten/rehearsals', {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({path, start}),
      })
      if (!response.ok) {
        const detail = await response.json().catch(() => ({}))
        throw new Error(detail.detail || 'Kitten CPU expression rehearsal unavailable')
      }
      const result = await response.json() as {filename:string}
      setKittenTakes(prev => ({ ...prev,[start]:endpoint + '/kitten/rehearsals/' + encodeURIComponent(result.filename) }))
      setMessage('Kitten native-emotion CPU take generated. Listen and compare; this is not approved book audio.')
    } catch (error) { setError(String(error)) }
    finally { setBusy(false) }
  }

  const dialogue = (script?.spans || []).filter(row => row.kind === 'dialogue')
  const shown = showAll ? (script?.spans || []).filter(row => row.text.trim()) : dialogue.filter(row => !row.speaker)
  return <details id="audio-director-tool" className="audiobook-direction" data-testid="audio-director">
    <summary>Audio Director · {script ? `${dialogue.length} spoken lines · ${script.unresolved_count} need review` : 'performance manuscript'}</summary>
    <p>The performance manuscript is a separate, lossless version of this chapter for narration. Every quotation gets its own voice and delivery direction. Unresolved voices block neural book production rather than defaulting to the narrator.</p>
    <p><small>Direct the performance, then audition it. CPU Kokoro now applies subtle emotion-specific timing, pitch, volume and breath-space presets; this is DSP-based prosody, not Fish-style neural acting. Fish Speech offers model-conditioned expressive tags when its separate GPU server is installed. Every take remains a draft until you listen and approve.</small></p>
    {capabilities && <p><small>Local expression: {capabilities.pitch_processing === 'rubberband' ? 'Pitch and dynamics available with FFmpeg Rubber Band' : 'Pitch unavailable — install FFmpeg with the Rubber Band filter for expressive cues'} · Native emotional acting: {capabilities.native_emotion_conditioning ? 'yes' : 'no, acoustic approximation'}.</small></p>}
    {!path && <p>Select a manuscript chapter first.</p>}
    {error && <p role="alert" className="audiobook-alert">{error}</p>}
    {message && <p role="status" className="audiobook-success">{message}</p>}
    <details className="audiobook-direction" style={{margin:'12px 0'}}>
      <summary>✦ Native emotion on CPU · KittenTTS 2 (optional)</summary>
      <p>Unlike the Kokoro acoustic presets, KittenTTS 2 understands ten native emotion tags and supports an expressive decoding mode. Model weights use the <b>Stellon Labs Community License</b>, with commercial restrictions. They are never downloaded automatically.</p>
      <p><a href="https://huggingface.co/KittenML/kitten-tts-2/blob/main/LICENSE.md" target="_blank" rel="noreferrer">Review model licensing</a> · <a href="https://github.com/KittenML/KittenTTS" target="_blank" rel="noreferrer">Official installation and local CPU instructions</a></p>
      <p>Local status: <strong>{kittenInstalled ? 'Configured; optional model ready to load' : 'Not configured'}</strong>. Install the optional Python package and downloaded model folder yourself, then set EMBERWRITER_KITTEN_MODEL_DIR to that local folder before launching EmberWriter. CPU inference with Python may be slower than real-time.</p>
      <button type="button" disabled={!kittenInstalled || kittenLoading || busy} onClick={() => void discoverKittenVoices()}>
        {kittenLoading ? 'Loading local voice library…' : 'Load available CPU expressive voices'}
      </button>
      {kittenVoiceIds.length > 0 && <div style={{display:'grid',gap:10,marginTop:12}}>
        {names.map(name => <div className="audiobook-editor-row" key={name}>
          <label>{name} · Kitten voice
            <select value={kittenSelected[name] || kittenProfiles[name]?.voice_id || ''}
              onChange={e => setKittenSelected(prev => ({...prev,[name]:e.target.value}))}>
              <option value="">Choose a voice</option>
              {kittenVoiceIds.map(voice => <option value={voice} key={voice}>{voice}</option>)}
            </select>
          </label>
          <button type="button" disabled={busy || !((kittenSelected[name] || kittenProfiles[name]?.voice_id))}
            onClick={() => void assignKittenVoice(name, kittenSelected[name] || kittenProfiles[name].voice_id)}>
            Save casting
          </button>
        </div>)}
      </div>}
      <p><small>Kitten's emotion cues are model-conditioned but still experimental. If the same character uses Kokoro or Fish elsewhere, assign those voice identities separately.</small></p>
    </details>
    {script && <>
      <p><strong>{script.render_ready ? 'Speaker preflight passed' : 'Speaker preflight blocked'}</strong> · {script.unresolved_count} unattributed dialogue lines.</p>
      <button type="button" onClick={() => setShowAll(v => !v)}>{showAll ? 'Show only unassigned dialogue' : 'Direct all voices, narration and emotion'}</button>
      {shown.length === 0 && <p>Every identified quotation has a voice assignment. Review the emotional delivery before rendering.</p>}
      {shown.map(row => {
        const current = edit[row.start] || {emotion: row.performance?.emotion || 'neutral',
                                          delivery: row.performance?.delivery || 'natural', energy: row.performance?.energy || 3}
        return <div key={row.start} className="audiobook-job-chapter" style={{display:'block',margin:'0.7rem 0',padding:'0.7rem'}}>
          <blockquote style={{whiteSpace:'pre-wrap',margin:'0 0 0.5rem'}}>{row.text}</blockquote>
          <small>{row.kind === 'narration' ? 'Narration' : 'Dialogue'} · Characters {row.start}–{row.end} · {row.attribution || (row.kind === 'narration' ? 'narrator' : 'unresolved')}</small>
          <div className="audiobook-editor-row">
            {row.kind === 'narration' ? <span><strong>Narrator</strong> · Set a scene-wide delivery below</span> :
            <label>Speaking character
              <select aria-label={`Speaker for line ${row.start}`} value={row.speaker || ''} disabled={disabled || busy}
                onChange={e => void save('/performance/speaker', {start:row.start, end:row.end, speaker:e.target.value})}>
                <option value="">Unassigned — requires review</option>
                {names.filter(name => name !== 'Narrator').map(name => <option key={name} value={name}>{name}</option>)}
              </select>
            </label>}
            <label>Emotion
              <select value={current.emotion} disabled={disabled || busy}
                onChange={e => setEdit(p => ({...p,[row.start]:{...current,emotion:e.target.value}}))}>
                {(capabilities?.expressions || ['neutral','joy','excitement','sadness','grief','anger','fear','urgency','relief','determination','uncertainty','tenderness','sarcasm','surprise','awe','exhaustion','soft']).map(v => <option key={v} value={v}>{v}</option>)}
              </select>
            </label>
            <label>Performance intensity (1 = restrained, 5 = strong)
              <input type="range" min="1" max="5" step="1" value={current.energy}
                disabled={disabled || busy} aria-label={`Energy for line ${row.start}`}
                onChange={e => setEdit(p => ({...p,[row.start]:{...current,energy:Number(e.target.value)}}))} />
              <span>{current.energy} / 5</span>
            </label>
            <label>Delivery cue
              <input aria-label={`Delivery for line ${row.start}`} maxLength={140} value={current.delivery}
                disabled={disabled || busy}
                onChange={e => setEdit(p => ({...p,[row.start]:{...current,delivery:e.target.value}}))} />
            </label>
            <button type="button" disabled={disabled || busy || !row.speaker || !current.delivery.trim()}
              onClick={() => void save('/performance/direction', {start:row.start,end:row.end,...current})}>
              Save delivery
            </button>
            {row.speaker && kokoroSpeakers.includes(row.speaker) && <button type="button"
              disabled={disabled || busy || row.end - row.start > 1200 ||
                current.emotion !== (row.performance?.emotion || 'neutral') ||
                current.delivery !== (row.performance?.delivery || 'natural') ||
                current.energy !== (row.performance?.energy || 3)}
              title="Save delivery first, then listen to the CPU take with the chosen expression."
              onClick={() => void kokoroPreview(row.start, row.end)}>▶ Hear CPU expression</button>}
            {row.kind === 'dialogue' && kittenInstalled && row.speaker && kittenProfiles[row.speaker] && <button type="button"
              disabled={disabled || busy || row.end - row.start > 1200 ||
                current.emotion !== (row.performance?.emotion || 'neutral') ||
                current.delivery !== (row.performance?.delivery || 'natural') ||
                current.energy !== (row.performance?.energy || 3)}
              title="Save your delivery cue before requesting native-emotion speech."
              onClick={() => void kittenPreview(row.start)}>▶ Hear native CPU emotion</button>}
            {row.kind === 'dialogue' && row.speaker && fishSpeakers.includes(row.speaker) && <button type="button" disabled={disabled || busy}
              onClick={() => void fishPreview(row.start)}>▶ Compare Fish take (GPU)</button>}
          </div>
          {kokoroTakes[row.start] && <div><small>CPU Kokoro take · unapproved</small><audio controls src={kokoroTakes[row.start]} aria-label={`Kokoro expressive rehearsal for line ${row.start}`} /></div>}
          {kittenTakes[row.start] && <div><small>Kitten native CPU emotion · unapproved</small><audio controls src={kittenTakes[row.start]} aria-label={`Kitten CPU emotion rehearsal for line ${row.start}`} /></div>}
          {fishTakes[row.start] && <div><small>Fish take · unapproved</small><audio controls src={fishTakes[row.start]} aria-label={`Fish performance rehearsal for line ${row.start}`} /></div>}
        </div>
      })}
    </>}
  </details>
}
