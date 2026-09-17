export type ModelPurposeKey = 'mature' | 'general' | 'planning'

export type ModelPurpose = {
  key: ModelPurposeKey
  title: string
  short: string
  why: string
  bestFor: string
  avoidFor: string
  candidates: string[]
}

export const MODEL_PURPOSES: ModelPurpose[] = [
  {
    key: 'mature',
    title: 'Mature / relationship fiction',
    short: 'Rocinante 12B · story/RP specialist',
    why: 'Use a model actually tuned for storytelling and roleplay rather than a general instruct model that was only decensored.',
    bestFor: 'Romance, harem, kink, adult relationship scenes, character chemistry, intimate dialogue.',
    avoidFor: 'Continuity audits and analytical planning.',
    candidates: [
      'HammerAI/rocinante-v1.1:12b-q4_K_M',
      'HammerAI/rocinante-v1.1',
      'RoseRudolph/rudy-nemo-12b-v1:12b',
      'fluffy/l3-8b-stheno-v3.2:q4_K_M',
      'fluffy/l3-8b-stheno-v3.2',
    ],
  },
  {
    key: 'general',
    title: 'General fiction',
    short: 'Ministral 3 · strong all-purpose prose',
    why: 'A strong instruction-following model with a large context window is a better default for normal chapters than an RP specialist.',
    bestFor: 'Action, horror, fantasy, dialogue, worldbuilding, rewrites, ordinary chapters.',
    avoidFor: 'Specialized adult RP when Rocinante is installed.',
    candidates: ['ministral-3:14b', 'ministral-3:8b', 'ministral-3'],
  },
  {
    key: 'planning',
    title: 'Planning / story logic',
    short: 'Qwen3 8B · reasoning and story-room work',
    why: 'Use the reasoning-oriented model for outlines and continuity instead of asking the final-prose model to solve every job.',
    bestFor: 'Brainstorming, outlines, critique, continuity, alternatives, plot problem-solving.',
    avoidFor: 'Final voice-sensitive or intimate prose.',
    candidates: ['qwen3:8b', 'qwen3:14b', 'qwen3'],
  },
]

export function purposeForTask(mode: 'scene' | 'brainstorm' | 'creative', heat: string, prompt: string): ModelPurposeKey {
  if (mode !== 'scene') return 'planning'
  const explicit = /\b(?:sex|sexual|erotic|kink|harem|intimat|spicy|fuck|nsfw)\b/i.test(prompt)
  if (explicit || heat === 'scorching' || heat === 'inferno') return 'mature'
  return 'general'
}

export function installedModelForPurpose(key: ModelPurposeKey, models: string[]): string | null {
  const profile = MODEL_PURPOSES.find((item) => item.key === key)
  if (!profile) return null
  const byFolded = new Map(models.map((model) => [model.toLocaleLowerCase(), model]))
  for (const candidate of profile.candidates) {
    const exact = byFolded.get(candidate.toLocaleLowerCase())
    if (exact) return exact
  }
  for (const model of models) {
    const lowered = model.toLocaleLowerCase()
    if (key === 'mature' && (lowered.includes('rocinante') || lowered.includes('stheno') || lowered.includes('rudy-nemo'))) return model
    if (key === 'general' && lowered.includes('ministral-3')) return model
    if (key === 'planning' && lowered.includes('qwen3')) return model
  }
  return null
}
