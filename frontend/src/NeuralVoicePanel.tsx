import { useEffect, useState } from 'react'

type Character = { reference_id: string; direction: string; seed: number | null }
type Cast = { start: number; end: number; text: string; voice: string; character?: string }

type Props = {
  productionEndpoint: string
  selected: string
  casts: Cast[]
  characters: string[]
  disabled: boolean
}

export default function NeuralVoicePanel({ productionEndpoint, selected, casts, characters, disabled }: Props) {
  const [library, setLibrary] = useState<Record<string, Character>>({})
  const [character, setCharacter] = useState('')
  const [referenceId, setReferenceId] = useState('')
  const [direction, setDirection] = useState('')
  const [seed, setSeed] = useState('')
  const [port, setPort] = useState('8080')
  const [busy, setBusy] = useState(false)
  const [health, setHealth] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [take, setTake] = useState<{ filename: string; character: string; status: string } | null>(null)
  const tagged = casts.filter(row => !!row.character)

  useEffect(() => {
    let live = true
    setTake(null)
    void fetch(productionEndpoint + '/neural-voices')
      .then(async response => { if (!response.ok) throw new Error('Could not load saved neural voices'); return response.json() as Promise<Record<string, Character>> })
      .then(value => { if (live) setLibrary(value) })
      .catch(e => { if (live) setError(String(e)) })
    return () => { live = false }
  }, [productionEndpoint])

  async function request(url: string, options?: RequestInit) {
    const response = await fetch(productionEndpoint + url, {
      ...options,
      headers: { 'Content-Type': 'application/json', ...(options?.headers ?? {}) },
    })
    if (!response.ok) {
      const body = await response.json().catch(() => ({}))
      throw new Error(body.detail || 'Local neural speech request failed')
    }
    return response.json()
  }

  async function save() {
    setBusy(true); setError(''); setMessage('')
    try {
      await request('/neural-voices', { method: 'PUT', body: JSON.stringify({
        character, reference_id: referenceId, direction, seed: seed === '' ? null : Number(seed),
      }) })
      setLibrary(await request('/neural-voices') as Record<string, Character>)
      setMessage('Neural voice direction saved locally for this character.')
    } catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }

  async function check() {
    setBusy(true); setError(''); setHealth('')
    try {
      const result = await request('/neural-health?port=' + Number(port)) as {reachable: boolean}
      setHealth(result.reachable ? 'Local Fish Speech server responding. Model identity and voice references are not verified.' : 'No compatible speech server detected on that local port.')
    } catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }

  async function rehearse(start: number) {
    setBusy(true); setError(''); setTake(null); setMessage('')
    try {
      const result = await request('/neural-takes', { method: 'POST', body: JSON.stringify({
        path: selected, start, port: Number(port),
      }) }) as { filename: string; character: string; status: string }
      setTake(result)
      setMessage('A local neural proof take was generated. It is not approved for publication.')
    } catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }

  return <details className="audiobook-direction">
    <summary>Neural Voice Studio — local Fish Speech / Drama 3 proof takes</summary>
    <p>Experimental, author-directed neural narration. Run a compatible Fish Speech API on your computer and register reference voices in that server first. EmberWriter connects only to 127.0.0.1, and saves reference IDs, performance direction, and proof takes locally. Nothing here replaces the finished audiobook tracks automatically.</p>
    <p><strong>Hardware:</strong> Drama 3 has substantial NVIDIA GPU requirements. A responsive local server does not guarantee Drama 3 is loaded. Use only voices and references you have the rights and consent to use; check Fish Audio model licensing before commercial distribution.</p>
    {error && <p role="alert" className="audiobook-alert">{error}</p>}
    {message && <p role="status">{message}</p>}
    <div className="audiobook-editor-row">
      <label>Local Fish server port<input type="number" min="1024" max="65535" value={port} onChange={e=>setPort(e.target.value)} /></label>
      <button type="button" disabled={disabled || busy} onClick={()=>void check()}>Check local speech server</button>
    </div>
    {health && <p role="status">{health}</p>}
    <div className="audiobook-editor-row">
      <label>Saved character<select value={character} onChange={e=>{
        const name = e.target.value; setCharacter(name)
        setReferenceId(library[name]?.reference_id || '')
        setDirection(library[name]?.direction || '')
        setSeed(library[name]?.seed == null ? '' : String(library[name].seed))
      }}>
        <option value="">Choose character</option>
        {characters.map(name=><option key={name} value={name}>{name}</option>)}
      </select></label>
      <label>Fish reference ID<input value={referenceId} maxLength={80} onChange={e=>setReferenceId(e.target.value)} placeholder="mira-voice" /></label>
      <label>Performance direction<input value={direction} maxLength={500} onChange={e=>setDirection(e.target.value)} placeholder="quiet, tense, restrained" /></label>
      <label>Optional seed<input type="number" min="0" max="4294967295" value={seed} onChange={e=>setSeed(e.target.value)} /></label>
      <button type="button" disabled={disabled || busy || !character || !referenceId.trim()} onClick={()=>void save()}>Save neural voice</button>
    </div>
    <p>Saved voices: {Object.entries(library).map(([name, value])=>name + ' → ' + value.reference_id).join(' · ') || 'None yet'}. Seeds may help repeat a generation but do not fix vocal identity; reference audio is essential.</p>
    <h4>Whole-novel audio-drama script</h4>
    <p>Export a Binder-ordered production plan with exact manuscript anchors, saved voice references, performance direction, and missing-voice warnings. This is a script/metadata export for human review, not rendered audio.</p>
    <a href={productionEndpoint+'/neural-production-plan'} download="emberwriter-audio-drama-plan.json">Export full-novel voice and dialogue production plan (JSON)</a>
    <h4>Rehearse an assigned dialogue line</h4>
    {tagged.length === 0 && <p>First tag spoken text with a saved character in the casting controls above.</p>}
    {tagged.map((span, index)=><div className="audiobook-editor-row" key={index+':'+span.start}>
      <span><strong>{span.character}</strong> · {span.text.slice(0,150)}</span>
      <button type="button" disabled={disabled || busy || !library[span.character || '']} onClick={()=>void rehearse(span.start)}>Generate local proof take</button>
    </div>)}
    {take && <div className="audiobook-track">
      <p><strong>{take.character}</strong> · {take.status}</p>
      <audio controls preload="none" aria-label={'Neural proof take for '+take.character} src={productionEndpoint+'/neural-takes/'+encodeURIComponent(take.filename)} />
      <a download href={productionEndpoint+'/neural-takes/'+encodeURIComponent(take.filename)}>Save this rehearsal WAV</a>
    </div>}
  </details>
}
