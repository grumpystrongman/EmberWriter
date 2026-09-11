import { useEffect, useMemo, useState } from 'react'

import type { ScenePlan, ScenePlanResponse } from './SceneArchitectPanel'
import type { StoryIntelligence } from './StoryIntelligencePanel'
import type { ProviderConfig, WorkspaceProject } from './workspace-types'

type Props = {
  apiBase: string
  project: WorkspaceProject
  sceneFiles: string[]
  onOpenSource: (path: string, anchor?: string) => void
  onFilesChanged: () => void
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

function StringList({ title, values }: { title: string; values: string[] }) {
  if (!values.length) return null
  return <div className="scene-center-list"><strong>{title}</strong>{values.map((value, index) => <div key={`${title}-${index}`}>• {value}</div>)}</div>
}

function writerPrompt(plan: ScenePlan) {
  const beats = plan.beats.map((beat, index) => `${index + 1}. ${beat.beat}${beat.purpose ? ` — ${beat.purpose}` : ''}`).join('\n')
  const guardrails = plan.continuity_requirements.map((item) => `- ${item}`).join('\n')
  const relationships = plan.relationship_moves.map((item) => `- ${item}`).join('\n')
  const intimacy = plan.intimacy_notes.map((item) => `- ${item}`).join('\n')
  return [
    `Write the planned scene “${plan.title}” as polished manuscript prose.`,
    `POV: ${plan.pov || 'infer from plan'}\nLocation: ${plan.location || 'infer from canon'}\nObjective: ${plan.scene_objective}\nConflict: ${plan.conflict}`,
    `Required beats:\n${beats}`,
    `Continuity guardrails:\n${guardrails || '- Preserve established canon and character knowledge boundaries.'}`,
    `Relationship movement:\n${relationships || '- Preserve established relationship state.'}`,
    intimacy ? `Intimacy / tension notes:\n${intimacy}` : '',
    `Ending state: ${plan.ending_state}\nNext-scene pressure: ${plan.next_scene_pressure}`,
  ].filter(Boolean).join('\n\n')
}

export default function ScenePlannerWorkspace({ apiBase, project, sceneFiles, onOpenSource, onFilesChanged }: Props) {
  const [intelligence, setIntelligence] = useState<StoryIntelligence>({ characters: [], relationships: [] })
  const [prompt, setPrompt] = useState('')
  const [pov, setPov] = useState('')
  const [location, setLocation] = useState('')
  const [heat, setHeat] = useState('author controlled')
  const [participants, setParticipants] = useState<string[]>([])
  const [result, setResult] = useState<ScenePlanResponse | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const characterNames = useMemo(() => intelligence.characters.map((character) => character.name), [intelligence.characters])

  useEffect(() => {
    void request<StoryIntelligence>(`${apiBase}/projects/${project.slug}/story-intelligence`)
      .then(setIntelligence)
      .catch(() => setIntelligence({ characters: [], relationships: [] }))
  }, [apiBase, project.slug])

  function toggleParticipant(name: string) {
    setParticipants((current) => current.includes(name) ? current.filter((item) => item !== name) : [...current, name])
  }

  async function architect() {
    if (!prompt.trim()) return
    const provider = currentProvider()
    if (!provider) {
      setError('Choose an AI model before using Scene Architect.')
      return
    }
    setBusy(true)
    setError('')
    try {
      const response = await request<ScenePlanResponse>(`${apiBase}/projects/${project.slug}/scene-plan`, {
        method: 'POST',
        body: JSON.stringify({
          prompt: prompt.trim(),
          provider,
          active_file: project.activePath || null,
          pov: pov.trim(),
          participants,
          location: location.trim(),
          desired_heat: heat.trim() || 'author controlled',
          save: true,
        }),
      })
      setResult(response)
      onFilesChanged()
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  function sendToWriter(plan: ScenePlan) {
    window.dispatchEvent(new CustomEvent('emberwriter:writer-brief', { detail: { prompt: writerPrompt(plan), mode: 'write' } }))
  }

  return (
    <div className="scene-center-workspace">
      <div className="scene-center-grid">
        <section className="scene-center-form">
          <div className="center-section-heading"><div><h2>Scene Architect</h2><p>Build a story-aware scene plan before prose. You can specify as much or as little as you want.</p></div></div>
          <label>What must happen<textarea rows={7} value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder="The protagonist confronts the witness, learns the alibi is false, but chooses not to expose her yet. Slow-burn tension with…" /></label>
          <div className="scene-center-fields">
            <label>POV<input value={pov} onChange={(event) => setPov(event.target.value)} placeholder="infer or specify" /></label>
            <label>Location<input value={location} onChange={(event) => setLocation(event.target.value)} placeholder="infer or specify" /></label>
            <label className="wide">Heat / intimacy direction<input value={heat} onChange={(event) => setHeat(event.target.value)} placeholder="author controlled" /></label>
          </div>
          {characterNames.length > 0 && <div className="scene-center-participants"><small>PARTICIPANTS</small><div className="tag-choice-row">{characterNames.slice(0, 30).map((name) => <button type="button" key={name} className={participants.includes(name) ? 'active' : ''} onClick={() => toggleParticipant(name)}>{name}</button>)}</div></div>}
          <button type="button" className="primary" onClick={() => void architect()} disabled={busy || !prompt.trim()}>{busy ? 'Architecting from story state…' : 'Architect scene'}</button>
          <small className="center-help">Ember uses Story Memory, character knowledge, relationship chemistry, unresolved threads, and nearby manuscript context. The saved plan is a normal project artifact you can inspect and edit.</small>
        </section>

        <aside className="scene-plan-library">
          <div className="center-section-heading"><div><h2>Saved plans</h2><p>{sceneFiles.length} project artifact{sceneFiles.length === 1 ? '' : 's'}</p></div></div>
          {sceneFiles.length === 0 && <div className="center-empty">No saved scene plans yet.</div>}
          <div className="scene-plan-file-list">{sceneFiles.map((path) => <button type="button" key={path} onClick={() => onOpenSource(path)}><span>▤</span><div><strong>{path.split('/').at(-1)?.replace(/\.(json|md)$/i, '')}</strong><small>{path}</small></div></button>)}</div>
        </aside>
      </div>

      {result && <section className="scene-center-result">
        <div className="scene-center-result-head"><div><small>SCENE PLAN</small><h2>{result.plan.title}</h2></div><div><button type="button" className="primary" onClick={() => sendToWriter(result.plan)}>Send plan to Write</button>{result.saved_path && <button type="button" onClick={() => onOpenSource(result.saved_path!)}>Open saved plan</button>}</div></div>
        <div className="scene-center-meta"><span><b>POV</b> {result.plan.pov || '—'}</span><span><b>Location</b> {result.plan.location || '—'}</span><span><b>Participants</b> {result.plan.participants.join(', ') || '—'}</span></div>
        <div className="scene-center-core"><p><strong>Objective:</strong> {result.plan.scene_objective}</p><p><strong>Conflict:</strong> {result.plan.conflict}</p>{result.plan.opening_state && <p><strong>Opening state:</strong> {result.plan.opening_state}</p>}{result.plan.emotional_arc && <p><strong>Emotional arc:</strong> {result.plan.emotional_arc}</p>}</div>
        <div className="scene-center-beats"><h3>Beats</h3>{result.plan.beats.map((beat, index) => <article key={`${beat.beat}-${index}`}><span>{index + 1}</span><div><strong>{beat.beat}</strong>{beat.purpose && <p>{beat.purpose}</p>}{beat.character_shift && <small>{beat.character_shift}</small>}</div></article>)}</div>
        <div className="scene-center-detail-grid"><StringList title="Relationship movement" values={result.plan.relationship_moves} /><StringList title="Reveals" values={result.plan.reveals} /><StringList title="Continuity guardrails" values={result.plan.continuity_requirements} /><StringList title="Threads in play" values={result.plan.unresolved_threads} /><StringList title="Intimacy / tension" values={result.plan.intimacy_notes} /></div>
        <div className="scene-center-ending"><p><strong>Ending state:</strong> {result.plan.ending_state}</p><p><strong>Next-scene pressure:</strong> {result.plan.next_scene_pressure}</p></div>
      </section>}

      {error && <div className="center-error">{error}</div>}
    </div>
  )
}
