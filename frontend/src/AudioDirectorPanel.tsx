import { useEffect, useState } from 'react'

type Cue = {
  start: number
  end: number
  kind: 'dialogue' | 'narration'
  text: string
  speaker: string | null
  attribution?: string
  performance?: { emotion: string; delivery: string; confidence: string }
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
}
type Props = { apiBase: string; slug: string; path: string; disabled: boolean }

export default function AudioDirectorPanel({ apiBase, slug, path, disabled }: Props) {
  const endpoint = `${apiBase}/projects/${encodeURIComponent(slug)}/audiobook-production`
  const [script, setScript] = useState<Performance | null>(null)
  const [names, setNames] = useState<string[]>([])
  const [edit, setEdit] = useState<Record<number, {emotion: string; delivery: string}>>({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [showAll, setShowAll] = useState(false)
  const [fishTakes, setFishTakes] = useState<Record<number, string>>({})
  const [fishSpeakers, setFishSpeakers] = useState<string[]>([])

  useEffect(() => {
    let alive = true
    setScript(null); setError(''); setEdit({}); setShowAll(false); setFishTakes({}); setFishSpeakers([])
    if (!path) return
    void Promise.all([
      fetch(endpoint + '/performance?path=' + encodeURIComponent(path)),
      fetch(endpoint),
    ]).then(async ([performance, library]) => {
      if (!performance.ok || !library.ok) throw new Error('Could not open the audiobook performance manuscript.')
      return [await performance.json() as Performance, await library.json() as SpeakerLibrary] as const
    }).then(([performance, library]) => {
      if (!alive) return
      setScript(performance)
      setFishSpeakers(Object.keys(library.neural_voices || {}))
      setNames(Array.from(new Set(['Narrator', ...Object.keys(library.character_voices || {}),
        ...Object.keys(library.kokoro_voices || {}), ...Object.keys(library.neural_voices || {})])).sort())
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

  const dialogue = (script?.spans || []).filter(row => row.kind === 'dialogue')
  const shown = showAll ? dialogue : dialogue.filter(row => !row.speaker)
  return <details id="audio-director-tool" className="audiobook-direction" data-testid="audio-director">
    <summary>Audio Director · {script ? `${dialogue.length} spoken lines · ${script.unresolved_count} need review` : 'performance manuscript'}</summary>
    <p>The performance manuscript is a separate, lossless version of this chapter for narration. Every quotation gets its own voice and delivery direction. Unresolved voices block neural book production rather than defaulting to the narrator.</p>
    {!path && <p>Select a manuscript chapter first.</p>}
    {error && <p role="alert" className="audiobook-alert">{error}</p>}
    {message && <p role="status" className="audiobook-success">{message}</p>}
    {script && <>
      <p><strong>{script.render_ready ? 'Speaker preflight passed' : 'Speaker preflight blocked'}</strong> · {script.unresolved_count} unattributed dialogue lines.</p>
      <button type="button" onClick={() => setShowAll(v => !v)}>{showAll ? 'Show only unassigned dialogue' : 'Review all dialogue and performance cues'}</button>
      {shown.length === 0 && <p>Every identified quotation has a voice assignment. Review the emotional delivery before rendering.</p>}
      {shown.map(row => {
        const current = edit[row.start] || {emotion: row.performance?.emotion || 'neutral',
                                          delivery: row.performance?.delivery || 'natural'}
        return <div key={row.start} className="audiobook-job-chapter" style={{display:'block',margin:'0.7rem 0',padding:'0.7rem'}}>
          <blockquote style={{whiteSpace:'pre-wrap',margin:'0 0 0.5rem'}}>{row.text}</blockquote>
          <small>Characters {row.start}–{row.end} · {row.attribution || 'unresolved'}</small>
          <div className="audiobook-editor-row">
            <label>Speaking character
              <select aria-label={`Speaker for line ${row.start}`} value={row.speaker || ''} disabled={disabled || busy}
                onChange={e => void save('/performance/speaker', {start:row.start, end:row.end, speaker:e.target.value})}>
                <option value="">Unassigned — requires review</option>
                {names.filter(name => name !== 'Narrator').map(name => <option key={name} value={name}>{name}</option>)}
              </select>
            </label>
            <label>Emotion
              <select value={current.emotion} disabled={disabled || busy}
                onChange={e => setEdit(p => ({...p,[row.start]:{...current,emotion:e.target.value}}))}>
                {['neutral','fear','sadness','joy','anger','urgency','relief','determination','uncertainty','tenderness'].map(v => <option key={v} value={v}>{v}</option>)}
              </select>
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
            {row.speaker && fishSpeakers.includes(row.speaker) && <button type="button" disabled={disabled || busy}
              onClick={() => void fishPreview(row.start)}>Rehearse with Fish (local)</button>}
          </div>
          {fishTakes[row.start] && <audio controls src={fishTakes[row.start]} aria-label={`Fish performance rehearsal for line ${row.start}`} />}
        </div>
      })}
    </>}
  </details>
}
