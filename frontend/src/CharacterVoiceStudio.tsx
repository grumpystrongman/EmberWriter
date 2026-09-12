import { useEffect, useState } from 'react'

import CharacterVoicePanel from './CharacterVoicePanel'
import type { StoryIntelligence } from './StoryIntelligencePanel'

type Props = { apiBase: string; slug: string }

export default function CharacterVoiceStudio({ apiBase, slug }: Props) {
  const [names, setNames] = useState<string[]>([])
  const [selected, setSelected] = useState('')

  useEffect(() => {
    let cancelled = false
    void fetch(`${apiBase}/projects/${slug}/story-intelligence`)
      .then(async (response) => response.ok ? response.json() as Promise<StoryIntelligence> : { characters: [], relationships: [] })
      .then((story) => {
        if (cancelled) return
        const next = story.characters.map((item) => item.name).sort((a, b) => a.localeCompare(b))
        setNames(next)
        setSelected((current) => current && next.includes(current) ? current : next[0] || '')
      })
    return () => { cancelled = true }
  }, [apiBase, slug])

  if (!names.length) return null

  return (
    <section className="character-voice-studio-shell">
      <div className="character-voice-studio-select">
        <div><small>VOICE MATRIX</small><strong>Character performance profiles</strong></div>
        <select value={selected} onChange={(event) => setSelected(event.target.value)} aria-label="Character voice card">
          {names.map((name) => <option key={name}>{name}</option>)}
        </select>
      </div>
      {selected && <CharacterVoicePanel apiBase={apiBase} slug={slug} character={selected} />}
    </section>
  )
}
