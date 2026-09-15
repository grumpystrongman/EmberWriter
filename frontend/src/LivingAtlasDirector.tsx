import type { AtlasAdvice } from './story-atlas-types'

type Props = {
  prompt: string
  advice: AtlasAdvice | null
  busy: boolean
  onPrompt: (value: string) => void
  onAsk: () => void
}

export default function LivingAtlasDirector({ prompt, advice, busy, onPrompt, onAsk }: Props) {
  return <section className="living-control-card living-director-panel">
    <div className="living-card-title"><b>Spatial Story Director</b><span>Suggestions never become canon automatically</span></div>
    <textarea value={prompt} onChange={(event) => onPrompt(event.target.value)} placeholder="What does the geography need to solve?" />
    <div className="living-prompt-chips">
      <button type="button" onClick={() => onPrompt('Find the strongest believable ambush point on this route and explain what the geography contributes.')}>Ambush</button>
      <button type="button" onClick={() => onPrompt('Find a slower route that creates a believable private conversation and relationship turning point.')}>Relationship beat</button>
      <button type="button" onClick={() => onPrompt('Audit this journey for spatial, travel-time, and chapter-state continuity problems.')}>Continuity audit</button>
    </div>
    <button type="button" className="primary" onClick={onAsk} disabled={busy || !prompt.trim()}>✦ Ask Atlas</button>
    {advice && <div className="living-advice">
      <p>{advice.summary}</p>
      {advice.continuity_warnings.map((warning) => <div className="living-warning" key={warning}>⚠ {warning}</div>)}
      {advice.ideas.map((idea) => <article key={`${idea.title}-${idea.rationale}`}><b>{idea.title}</b><p>{idea.rationale}</p><small>{idea.story_effect}</small></article>)}
    </div>}
  </section>
}
