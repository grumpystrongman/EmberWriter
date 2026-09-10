import { useMemo, useState } from 'react'

import type { CharacterProfile } from './StoryIntelligencePanel'

export type SceneBeat = {
  beat: string
  purpose: string
  character_shift: string
}

export type ScenePlan = {
  title: string
  pov: string
  participants: string[]
  location: string
  scene_objective: string
  conflict: string
  opening_state: string
  beats: SceneBeat[]
  emotional_arc: string
  relationship_moves: string[]
  reveals: string[]
  continuity_requirements: string[]
  unresolved_threads: string[]
  intimacy_notes: string[]
  ending_state: string
  next_scene_pressure: string
}

export type ScenePlanResponse = {
  plan: ScenePlan
  saved_path?: string | null
  context_files: string[]
}

type SceneInput = {
  prompt: string
  pov: string
  participants: string[]
  location: string
  desired_heat: string
}

type Props = {
  characters: CharacterProfile[]
  disabled: boolean
  onGenerate: (input: SceneInput) => Promise<ScenePlanResponse | null>
  onOpenSaved: (path: string) => void
  onUseAsPrompt: (plan: ScenePlan) => void
}

function StringList({ title, values }: { title: string; values: string[] }) {
  if (!values.length) return null
  return (
    <div className="scene-plan-list">
      <h4>{title}</h4>
      {values.map((value, index) => <div key={`${title}-${index}`}>• {value}</div>)}
    </div>
  )
}

export default function SceneArchitectPanel({
  characters,
  disabled,
  onGenerate,
  onOpenSaved,
  onUseAsPrompt,
}: Props) {
  const [prompt, setPrompt] = useState('')
  const [pov, setPov] = useState('')
  const [location, setLocation] = useState('')
  const [heat, setHeat] = useState('author controlled')
  const [participantNames, setParticipantNames] = useState<string[]>([])
  const [result, setResult] = useState<ScenePlanResponse | null>(null)
  const characterNames = useMemo(() => characters.map((character) => character.name), [characters])

  function toggleParticipant(name: string) {
    setParticipantNames((current) => (
      current.includes(name) ? current.filter((item) => item !== name) : [...current, name]
    ))
  }

  async function generate() {
    if (!prompt.trim() || disabled) return
    const response = await onGenerate({
      prompt: prompt.trim(),
      pov: pov.trim(),
      participants: participantNames,
      location: location.trim(),
      desired_heat: heat.trim() || 'author controlled',
    })
    if (response) setResult(response)
  }

  return (
    <details className="scene-architect-panel" open>
      <summary>
        <span>Scene Architect</span>
        <small>plan before prose</small>
      </summary>

      <textarea
        className="scene-request"
        value={prompt}
        onChange={(event) => setPrompt(event.target.value)}
        placeholder="What must happen in the next scene? Include tension, revelations, relationship movement, or constraints."
      />

      <div className="scene-field-grid">
        <label>
          POV
          <input value={pov} onChange={(event) => setPov(event.target.value)} placeholder="infer or specify" />
        </label>
        <label>
          Location
          <input value={location} onChange={(event) => setLocation(event.target.value)} placeholder="infer or specify" />
        </label>
      </div>

      <label className="scene-label">Heat / intimacy direction</label>
      <input value={heat} onChange={(event) => setHeat(event.target.value)} placeholder="author controlled" />

      {characterNames.length > 0 && (
        <div className="scene-participants">
          <span>Participants</span>
          <div className="character-chip-row">
            {characterNames.slice(0, 18).map((name) => (
              <button
                type="button"
                key={name}
                className={participantNames.includes(name) ? 'active' : ''}
                onClick={() => toggleParticipant(name)}
              >
                {name}
              </button>
            ))}
          </div>
        </div>
      )}

      <button className="primary scene-plan-button" disabled={disabled || !prompt.trim()} onClick={() => void generate()}>
        {disabled ? 'Model busy…' : 'Architect scene'}
      </button>

      {result && (
        <div className="scene-plan-card">
          <div className="scene-plan-head">
            <div>
              <small>SCENE PLAN</small>
              <h3>{result.plan.title}</h3>
            </div>
            <div className="scene-plan-actions">
              <button className="quiet" onClick={() => onUseAsPrompt(result.plan)}>Send to Writer</button>
              {result.saved_path && <button className="quiet" onClick={() => onOpenSaved(result.saved_path!)}>Open saved</button>}
            </div>
          </div>
          <div className="scene-plan-meta">
            <span>POV: {result.plan.pov || '—'}</span>
            <span>Location: {result.plan.location || '—'}</span>
          </div>
          <p><strong>Objective:</strong> {result.plan.scene_objective}</p>
          <p><strong>Conflict:</strong> {result.plan.conflict}</p>
          {result.plan.opening_state && <p><strong>Opening:</strong> {result.plan.opening_state}</p>}

          <div className="scene-beats">
            <h4>Beats</h4>
            {result.plan.beats.map((beat, index) => (
              <div className="scene-beat" key={`${beat.beat}-${index}`}>
                <span>{index + 1}</span>
                <div>
                  <strong>{beat.beat}</strong>
                  {beat.purpose && <small>{beat.purpose}</small>}
                  {beat.character_shift && <em>{beat.character_shift}</em>}
                </div>
              </div>
            ))}
          </div>

          {result.plan.emotional_arc && <p><strong>Emotional arc:</strong> {result.plan.emotional_arc}</p>}
          <StringList title="Relationship movement" values={result.plan.relationship_moves} />
          <StringList title="Reveals" values={result.plan.reveals} />
          <StringList title="Continuity guardrails" values={result.plan.continuity_requirements} />
          <StringList title="Threads in play" values={result.plan.unresolved_threads} />
          <StringList title="Intimacy notes" values={result.plan.intimacy_notes} />
          {result.plan.ending_state && <p><strong>Ending state:</strong> {result.plan.ending_state}</p>}
          {result.plan.next_scene_pressure && <p><strong>Next pressure:</strong> {result.plan.next_scene_pressure}</p>}
          <details>
            <summary>Context used ({result.context_files.length})</summary>
            {result.context_files.map((file) => <div className="context-file" key={file}>{file}</div>)}
          </details>
        </div>
      )}
    </details>
  )
}
