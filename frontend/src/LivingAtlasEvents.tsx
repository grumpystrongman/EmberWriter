import type { AtlasEventAction, StoryAtlas } from './story-atlas-types'
import { titleCase } from './living-atlas-helpers'

type Option = { id: string; name: string }

type Props = {
  atlas: StoryAtlas
  action: AtlasEventAction
  target: string
  chapter: string
  value: string
  summary: string
  options: Option[]
  onAction: (value: AtlasEventAction) => void
  onTarget: (value: string) => void
  onChapter: (value: string) => void
  onValue: (value: string) => void
  onSummary: (value: string) => void
  onAdd: () => void
  onDelete: (id: string) => void
}

export default function LivingAtlasEvents({
  atlas,
  action,
  target,
  chapter,
  value,
  summary,
  options,
  onAction,
  onTarget,
  onChapter,
  onValue,
  onSummary,
  onAdd,
  onDelete,
}: Props) {
  return <section className="living-control-card living-events-panel">
    <div className="living-card-title"><b>World history</b><span>Scrub the chapter slider to watch geography change</span></div>
    <div className="living-two">
      <select value={action} onChange={(event) => onAction(event.target.value as AtlasEventAction)}>
        <option value="connection_close">Close route</option>
        <option value="connection_open">Open route</option>
        <option value="location_reveal">Reveal place</option>
        <option value="location_control">Change control</option>
        <option value="note">Story note</option>
      </select>
      <input type="number" min="0" value={chapter} onChange={(event) => onChapter(event.target.value)} placeholder="Chapter" />
    </div>
    <select value={target} onChange={(event) => onTarget(event.target.value)}><option value="">Target…</option>{options.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select>
    {(action === 'location_reveal' || action === 'location_control' || action === 'note') && <input value={value} onChange={(event) => onValue(event.target.value)} placeholder={action === 'location_reveal' ? 'Characters, comma separated' : action === 'location_control' ? 'Faction / controller' : 'Value'} />}
    <input value={summary} onChange={(event) => onSummary(event.target.value)} placeholder="What changes in the story?" />
    <button type="button" className="primary" onClick={onAdd} disabled={!target}>Add world-state event</button>
    <div className="living-event-list">
      {[...atlas.events].sort((a, b) => b.chapter - a.chapter).map((event) => <article key={event.id}>
        <b>Ch {event.chapter}</b><span>{titleCase(event.action.replaceAll('_', '-'))}</span><p>{event.summary || event.value || event.target_id}</p><button type="button" onClick={() => onDelete(event.id)}>×</button>
      </article>)}
      {!atlas.events.length && <p className="living-panel-hint">Add route closures, reveals, control changes and other chapter-aware geography. These become part of continuity checking.</p>}
    </div>
  </section>
}
