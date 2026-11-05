import { useEffect, useState } from 'react'

type Engine = { installed: boolean; voice_ids: string[]; offline_only: boolean }
type Profile = { voice_id: string; speed: number }
type Take = { filename: string; seconds: number; segments: {speaker: string; voice_id: string}[]; status: string }

type Props = {
  endpoint: string
  selected: string
  selectionStart: number
  selectionEnd: number
  characters: string[]
  disabled: boolean
}
export default function LocalKokoroPanel({
  endpoint, selected, selectionStart, selectionEnd, characters, disabled,
}: Props) {
  const [engine, setEngine] = useState<Engine | null>(null)
  const [profiles, setProfiles] = useState<Record<string, Profile>>({})
  const [speaker, setSpeaker] = useState('Narrator')
  const [voice, setVoice] = useState('')
  const [speed, setSpeed] = useState(1.0)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [take, setTake] = useState<Take | null>(null)
  const available = ['Narrator', ...characters.filter(name => name !== 'Narrator')]
  async function request(path: string, init?: RequestInit) {
    const response = await fetch(endpoint + path, init)
    if (!response.ok) {
      const info = await response.json().catch(() => ({}))
      throw new Error(info.detail || 'Local rehearsal request failed')
    }
    return response.json()
  }
  useEffect(() => {
    let live = true
    Promise.all([request('/kokoro/status'), request('/kokoro/voices')])
      .then(([a,b]) => { if (live) { setEngine(a as Engine); setProfiles(b as Record<string,Profile>) } })
      .catch(e => { if (live) setError(String(e)) })
    return () => { live = false }
    // This is read-only bootstrap. Work begins only when the author clicks.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [endpoint])
  async function save() {
    setBusy(true); setError(''); setMessage('')
    try {
      await request('/kokoro/voices', { method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ character: speaker, voice_id: voice, speed }) })
      setProfiles(await request('/kokoro/voices') as Record<string,Profile>)
      setMessage('Saved voice identity. This setting is reused when you rehearse this character later.')
    } catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }
  async function rehearse() {
    setBusy(true); setError(''); setMessage(''); setTake(null)
    try {
      const result = await request('/kokoro/rehearsals', { method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path:selected, start:selectionStart, end:selectionEnd }),
      }) as Take
      setTake(result)
      setMessage('This is a rehearsal, not an approved audiobook chapter. Listen and decide what to change.')
    } catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }
  return <details className="audiobook-direction kokoro-local-studio">
    <summary>Local Voice Lab · Rehearse a scene with real neural voices</summary>
    <p>Kokoro ONNX runs entirely on your computer, including CPU-only machines. No manuscript is uploaded. You choose every voice and which passage to rehearse; EmberWriter will not overwrite the manuscript or approved recordings.</p>
    {error && <p className="audiobook-alert" role="alert">{error}</p>}
    {message && <p className="audiobook-success" role="status">{message}</p>}
    <p role="status"><strong>Offline model:</strong> {engine ? engine.installed
      ? 'Installed and available · '+engine.voice_ids.length+' voice styles'
      : 'Not yet installed · local model files required' : 'Checking local model files…'}</p>
    {engine?.installed && <>
      <h4>1. Cast your characters</h4>
      <p>Start with a narrator, then save a style for each speaker in your scene. A saved voice ID and speed persist across chapters. This is not voice cloning; these are built-in licensed voice styles.</p>
      <div className="audiobook-editor-row">
        <label>Role<select value={speaker} onChange={e=>{
          const name=e.target.value;setSpeaker(name)
          setVoice(profiles[name]?.voice_id || '');setSpeed(profiles[name]?.speed ?? 1)
        }}>{available.map(name=><option value={name} key={name}>{name}</option>)}</select></label>
        <label>Kokoro voice<select value={voice} onChange={e=>setVoice(e.target.value)}>
          <option value="">Choose a voice</option>
          {engine.voice_ids.map(id=><option key={id} value={id}>{id}</option>)}
        </select></label>
        <label>Speaking speed<input type="number" min="0.7" max="1.4" step="0.05" value={speed}
          onChange={e=>setSpeed(Number(e.target.value))} /></label>
        <button type="button" disabled={disabled || busy || !voice} onClick={()=>void save()}>Save this voice</button>
      </div>
      <p>Saved cast: {Object.entries(profiles).map(([name,p])=>name+' · '+p.voice_id+' ('+p.speed.toFixed(2)+'×)').join(' | ') || 'None yet'}</p>
      <h4>2. Select a passage</h4>
      <p>Highlight 1–1,200 characters in the spoken-text preview under “Character dialogue casting” above. Voice-tagged dialogue inside that selection will use the character's saved neural voice; the rest uses your narrator. Selection boundaries must not cut a tagged line.</p>
      <p><strong>Current selection:</strong> {selectionEnd>selectionStart ? (selectionEnd-selectionStart)+' characters' : 'No passage selected'}</p>
      <h4>3. Rehearse and direct</h4>
      <button type="button" disabled={disabled || busy || !selected || selectionEnd<=selectionStart || selectionEnd-selectionStart>1200}
        onClick={()=>void rehearse()}>{busy ? 'Synthesizing locally…' : 'Generate author-controlled scene rehearsal'}</button>
      {take && <div className="audiobook-track">
        <div><strong>Scene rehearsal · {take.seconds.toFixed(1)} seconds</strong>
          <small>{take.segments.map(x=>x.speaker+' ('+x.voice_id+')').join(' · ')}</small>
          <small>Not proof-approved or included in the publishing export.</small>
        </div>
        <audio controls preload="none" aria-label="Listen to the local neural scene rehearsal"
          src={endpoint+'/kokoro/rehearsals/'+encodeURIComponent(take.filename)} />
        <a download href={endpoint+'/kokoro/rehearsals/'+encodeURIComponent(take.filename)}>Save WAV</a>
      </div>}
    </>}
    <p>Quality is subjective. Listen for pronunciation, pacing, tone, and performance continuity. Model licenses and voices must be reviewed before commercial distribution.</p>
  </details>
}
