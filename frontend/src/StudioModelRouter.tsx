import { useEffect, useMemo, useState } from 'react'

import type { ProviderConfig } from './workspace-types'

type StudioMode = 'scene' | 'brainstorm' | 'creative'
type HeatLevel = 'simmer' | 'hot' | 'scorching' | 'inferno'
type WritingPurpose = 'auto' | 'adult' | 'general' | 'character' | 'planning'
type ResolvedPurpose = Exclude<WritingPurpose, 'auto'>
type PerformanceProfile = 'quality' | 'fast'

type Props = {
  provider: ProviderConfig
  models: string[]
  studioMode: StudioMode
  heatLevel: HeatLevel
  prompt: string
  busy: boolean
  onProviderChange: (provider: ProviderConfig) => void
  onRefresh: () => void | Promise<void>
}

type ModelGuide = {
  label: string
  bestFor: string
  why: string
}

const PURPOSE_STORAGE = 'emberwriter.studioWritingPurpose'
const AUTO_SWITCH_STORAGE = 'emberwriter.studioAutoModelRouting'
const PERFORMANCE_STORAGE = 'emberwriter.studioPerformanceProfile'

const PURPOSES: Record<WritingPurpose, { label: string; short: string; why: string }> = {
  auto: {
    label: 'Auto-match my writing',
    short: 'Studio decides from mode, heat, and your prompt.',
    why: 'General scenes stay on a strong general model; high-heat work moves to an uncensored model; planning favors instruction-following.',
  },
  adult: {
    label: 'Adult / high heat',
    short: 'Explicit adult intimacy and other on-page mature material.',
    why: 'Prioritizes uncensored creative-writing models so the requested scene is less likely to soften, refuse, or drift away from the brief.',
  },
  general: {
    label: 'General fiction',
    short: 'Fantasy, sci-fi, horror, action, mystery, romance, and ordinary scene drafting.',
    why: 'Prioritizes prose control, continuity, action, description, and non-explicit long-form fiction.',
  },
  character: {
    label: 'Character & dialogue',
    short: 'Banter, chemistry, relationship scenes, voice work, and roleplay-heavy passages.',
    why: 'Prioritizes models known for character voice and roleplay when they are installed.',
  },
  planning: {
    label: 'Plotting & analysis',
    short: 'Brainstorming, outlines, critique, continuity thinking, and story problem-solving.',
    why: 'Prioritizes reasoning and instruction-following over raw prose specialization.',
  },
}

const ADULT_PROMPT = /\b(?:sex|sexual|erotic|explicit|intimate|intimacy|kink|kinky|fetish|bdsm|orgasm|fuck|fucking|blowjob|oral sex|anal|penetrat(?:e|ion)|threesome|foursome|group sex)\b/i
const CHARACTER_PROMPT = /\b(?:dialogue|banter|chemistry|character voice|roleplay|relationship scene|conversation|flirt|flirting)\b/i

function readPurpose(): WritingPurpose {
  try {
    const value = localStorage.getItem(PURPOSE_STORAGE) as WritingPurpose | null
    return value && value in PURPOSES ? value : 'auto'
  } catch {
    return 'auto'
  }
}

function readAutoSwitch(): boolean {
  try {
    const value = localStorage.getItem(AUTO_SWITCH_STORAGE)
    return value === null ? true : value === 'true'
  } catch {
    return true
  }
}

function readPerformanceProfile(): PerformanceProfile {
  try {
    return localStorage.getItem(PERFORMANCE_STORAGE) === 'fast' ? 'fast' : 'quality'
  } catch {
    return 'quality'
  }
}

function inferPurpose(mode: StudioMode, heat: HeatLevel, prompt: string): ResolvedPurpose {
  if (mode === 'brainstorm') return 'planning'
  if (heat === 'scorching' || heat === 'inferno' || ADULT_PROMPT.test(prompt)) return 'adult'
  if (mode === 'creative' || CHARACTER_PROMPT.test(prompt)) return 'character'
  return 'general'
}

function normalized(model: string) {
  return model.toLocaleLowerCase()
}

function modelSize(model: string) {
  const match = normalized(model).match(/(?:^|[-_:])(\d+(?:\.\d+)?)b(?:[-_:]|$)/)
  return match ? Number(match[1]) : 0
}

function scoreModel(model: string, purpose: ResolvedPurpose, profile: PerformanceProfile): number {
  const name = normalized(model)
  const size = modelSize(model)
  const qwen25Heretic14 = name.includes('qwen2.5-14b') && name.includes('heretic')
  const qwen3Heretic8 = name.includes('qwen3-8b') && name.includes('heretic')
  const rocinante = name.includes('rocinante')
  const pygmalion3 = name.includes('pygmalion-3-12b')
  const magnumV4 = name.includes('magnum-v4-12b')
  const uncensored = name.includes('heretic') || name.includes('uncensored') || name.includes('abliterat')
  const mainstreamQwen3 = name.includes('qwen3') && !uncensored
  const mainstreamQwen25 = name.includes('qwen2.5') && !uncensored
  const mistralSmall = name.includes('mistral-small3.1') || name.includes('mistral-small-3.1')
  const roleplay = rocinante || name.includes('magnum') || name.includes('mag-mell') || name.includes('mag_mell') || name.includes('stheno') || name.includes('pygmalion')

  if (profile === 'fast') {
    let fastScore = 20
    if (qwen3Heretic8) fastScore += 150
    else if (size > 0 && size <= 8 && uncensored) fastScore += 130
    else if (size > 0 && size <= 9) fastScore += 100
    else if (size > 12) fastScore -= 40
    else if (size > 0) fastScore += Math.max(0, 55 - size * 2)
    if (purpose === 'adult' && uncensored) fastScore += 35
    if (purpose === 'character' && roleplay) fastScore += 25
    if (purpose === 'planning' && (mainstreamQwen3 || mainstreamQwen25)) fastScore += 20
    return fastScore
  }

  let score = 20 + Math.min(size || 0, 40) / 10
  if (purpose === 'adult') {
    if (pygmalion3) score += 140
    else if (magnumV4) score += 132
    else if (rocinante && uncensored) score += 115
    else if (qwen25Heretic14) score += 108
    else if (roleplay && uncensored) score += 104
    else if (uncensored && size >= 12) score += 98
    else if (qwen3Heretic8) score += 78
    else if (roleplay) score += 70
    else score += 25
  }
  if (purpose === 'general') {
    if (magnumV4) score += 106
    else if (mistralSmall) score += 100
    else if (mainstreamQwen25) score += 96
    else if (mainstreamQwen3) score += 94
    else if (qwen25Heretic14) score += 88
    else if (rocinante) score += 84
    else if (qwen3Heretic8) score += 72
    else score += 50
  }
  if (purpose === 'character') {
    if (pygmalion3) score += 120
    else if (magnumV4) score += 116
    else if (rocinante) score += 115
    else if (name.includes('magnum') || name.includes('mag-mell') || name.includes('mag_mell')) score += 105
    else if (name.includes('stheno') || name.includes('pygmalion')) score += 98
    else if (qwen25Heretic14) score += 90
    else if (qwen3Heretic8) score += 82
    else score += 55
  }
  if (purpose === 'planning') {
    if (mainstreamQwen3) score += 100
    else if (mainstreamQwen25) score += 98
    else if (qwen25Heretic14) score += 96
    else if (mistralSmall) score += 94
    else if (qwen3Heretic8) score += 86
    else score += 55
  }
  return score
}

function recommendModel(models: string[], purpose: ResolvedPurpose, profile: PerformanceProfile) {
  if (!models.length) return ''
  return [...models].sort((left, right) => scoreModel(right, purpose, profile) - scoreModel(left, purpose, profile))[0]
}

function describeModel(model: string): ModelGuide {
  const name = normalized(model)
  if (name.includes('qwen3-8b') && name.includes('heretic')) {
    return {
      label: 'Fast uncensored 8B',
      bestFor: 'Quick Studio drafts, brainstorming, character play, and lower-VRAM machines.',
      why: 'This is EmberWriter’s Fast profile target. It uses less model memory and smaller Studio budgets, improving the chance of full-GPU inference.',
    }
  }
  if (name.includes('pygmalion-3-12b')) {
    return {
      label: 'Adult / roleplay specialist 12B',
      bestFor: 'Direct adult scenes, character interaction, relationship-heavy roleplay, and scene-forward writing.',
      why: 'Pygmalion-3 is trained specifically for fictional roleplay and is EmberWriter’s primary adult-scene candidate when installed.',
    }
  }
  if (name.includes('magnum-v4-12b')) {
    return {
      label: 'Creative prose specialist 12B',
      bestFor: 'Polished scene prose, character chemistry, dialogue, and adult-scene drafting.',
      why: 'Magnum v4 is EmberWriter’s adult-prose challenger and a strong general/character-writing option.',
    }
  }
  if (name.includes('rocinante')) {
    return {
      label: 'Quality creative prose 12B',
      bestFor: 'Character voice, dialogue, chemistry, immersive scenes, and difficult long-form drafting.',
      why: 'This is EmberWriter’s preferred Quality profile when the managed Rocinante model is installed.',
    }
  }
  if (name.includes('qwen2.5-14b') && name.includes('heretic')) {
    return {
      label: '14B uncensored generalist',
      bestFor: 'Complex adult scenes and difficult instructions when speed is secondary.',
      why: 'More model capacity, but heavier local inference and VRAM pressure than the 8B and 12B profiles.',
    }
  }
  if (name.includes('mistral-small3.1') || name.includes('mistral-small-3.1')) {
    return { label: 'Mainstream general-purpose model', bestFor: 'Non-explicit fiction, action, editing, and worldbuilding.', why: 'A broad general-writing option when adult-content specialization is unnecessary.' }
  }
  if (name.includes('magnum') || name.includes('mag-mell') || name.includes('mag_mell')) {
    return { label: 'Creative prose specialist', bestFor: 'Expressive scene drafting, chemistry, dialogue, and roleplay-oriented prose.', why: 'Studio favors this family for character-centered creative work when available.' }
  }
  if (name.includes('stheno') || name.includes('pygmalion')) {
    return { label: 'Character / roleplay specialist', bestFor: 'Dialogue, personas, relationship interactions, and voice-forward scenes.', why: 'These families emphasize character interaction rather than planning or editorial analysis.' }
  }
  if (name.includes('qwen3') && !name.includes('heretic')) {
    return { label: 'Reasoning-oriented generalist', bestFor: 'Plotting, brainstorming, continuity, critique, and non-explicit drafting.', why: 'A strong structured-thinking option.' }
  }
  if (name.includes('qwen2.5') && !name.includes('heretic')) {
    return { label: 'Instruction-following generalist', bestFor: 'General fiction, editing, structured drafting, and story analysis.', why: 'A conventional all-purpose writing option.' }
  }
  return { label: 'Custom installed model', bestFor: 'Manual selection or experimentation.', why: 'Studio does not recognize this model family yet, so it remains available as a manual override.' }
}

function fitLabel(model: string, purpose: ResolvedPurpose, profile: PerformanceProfile) {
  const score = scoreModel(model, purpose, profile)
  if (score >= 120) return 'Strong match'
  if (score >= 90) return 'Good match'
  return 'Best installed fallback'
}

export default function StudioModelRouter({ provider, models, studioMode, heatLevel, prompt, busy, onProviderChange, onRefresh }: Props) {
  const [purpose, setPurpose] = useState<WritingPurpose>(readPurpose)
  const [autoSwitch, setAutoSwitch] = useState<boolean>(readAutoSwitch)
  const [performanceProfile, setPerformanceProfile] = useState<PerformanceProfile>(readPerformanceProfile)

  const inferredPurpose = useMemo(() => inferPurpose(studioMode, heatLevel, prompt), [studioMode, heatLevel, prompt])
  const resolvedPurpose: ResolvedPurpose = purpose === 'auto' ? inferredPurpose : purpose
  const recommended = useMemo(
    () => recommendModel(models, resolvedPurpose, performanceProfile),
    [models, resolvedPurpose, performanceProfile],
  )
  const activeGuide = provider.model ? describeModel(provider.model) : null

  useEffect(() => {
    try {
      localStorage.setItem(PURPOSE_STORAGE, purpose)
      localStorage.setItem(AUTO_SWITCH_STORAGE, String(autoSwitch))
      localStorage.setItem(PERFORMANCE_STORAGE, performanceProfile)
    } catch {
      // Local storage is a convenience only.
    }
  }, [purpose, autoSwitch, performanceProfile])

  useEffect(() => {
    if (!autoSwitch || !recommended) return
    if (provider.model === recommended && provider.lock_model === false) return
    onProviderChange({ ...provider, model: recommended, lock_model: false })
  }, [autoSwitch, recommended, provider, onProviderChange])

  function chooseManualModel(model: string) {
    setAutoSwitch(false)
    onProviderChange({ ...provider, model, lock_model: true })
  }

  function choosePerformanceProfile(profile: PerformanceProfile) {
    setPerformanceProfile(profile)
    setAutoSwitch(true)
    onProviderChange({ ...provider, lock_model: false })
  }

  function chooseAutoSwitch(enabled: boolean) {
    setAutoSwitch(enabled)
    if (enabled) {
      onProviderChange({ ...provider, model: recommended || provider.model, lock_model: false })
    }
  }

  const wrapperStyle = { minWidth: 360, maxWidth: 470, padding: 14, border: '1px solid var(--border, #2c3947)', borderRadius: 12, background: 'rgba(255,255,255,.025)' } as const
  const rowStyle = { display: 'flex', gap: 8, alignItems: 'center' } as const
  const labelStyle = { display: 'block', marginBottom: 6, color: 'var(--muted, #9eabb8)', fontSize: 12 } as const
  const hintStyle = { margin: '6px 0 0', color: 'var(--muted, #96a4b1)', fontSize: 11, lineHeight: 1.4 } as const
  const badgeStyle = { display: 'inline-block', marginTop: 7, padding: '3px 7px', border: '1px solid rgba(103,184,143,.35)', borderRadius: 999, color: '#9dd6b8', fontSize: 10 } as const

  return (
    <div className="ai-studio-model" style={wrapperStyle}>
      <label style={labelStyle}>Performance profile</label>
      <div style={{ ...rowStyle, marginBottom: 8 }}>
        <button type="button" className={performanceProfile === 'quality' ? 'active' : ''} onClick={() => choosePerformanceProfile('quality')} disabled={busy}>Quality 12B</button>
        <button type="button" className={performanceProfile === 'fast' ? 'active' : ''} onClick={() => choosePerformanceProfile('fast')} disabled={busy}>Fast 8B</button>
      </div>
      <p style={hintStyle}>
        {performanceProfile === 'fast'
          ? 'Fast favors an uncensored 8B model, a smaller adaptive context window, and a 3,072-token prose ceiling per pass.'
          : 'Quality uses the best installed 12B model for the author’s intent and allows a larger adaptive context plus up to 4,096 prose tokens per pass.'}
      </p>

      <label style={{ ...labelStyle, marginTop: 12 }}>Writing type</label>
      <select value={purpose} onChange={(event) => setPurpose(event.target.value as WritingPurpose)} disabled={busy}>
        {(Object.keys(PURPOSES) as WritingPurpose[]).map((item) => <option key={item} value={item}>{PURPOSES[item].label}</option>)}
      </select>
      <p style={hintStyle}>{PURPOSES[purpose].short}</p>
      <p style={hintStyle}>{PURPOSES[purpose].why}</p>

      <div style={{ ...rowStyle, marginTop: 11, justifyContent: 'space-between' }}>
        <label style={{ ...labelStyle, marginBottom: 0 }}>
          <input type="checkbox" checked={autoSwitch} onChange={(event) => chooseAutoSwitch(event.target.checked)} disabled={busy} style={{ width: 'auto', minHeight: 0, marginRight: 6 }} />
          Auto-switch within this profile
        </label>
        <button type="button" onClick={() => { setAutoSwitch(true); if (recommended) onProviderChange({ ...provider, model: recommended, lock_model: false }) }} disabled={busy || !recommended}>Best match</button>
      </div>

      <div style={{ marginTop: 12 }}>
        <label style={labelStyle}>Active model</label>
        <div style={rowStyle}>
          <select value={provider.model} onChange={(event) => chooseManualModel(event.target.value)} disabled={busy}>
            {!provider.model && <option value="">Choose model</option>}
            {models.map((model) => <option key={model} value={model}>{model}</option>)}
            {provider.model && !models.includes(provider.model) && <option value={provider.model}>{provider.model} · unavailable</option>}
          </select>
          <button type="button" onClick={() => void onRefresh()} disabled={busy} title="Refresh installed models">↻</button>
        </div>
      </div>

      {recommended && (
        <div style={{ marginTop: 10, padding: 10, border: '1px solid rgba(224,120,69,.22)', borderRadius: 9, background: 'rgba(224,120,69,.06)' }}>
          <strong style={{ display: 'block', fontSize: 12 }}>{performanceProfile === 'fast' ? 'Fast' : 'Quality'} recommendation: {recommended}</strong>
          <span style={badgeStyle}>{fitLabel(recommended, resolvedPurpose, performanceProfile)}</span>
          <p style={hintStyle}>{describeModel(recommended).bestFor}</p>
        </div>
      )}

      {performanceProfile === 'fast' && !models.some((model) => normalized(model).includes('qwen3-8b') && normalized(model).includes('heretic')) && (
        <p style={{ ...hintStyle, color: '#e8c986' }}>The managed Fast 8B model is not installed yet. Run install.ps1 after updating EmberWriter; Auto setup now installs both Fast 8B and Quality 12B.</p>
      )}

      {activeGuide && (
        <div style={{ marginTop: 10 }}>
          <strong style={{ display: 'block', fontSize: 12 }}>{activeGuide.label}</strong>
          <p style={hintStyle}><b>Use it for:</b> {activeGuide.bestFor}</p>
          <p style={hintStyle}><b>Why:</b> {activeGuide.why}</p>
          {!autoSwitch && <span style={{ ...badgeStyle, borderColor: 'rgba(226,178,89,.35)', color: '#e8c986' }}>Manual override locked</span>}
        </div>
      )}

      {models.length > 1 && (
        <details style={{ marginTop: 11, color: 'var(--muted, #9eabb8)', fontSize: 11 }}>
          <summary style={{ cursor: 'pointer' }}>Installed model guide</summary>
          <div style={{ display: 'grid', gap: 9, marginTop: 9 }}>
            {models.map((model) => {
              const guide = describeModel(model)
              return <div key={model} style={{ paddingTop: 8, borderTop: '1px solid rgba(255,255,255,.06)' }}><strong style={{ display: 'block', color: 'var(--text, #e6edf4)' }}>{model}</strong><span>{guide.label} · {guide.bestFor}</span><div style={{ marginTop: 3 }}>{guide.why}</div></div>
            })}
          </div>
        </details>
      )}

      {!models.length && <p style={hintStyle}>No installed models were returned by the configured provider. Refresh after installing or starting a local model.</p>}
    </div>
  )
}
