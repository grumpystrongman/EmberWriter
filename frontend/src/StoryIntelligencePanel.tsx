import { useMemo, useState } from 'react'

export type CharacterFact = {
  kind: string
  predicate: string
  object: string
  source_path: string
  confidence: number
  importance: number
  chapter_order: number
  metadata: Record<string, unknown>
}

export type CharacterProfile = {
  name: string
  dossier_path?: string | null
  state: CharacterFact[]
  knowledge: CharacterFact[]
  relationships: CharacterFact[]
  other_facts: CharacterFact[]
  latest_chapter: number
}

export type RelationshipEdge = {
  source: string
  target: string
  state: string
  detail: string
  source_path: string
  chapter_order: number
  confidence: number
  importance: number
}

export type StoryIntelligence = {
  characters: CharacterProfile[]
  relationships: RelationshipEdge[]
}

type Props = {
  intelligence: StoryIntelligence
  onRefresh: () => void
  onOpenSource: (path: string) => void
}

function FactList({ title, facts, onOpenSource }: {
  title: string
  facts: CharacterFact[]
  onOpenSource: (path: string) => void
}) {
  if (!facts.length) return null
  return (
    <div className="character-fact-group">
      <h4>{title}</h4>
      {facts.slice(0, 8).map((fact, index) => (
        <button
          className="character-fact"
          key={`${fact.source_path}-${fact.predicate}-${index}`}
          onClick={() => onOpenSource(fact.source_path)}
        >
          <span>{fact.predicate} <strong>{fact.object}</strong></span>
          <small>ch {fact.chapter_order || '?'} · {Math.round(fact.confidence * 100)}%</small>
        </button>
      ))}
    </div>
  )
}

export default function StoryIntelligencePanel({ intelligence, onRefresh, onOpenSource }: Props) {
  const [selected, setSelected] = useState('')
  const selectedProfile = useMemo(
    () => intelligence.characters.find((character) => character.name === selected) ?? intelligence.characters[0],
    [intelligence.characters, selected],
  )

  return (
    <details className="story-intelligence-panel">
      <summary>
        <span>Characters & relationships</span>
        <small>{intelligence.characters.length} people · {intelligence.relationships.length} links</small>
      </summary>

      <div className="story-toolbar">
        <button className="quiet" onClick={onRefresh}>Refresh story state</button>
      </div>

      {intelligence.characters.length === 0 ? (
        <div className="memory-empty">Build Story Memory to derive character state and relationships.</div>
      ) : (
        <>
          <div className="character-chip-row">
            {intelligence.characters.slice(0, 20).map((character) => (
              <button
                key={character.name}
                className={selectedProfile?.name === character.name ? 'active' : ''}
                onClick={() => setSelected(character.name)}
              >
                {character.name}
              </button>
            ))}
          </div>

          {selectedProfile && (
            <div className="character-dossier-card">
              <div className="character-card-head">
                <div>
                  <strong>{selectedProfile.name}</strong>
                  <small>latest story state: ch {selectedProfile.latest_chapter || '?'}</small>
                </div>
                {selectedProfile.dossier_path && (
                  <button className="quiet" onClick={() => onOpenSource(selectedProfile.dossier_path!)}>Open dossier</button>
                )}
              </div>
              <FactList title="Current state" facts={selectedProfile.state} onOpenSource={onOpenSource} />
              <FactList title="What they know" facts={selectedProfile.knowledge} onOpenSource={onOpenSource} />
              <FactList title="Relationship history" facts={selectedProfile.relationships} onOpenSource={onOpenSource} />
              <FactList title="Other continuity" facts={selectedProfile.other_facts} onOpenSource={onOpenSource} />
            </div>
          )}
        </>
      )}

      {intelligence.relationships.length > 0 && (
        <div className="relationship-list">
          <h4>Recent relationship movement</h4>
          {intelligence.relationships.slice(0, 18).map((edge, index) => (
            <button
              className="relationship-edge"
              key={`${edge.source_path}-${edge.source}-${edge.target}-${index}`}
              onClick={() => onOpenSource(edge.source_path)}
            >
              <span><strong>{edge.source}</strong> → <strong>{edge.target}</strong></span>
              <span>{edge.state}{edge.detail ? ` · ${edge.detail}` : ''}</span>
              <small>ch {edge.chapter_order || '?'} · {'◆'.repeat(Math.min(5, edge.importance))}</small>
            </button>
          ))}
        </div>
      )}
    </details>
  )
}
