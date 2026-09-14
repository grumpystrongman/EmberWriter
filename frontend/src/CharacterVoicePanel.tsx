import { useEffect, useMemo, useState } from 'react'

import type { ProviderConfig } from './workspace-types'
import './character-voice.css'

export type CharacterVoiceCard = {
  character: string
  speech_rhythm: string
  vocabulary: string
  humor: string
  emotional_expression: string
  subtext: string
  physical_mannerisms: string
  intimacy_expression: string
  signature_phrases: string[]
  avoidances: string[]
  author_notes: string
}

type VoiceState = { schema_version: number; voices: CharacterVoiceCard[] }

type Props = {
  apiBase: string
  slug: string
  character: string
  disabled?: boolean
}

const emptyCard = (character: string): CharacterVoiceCard => ({
  character,
  speech_rhythm: '',
  vocabulary: '',
  humor: '',
  emotional_expression: '',
  subtext: '',
  physical_mannerisms: '',
  intimacy_expression: '',
  signature_phrases: [],
  avoidances: [],
  author_notes: '',
})

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

function provider(): ProviderConfig | null {
  try {
    const parsed = JSON.parse(localStorage.getItem('emberwriter.provider') || 'null') as ProviderConfig | null
    return parsed?.model?.trim() && parsed.base_url?.trim() ? parsed : null
  } catch {
    return null
  }
}

function splitList(value: string) {
  return value.split(/\n|;/).map((item) => item.trim()).filter(Boolean)
}

export default function CharacterVoicePanel({ apiBase, slug, character, disabled = false }: Props) {
  const [state, setState] = useState<VoiceState>({ schema_version: 1, voices: [] })
  const [draft, setDraft] = useState<CharacterVoiceCard>(() => emptyCard(character))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(true)

  const existing = useMemo(
    () => state.voices.find((item) => item.character.toLowerCase() === character.toLowerCase()) || null,
    [state.voices, character],
  )

  useEffect(() => {
    void refresh()
  }, [apiBase, slug])

  useEffect(() => {
    setDraft(existing ? { ...existing } : emptyCard(character))
    setSaved(true)
    setError('')
  }, [character, existing])

  async function refresh() {
    try {
      setState(await request<VoiceState>(`${apiBase}/projects/${slug}/character-voices`))
    } catch (cause) {
      setError((cause as Error).message)
    }
  }

  function patch<K extends keyof CharacterVoiceCard>(key: K, value: CharacterVoiceCard[K]) {
    setDraft((current) => ({ ...current, [key]: value }))
    setSaved(false)
  }

  async function save() {
    if (!character || busy) return
    setBusy(true)
    setError('')
    try {
      setState(await request<VoiceState>(`${apiBase}/projects/${slug}/character-voices/${encodeURIComponent(character)}`, {
        method: 'PUT',
        body: JSON.stringify({ ...draft, character }),
      }))
      setSaved(true)
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function infer() {
    const activeProvider = provider()
    if (!activeProvider) {
      setError('Choose a local/text model in Ember before inferring a character voice.')
      return
    }
    setBusy(true)
    setError('')
    try {
      const card = await request<CharacterVoiceCard>(
        `${apiBase}/projects/${slug}/character-voices/${encodeURIComponent(character)}/infer`,
        {
          method: 'POST',
          body: JSON.stringify({ provider: activeProvider, author_notes: draft.author_notes }),
        },
      )
      setDraft(card)
      setState((current) => ({
        ...current,
        voices: [...current.voices.filter((item) => item.character.toLowerCase() !== character.toLowerCase()), card],
      }))
      setSaved(true)
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="character-voice-card">
      <div className="character-voice-head">
        <div>
          <small>CHARACTER PERFORMANCE</small>
          <h2>Voice Card</h2>
          <p>Author-owned rules for how {character} sounds, masks emotion, uses subtext, and behaves under pressure. Generation and Scene Architect use this automatically.</p>
        </div>
        <div className="character-voice-actions">
          <button type="button" onClick={() => void infer()} disabled={disabled || busy}>{busy ? 'Learning…' : 'Infer from manuscript'}</button>
          <button type="button" className="primary" onClick={() => void save()} disabled={disabled || busy || saved}>{saved ? 'Saved' : 'Save voice card'}</button>
        </div>
      </div>

      <div className="character-voice-grid">
        <label>Speech rhythm<textarea rows={4} value={draft.speech_rhythm} onChange={(event) => patch('speech_rhythm', event.target.value)} placeholder="Long winding sentences when nervous; clipped answers when angry…" /></label>
        <label>Vocabulary / register<textarea rows={4} value={draft.vocabulary} onChange={(event) => patch('vocabulary', event.target.value)} placeholder="Formal, blunt, technical, regional, profane, lyrical…" /></label>
        <label>Humor<textarea rows={4} value={draft.humor} onChange={(event) => patch('humor', event.target.value)} placeholder="Dry deflection, teasing, no humor under stress…" /></label>
        <label>Emotional expression<textarea rows={4} value={draft.emotional_expression} onChange={(event) => patch('emotional_expression', event.target.value)} placeholder="What they admit, hide, externalize, or convert into action…" /></label>
        <label>Subtext<textarea rows={4} value={draft.subtext} onChange={(event) => patch('subtext', event.target.value)} placeholder="How they imply what they will not say directly…" /></label>
        <label>Physical mannerisms<textarea rows={4} value={draft.physical_mannerisms} onChange={(event) => patch('physical_mannerisms', event.target.value)} placeholder="Recurring embodied habits that reveal state without becoming tics…" /></label>
        <label className="wide">Romance / intimacy expression<textarea rows={4} value={draft.intimacy_expression} onChange={(event) => patch('intimacy_expression', event.target.value)} placeholder="How attraction, trust, vulnerability, affection, control, hesitation, humor, or surrender change this character's behavior when relevant…" /></label>
        <label>Signature language cues<textarea rows={4} value={draft.signature_phrases.join('\n')} onChange={(event) => patch('signature_phrases', splitList(event.target.value))} placeholder="One cue per line. Use sparingly." /></label>
        <label>Avoidances<textarea rows={4} value={draft.avoidances.join('\n')} onChange={(event) => patch('avoidances', splitList(event.target.value))} placeholder="Things this character would never say/do; generic habits to avoid…" /></label>
        <label className="wide">Author notes<textarea rows={4} value={draft.author_notes} onChange={(event) => patch('author_notes', event.target.value)} placeholder="Your overrides always outrank inferred tendencies." /></label>
      </div>
      {error && <div className="center-error">{error}</div>}
    </section>
  )
}
