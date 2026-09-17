import { useEffect, useMemo, useState } from 'react'

import type { ProviderConfig } from './workspace-types'

type StudioMode = 'scene' | 'brainstorm' | 'creative'
type HeatLevel = 'simmer' | 'hot' | 'scorching' | 'inferno'
type WritingPurpose = 'auto' | 'adult' | 'general' | 'character' | 'planning'
type ResolvedPurpose = Exclude<WritingPurpose, 'auto'>

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

const PURPOSES: Record<WritingPurpose, { label: string; short: string; why: string }> = {
  auto: {
    label: 'Auto-match my writing',
    short: 'Studio decides from mode, heat, and your prompt.',
    why: 'Use this most of the time. General scenes stay on a strong general model; explicit/high-heat work moves to an uncensored model; planning favors reasoning and instruction-following.',
  },
  adult: {
    label: 'Adult / high heat',
    short: 'Explicit intimacy, kink, erotic harem scenes, and other on-page adult material.',
    why: 'Prioritizes uncensored creative-writing models so the requested adult scene is less likely to soften, refuse, or drift away from the brief.',
  },
  general: {
    label: 'General fiction',
    short: 'Fantasy, sci-fi, horror, action, mystery, romance, and ordinary scene drafting.',
    why: 'Prioritizes larger or mainstream instruction models for prose control, continuity, action, description, and non-explicit long-form fiction.',
  },
  character: {
    label: 'Character & dialogue',
    short: 'Banter, chemistry, relationship scenes, voice work, and roleplay-heavy passages.',
    why: 'Prioritizes models known for character voice and roleplay when they are installed, then falls back to the strongest creative model available.',
  },
  planning: {
    label: 'Plotting & analysis',
    short: 'Brainstorming, outlines, critique, continuity thinking, and story problem-solving.',
    why: 'Prioritizes reasoning and instruction-following over raw prose heat so ideas, tradeoffs, and story logic stay organized.',
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

function inferPurpose(mode: StudioMode, heat: HeatLevel, prompt: string): ResolvedPurpose {
  if (mode === 'brainstorm') return 'planning'
  if (heat === 'scorching' || heat === 'inferno' || ADULT_PROMPT.test(prompt)) return 'adult'
  if (mode === 'creative' || CHARACTER_PROMPT.test(prompt)) return 'character'
  return 'general'
}

function normalized(model: string) {
  return model.toLocaleLowerCase()
}

function modelSizeBonus(model: string) {
  const match = normalized(model).match(/(?:^|[-_:])(\d+(?:\.\d+)?)b(?:[-_:]|$)/)
  return match ? Math.min(Number(match[1]), 40) / 10 : 0
}

function scoreModel(model: string, purpose: ResolvedPurpose): number {
  const name = normalized(model)
  const qwen25Heretic14 = name.includes('qwen2.5-14b') && name.includes('heretic')
  const qwen3Heretic8 = name.includes('qwen3-8b') && name.includes('heretic')
  const uncensored = name.includes('heretic') || name.includes('uncensored') || name.includes('abliterat')
  const mainstreamQwen3 = name.includes('qwen3') && !uncensored
  const mainstreamQwen25 = name.includes('qwen2.5') && !uncensored
  const mistralSmall = name.includes('mistral-small3.1') || name.includes('mistral-small-3.1')
  const roleplay = name.includes('rocinante') || name.includes('magnum') || name.includes('mag-mell') || name.includes('mag_mell') || name.includes('stheno') || name.includes('pygmalion')

  let score = 20 + modelSizeBonus(model)

  if (purpose === 'adult') {
    if (qwen25Heretic14) score += 100
    else if (qwen3Heretic8) score += 92
    else if (roleplay && uncensored) score += 88
    else if (uncensored) score += 78
    else if (roleplay) score += 65
    else score += 25
  }

  if (purpose === 'general') {
    if (mistralSmall) score += 100
    else if (mainstreamQwen25) score += 96
    else if (mainstreamQwen3) score += 94
    else if (qwen25Heretic14) score += 88
    else if (qwen3Heretic8) score += 78
    else if (roleplay) score += 68
    else score += 50
  }

  if (purpose === 'character') {
    if (name.includes('rocinante')) score += 100
    else if (name.includes('magnum') || name.includes('mag-mell') || name.includes('mag_mell')) score += 98
    else if (name.includes('stheno')) score += 95
    else if (name.includes('pygmalion')) score += 92
    else if (qwen3Heretic8) score += 90
    else if (qwen25Heretic14) score += 87
    else if (mistralSmall || mainstreamQwen3 || mainstreamQwen25) score += 80
    else score += 55
  }

  if (purpose === 'planning') {
    if (mainstreamQwen3) score += 100
    else if (mainstreamQwen25) score += 98
    else if (qwen25Heretic14) score += 96
    else if (mistralSmall) score += 94
    else if (qwen3Heretic8) score += 90
    else score += 55
  }

  return score
}

function recommendModel(models: string[], purpose: ResolvedPurpose) {
  if (!models.length) return ''
  return [...models].sort((left, right) => scoreModel(right, purpose) - scoreModel(left, purpose))[0]
}

function describeModel(model: string): ModelGuide {
  const name = normalized(model)
  if (name.includes('qwen2.5-14b') && name.includes('heretic')) {
    return {
      label: '14B uncensored generalist',
      bestFor: 'High-heat adult scenes, difficult long-form scenes, and complex instructions.',
      why: 'The larger 14B model gives Studio more room for continuity and instruction-following while keeping refusal behavior reduced. Prefer it when quality matters more than speed.',
    }
  }
  if (name.includes('qwen3-8b') && name.includes('heretic')) {
    return {
      label: 'Fast uncensored 8B',
      bestFor: 'Quick adult drafts, brainstorming, character play, and lower-VRAM machines.',
      why: 'It is faster and lighter than the 14B option and retains Qwen3 reasoning behavior, but long-scene consistency can be less steady.',
    }
  }
  if (name.includes('mistral-small3.1') || name.includes('mistral-small-3.1')) {
    return {
      label: 'Mainstream general-purpose model',
      bestFor: 'Non-explicit fiction, action, editing, worldbuilding, and conventional prose.',
      why: 'A strong fit when you want broad instruction-following and prose work without specifically optimizing for uncensored adult content.',
    }
  }
  if (name.includes('rocinante')) {
    return {
      label: 'Creative prose / roleplay specialist',
      bestFor: 'Character voice, dialogue, chemistry, immersive scenes, and relationship-heavy writing.',
      why: 'Studio treats Rocinante-family models as character-first creative options when installed.',
    }
  }
  if (name.includes('magnum') || name.includes('mag-mell') || name.includes('mag_mell')) {
    return {
      label: 'Creative prose specialist',
      bestFor: 'Expressive scene drafting, character chemistry, dialogue, and roleplay-oriented prose.',
      why: 'Studio favors this family for character-centered creative work when it is available locally.',
    }
  }
  if (name.includes('stheno') || name.includes('pygmalion')) {
    return {
      label: 'Character / roleplay specialist',
      bestFor: 'Dialogue, personas, relationship interactions, and voice-forward scene work.',
      why: 'These model families are weighted toward character interaction rather than planning or editorial analysis.',
    }
  }
  if (name.includes('qwen3') && !name.includes('heretic')) {
    return {
      label: 'Reasoning-oriented generalist',
      bestFor: 'Plotting, brainstorming, continuity, critique, and non-explicit drafting.',
      why: 'Studio prefers standard Qwen3-family models for structured story thinking when one is installed.',
    }
  }
  if (name.includes('qwen2.5') && !name.includes('heretic')) {
    return {
      label: 'Instruction-following generalist',
      bestFor: 'General fiction, editing, structured drafting, and story analysis.',
      why: 'A conventional all-purpose choice when adult-content specialization is unnecessary.',
    }
  }
  if (name.includes('gemma') || name.includes('mistral') || name.includes('llama')) {
    return {
      label: 'General-purpose model',
      bestFor: 'General fiction, story development, editing, and ordinary creative work.',
      why: 'Studio can use it as a mainstream writing option; exact strengths depend on the specific fine-tune and size.',
    }
  }
  return {
    label: 'Custom installed model',
    bestFor: 'Manual selection or experimentation.',
    why: 'Studio does not recognize this model family yet, so it remains available as a manual override and a fallback when needed.',
  }
}

function fitLabel(model: string, purpose: ResolvedPurpose) {
  const score = scoreModel(model, purpose)
  if (score >= 112) return 'Strong match'
  if (score >= 95) return 'Good match'
  return 'Best installed fallback'
}

export default function StudioModelRouter({
  provider,
  models,
  studioMode,
  heatLevel,
  prompt,
  busy,
  onProviderChange,
  onRefresh,
}: Props) {
  const [purpose, setPurpose] = useState<WritingPurpose>(readPurpose)
  const [autoSwitch, setAutoSwitch] = useState<boolean>(readAutoSwitch)

  const inferredPurpose = useMemo(() => inferPurpose(studioMode, heatLevel, prompt), [studioMode, heatLevel, prompt])
  const resolvedPurpose: ResolvedPurpose = purpose === 'auto' ? inferredPurpose : purpose
  const recommended = useMemo(() => recommendModel(models, resolvedPurpose), [models, resolvedPurpose])
  const activeGuide = provider.model ? describeModel(provider.model) : null

  useEffect(() => {
    try {
      localStorage.setItem(PURPOSE_STORAGE, purpose)
      localStorage.setItem(AUTO_SWITCH_STORAGE, String(autoSwitch))
    } catch {
      // Local storage is a convenience only; routing still works for the current session.
    }
  }, [purpose, autoSwitch])

  useEffect(() => {
    if (!autoSwitch || !recommended || provider.model === recommended) return
    onProviderChange({ ...provider, model: recommended })
  }, [autoSwitch, recommended, provider, onProviderChange])

  function chooseManualModel(model: string) {
    setAutoSwitch(false)
    onProviderChange({ ...provider, model })
  }

  function useBestMatch() {
    setAutoSwitch(true)
    if (recommended && provider.model !== recommended) {
      onProviderChange({ ...provider, model: recommended })
    }
  }

  const wrapperStyle = {
    minWidth: 360,
    maxWidth: 470,
    padding: 14,
    border: '1px solid var(--border, #2c3947)',
    borderRadius: 12,
    background: 'rgba(255,255,255,.025)',
  } as const
  const rowStyle = { display: 'flex', gap: 8, alignItems: 'center' } as const
  const labelStyle = { display: 'block', marginBottom: 6, color: 'var(--muted, #9eabb8)', fontSize: 12 } as const
  const hintStyle = { margin: '6px 0 0', color: 'var(--muted, #96a4b1)', fontSize: 11, lineHeight: 1.4 } as const
  const badgeStyle = {
    display: 'inline-block',
    marginTop: 7,
    padding: '3px 7px',
    border: '1px solid rgba(103,184,143,.35)',
    borderRadius: 999,
    color: '#9dd6b8',
    fontSize: 10,
  } as const

  return (
    <div className="ai-studio-model" style={wrapperStyle}>
      <label style={labelStyle}>Writing type</label>
      <select value={purpose} onChange={(event) => setPurpose(event.target.value as WritingPurpose)} disabled={busy}>
        {(Object.keys(PURPOSES) as WritingPurpose[]).map((item) => (
          <option key={item} value={item}>{PURPOSES[item].label}</option>
        ))}
      </select>
      <p style={hintStyle}>{PURPOSES[purpose].short}</p>
      <p style={hintStyle}>{PURPOSES[purpose].why}</p>

      <div style={{ ...rowStyle, marginTop: 11, justifyContent: 'space-between' }}>
        <label style={{ ...labelStyle, marginBottom: 0 }}>
          <input
            type="checkbox"
            checked={autoSwitch}
            onChange={(event) => setAutoSwitch(event.target.checked)}
            disabled={busy}
            style={{ width: 'auto', minHeight: 0, marginRight: 6 }}
          />
          Auto-switch to best installed model
        </label>
        <button type="button" onClick={useBestMatch} disabled={busy || !recommended}>Best match</button>
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
          <strong style={{ display: 'block', fontSize: 12 }}>Recommended for {PURPOSES[resolvedPurpose].label}: {recommended}</strong>
          <span style={badgeStyle}>{fitLabel(recommended, resolvedPurpose)}</span>
          <p style={hintStyle}>{describeModel(recommended).bestFor}</p>
        </div>
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
          <summary style={{ cursor: 'pointer' }}>When should I use each installed model?</summary>
          <div style={{ display: 'grid', gap: 9, marginTop: 9 }}>
            {models.map((model) => {
              const guide = describeModel(model)
              return (
                <div key={model} style={{ paddingTop: 8, borderTop: '1px solid rgba(255,255,255,.06)' }}>
                  <strong style={{ display: 'block', color: 'var(--text, #e6edf4)' }}>{model}</strong>
                  <span>{guide.label} · {guide.bestFor}</span>
                  <div style={{ marginTop: 3 }}>{guide.why}</div>
                </div>
              )
            })}
          </div>
        </details>
      )}

      {!models.length && <p style={hintStyle}>No installed models were returned by the configured provider. Refresh after installing or starting a local model.</p>}
    </div>
  )
}
