import { useEffect, useState } from 'react'

import './craft.css'

export type HeatLevel = 'simmer' | 'hot' | 'scorching' | 'inferno'
export type TensionCurve = 'slow_burn' | 'steady_rise' | 'pressure_cooker' | 'flashpoint'

export type CraftControls = {
  heat_level: HeatLevel | null
  tension_curve: TensionCurve | null
  voice_lock: boolean
  quality_pass: boolean
  sensory_intensity: number
  dialogue_intensity: number
  interiority: number
}

export type CraftProfile = {
  default_heat: HeatLevel
  default_tension_curve: TensionCurve
  quality_pass_default: boolean
  prose_directive: string
  avoidances: string[]
}

export type VoiceProfile = {
  name: string
  prose_directive: string
  sentence_rhythm: string
  diction: string
  imagery: string
  dialogue: string
  interiority: string
  pov_distance: string
  sensual_voice: string
  signature_traits: string[]
  avoidances: string[]
}

type Props = {
  controls: CraftControls
  profile: CraftProfile
  voiceProfile: VoiceProfile | null
  disabled: boolean
  sampleAvailable: boolean
  onControlsChange: (controls: CraftControls) => void
  onSaveProfile: (profile: CraftProfile) => Promise<void>
  onAnalyzeVoice: (profileName: string) => Promise<void>
}

const heatOptions: Array<{ value: HeatLevel; label: string; note: string }> = [
  { value: 'simmer', label: 'Simmer', note: 'anticipation' },
  { value: 'hot', label: 'Hot', note: 'sustained desire' },
  { value: 'scorching', label: 'Scorching', note: 'explicit adult' },
  { value: 'inferno', label: 'Inferno', note: 'maximum heat' },
]

const curves: Array<{ value: TensionCurve; label: string }> = [
  { value: 'slow_burn', label: 'Slow burn' },
  { value: 'steady_rise', label: 'Steady rise' },
  { value: 'pressure_cooker', label: 'Pressure cooker' },
  { value: 'flashpoint', label: 'Flashpoint' },
]

function RangeControl({
  label,
  value,
  onChange,
}: {
  label: string
  value: number
  onChange: (value: number) => void
}) {
  return (
    <label className="craft-range">
      <span>{label}<small>{value}/5</small></span>
      <input type="range" min="1" max="5" value={value} onChange={(event) => onChange(Number(event.target.value))} />
    </label>
  )
}

export default function CraftPanel({
  controls,
  profile,
  voiceProfile,
  disabled,
  sampleAvailable,
  onControlsChange,
  onSaveProfile,
  onAnalyzeVoice,
}: Props) {
  const [directive, setDirective] = useState(profile.prose_directive)
  const [avoidances, setAvoidances] = useState(profile.avoidances.join('; '))
  const [profileName, setProfileName] = useState(voiceProfile?.name || 'Book voice')

  useEffect(() => {
    setDirective(profile.prose_directive)
    setAvoidances(profile.avoidances.join('; '))
  }, [profile])

  useEffect(() => {
    if (voiceProfile?.name) setProfileName(voiceProfile.name)
  }, [voiceProfile?.name])

  function patch(next: Partial<CraftControls>) {
    onControlsChange({ ...controls, ...next })
  }

  async function saveDefaults() {
    await onSaveProfile({
      default_heat: controls.heat_level || profile.default_heat,
      default_tension_curve: controls.tension_curve || profile.default_tension_curve,
      quality_pass_default: controls.quality_pass,
      prose_directive: directive.trim(),
      avoidances: avoidances.split(';').map((item) => item.trim()).filter(Boolean),
    })
  }

  return (
    <details className="craft-panel" open>
      <summary>
        <span>Craft & Heat</span>
        <small>{controls.heat_level || profile.default_heat} · {controls.voice_lock ? 'voice locked' : 'free voice'}</small>
      </summary>

      <div className="craft-caption">Heat changes escalation and explicitness. Craft rules still control voice, pacing, and character.</div>

      <div className="heat-grid">
        {heatOptions.map((option) => (
          <button
            type="button"
            key={option.value}
            className={(controls.heat_level || profile.default_heat) === option.value ? 'active' : ''}
            onClick={() => patch({ heat_level: option.value })}
          >
            <strong>{option.label}</strong>
            <small>{option.note}</small>
          </button>
        ))}
      </div>

      <label className="craft-label">Tension curve</label>
      <select
        value={controls.tension_curve || profile.default_tension_curve}
        onChange={(event) => patch({ tension_curve: event.target.value as TensionCurve })}
      >
        {curves.map((curve) => <option key={curve.value} value={curve.value}>{curve.label}</option>)}
      </select>

      <div className="craft-ranges">
        <RangeControl label="Sensory" value={controls.sensory_intensity} onChange={(value) => patch({ sensory_intensity: value })} />
        <RangeControl label="Dialogue" value={controls.dialogue_intensity} onChange={(value) => patch({ dialogue_intensity: value })} />
        <RangeControl label="Interiority" value={controls.interiority} onChange={(value) => patch({ interiority: value })} />
      </div>

      <label className="toggle-row craft-toggle">
        <input type="checkbox" checked={controls.voice_lock} onChange={(event) => patch({ voice_lock: event.target.checked })} />
        <span><strong>Voice Lock</strong><small>Keep generated prose inside the learned book voice.</small></span>
      </label>

      <label className="toggle-row craft-toggle">
        <input type="checkbox" checked={controls.quality_pass} onChange={(event) => patch({ quality_pass: event.target.checked })} />
        <span><strong>Craft Pass</strong><small>Run a second line-edit pass for cadence, specificity, and repetition.</small></span>
      </label>

      <details className="voice-lab">
        <summary>Voice Lab</summary>
        <label>Profile name</label>
        <input value={profileName} onChange={(event) => setProfileName(event.target.value)} />
        <button
          type="button"
          className="voice-learn-button"
          disabled={disabled || !sampleAvailable || !profileName.trim()}
          onClick={() => void onAnalyzeVoice(profileName.trim())}
        >
          Learn voice from selection / chapter
        </button>
        {!sampleAvailable && <small className="craft-hint">Select at least 200 characters or open a chapter with enough prose.</small>}

        {voiceProfile && (
          <div className="voice-card">
            <strong>{voiceProfile.name}</strong>
            <p>{voiceProfile.prose_directive}</p>
            <div><span>Rhythm</span>{voiceProfile.sentence_rhythm}</div>
            <div><span>Dialogue</span>{voiceProfile.dialogue}</div>
            <div><span>Sensual voice</span>{voiceProfile.sensual_voice}</div>
            {voiceProfile.signature_traits.length > 0 && <small>{voiceProfile.signature_traits.join(' · ')}</small>}
          </div>
        )}
      </details>

      <details className="project-craft">
        <summary>Project craft rules</summary>
        <label>Prose directive</label>
        <textarea
          value={directive}
          onChange={(event) => setDirective(event.target.value)}
          placeholder="Example: close third person, muscular verbs, restrained metaphor, banter under pressure, no generic romance language…"
        />
        <label>Avoidances <small>semicolon separated</small></label>
        <input
          value={avoidances}
          onChange={(event) => setAvoidances(event.target.value)}
          placeholder="repetitive breath language; purple euphemism; interchangeable banter"
        />
        <button type="button" className="quiet save-craft" disabled={disabled} onClick={() => void saveDefaults()}>
          Save project defaults
        </button>
      </details>
    </details>
  )
}
