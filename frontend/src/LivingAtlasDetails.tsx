import type { AtlasConnection, AtlasLocation, VisualAsset } from './story-atlas-types'
import { asList, clamp, inferScale, SCALE_OPTIONS, tagValue, titleCase, withTag } from './living-atlas-helpers'

type Props = {
  apiBase: string
  projectSlug: string
  selectedLocation: AtlasLocation | null
  selectedConnection: AtlasConnection | null
  locations: AtlasLocation[]
  visibleLocations: AtlasLocation[]
  visuals: VisualAsset[]
  parentIdFor: (location: AtlasLocation) => string
  onUpdateLocation: (id: string, patch: Partial<AtlasLocation>) => void
  onUpdateConnection: (id: string, patch: Partial<AtlasConnection>) => void
  onDeleteLocation: () => void
  onDeleteConnection: () => void
  onExplore: (id: string) => void
  onOpenSource: (path: string) => void
}

export default function LivingAtlasDetails({
  apiBase,
  projectSlug,
  selectedLocation,
  selectedConnection,
  locations,
  visibleLocations,
  visuals,
  parentIdFor,
  onUpdateLocation,
  onUpdateConnection,
  onDeleteLocation,
  onDeleteConnection,
  onExplore,
  onOpenSource,
}: Props) {
  if (selectedLocation) {
    const children = visibleLocations.filter((item) => parentIdFor(item) === selectedLocation.id)
    const descendantIds = new Set<string>()
    let frontier = [selectedLocation.id]
    while (frontier.length) {
      const next: string[] = []
      for (const parentId of frontier) {
        for (const item of locations) {
          if (parentIdFor(item) === parentId && !descendantIds.has(item.id)) {
            descendantIds.add(item.id)
            next.push(item.id)
          }
        }
      }
      frontier = next
    }
    const origin = tagValue(selectedLocation, 'origin:') || (selectedLocation.source_paths.length ? 'manuscript' : selectedLocation.canon_status)
    const basis = tagValue(selectedLocation, 'basis:')
    return <section className="living-control-card living-inspector">
      <div className="living-card-title"><b>{selectedLocation.name}</b><button type="button" className="danger" onClick={onDeleteLocation}>Delete</button></div>
      {selectedLocation.image_asset_id && <img src={`${apiBase}/projects/${projectSlug}/visual-assets/${selectedLocation.image_asset_id}`} alt={`Reference for ${selectedLocation.name}`} />}
      <div className="living-source-summary">
        <b>{titleCase(origin)}</b>
        <span>{Math.round(selectedLocation.confidence * 100)}% confidence · {selectedLocation.source_paths.length ? `${selectedLocation.source_paths.length} manuscript source${selectedLocation.source_paths.length === 1 ? '' : 's'}` : 'no direct manuscript citation'}</span>
        {basis && <small>Why Ember inferred it: {basis}</small>}
      </div>
      <label>Name<input value={selectedLocation.name} onChange={(event) => onUpdateLocation(selectedLocation.id, { name: event.target.value })} /></label>
      <div className="living-two">
        <label>Kind<input value={selectedLocation.kind} onChange={(event) => onUpdateLocation(selectedLocation.id, { kind: event.target.value })} /></label>
        <label>Level<select value={inferScale(selectedLocation)} onChange={(event) => onUpdateLocation(selectedLocation.id, { tags: withTag(selectedLocation, 'scale:', event.target.value) })}>{SCALE_OPTIONS.map((scale) => <option key={scale} value={scale}>{titleCase(scale)}</option>)}</select></label>
      </div>
      <label>Inside<select value={parentIdFor(selectedLocation)} onChange={(event) => onUpdateLocation(selectedLocation.id, {
        region: event.target.value ? locations.find((item) => item.id === event.target.value)?.name || selectedLocation.region : '',
        tags: withTag(selectedLocation, 'parent:', event.target.value),
      })}><option value="">Top level</option>{locations.filter((item) => item.id !== selectedLocation.id && !descendantIds.has(item.id)).map((item) => <option key={item.id} value={item.id}>{item.name} · {titleCase(inferScale(item))}</option>)}</select></label>
      <textarea value={selectedLocation.summary} onChange={(event) => onUpdateLocation(selectedLocation.id, { summary: event.target.value })} placeholder="Atmosphere, geography, constraints, what the reader should understand…" />
      <label>Terrain<input value={selectedLocation.terrain.join(', ')} onChange={(event) => onUpdateLocation(selectedLocation.id, { terrain: asList(event.target.value) })} placeholder="forest, river, mountains…" /></label>
      <div className="living-two">
        <label>Canon<select value={selectedLocation.canon_status} onChange={(event) => onUpdateLocation(selectedLocation.id, { canon_status: event.target.value as AtlasLocation['canon_status'] })}><option value="canon">Canon / accepted</option><option value="inferred">Inferred</option><option value="suggested">Suggested</option></select></label>
        <label>Position<select value={selectedLocation.position_status} onChange={(event) => onUpdateLocation(selectedLocation.id, { position_status: event.target.value as AtlasLocation['position_status'] })}><option value="canon">Canon / fixed</option><option value="inferred">Inferred</option><option value="suggested">Suggested</option></select></label>
      </div>
      <label>Confidence<input type="range" min="0" max="1" step=".05" value={selectedLocation.confidence} onChange={(event) => onUpdateLocation(selectedLocation.id, { confidence: clamp(Number(event.target.value), 0, 1) })} /></label>
      <label>Known by<input value={selectedLocation.known_by.join(', ')} onChange={(event) => onUpdateLocation(selectedLocation.id, { known_by: asList(event.target.value) })} placeholder="Blank = everyone" /></label>
      <label>Reference image<select value={selectedLocation.image_asset_id || ''} onChange={(event) => onUpdateLocation(selectedLocation.id, { image_asset_id: event.target.value || null })}><option value="">None</option>{visuals.map((asset) => <option key={asset.asset_id} value={asset.asset_id}>{asset.title}</option>)}</select></label>
      <div className="living-two living-coordinate-row"><label>X<input type="number" value={Math.round(selectedLocation.x)} onChange={(event) => onUpdateLocation(selectedLocation.id, { x: clamp(Number(event.target.value), -100000, 100000) })} /></label><label>Y<input type="number" value={Math.round(selectedLocation.y)} onChange={(event) => onUpdateLocation(selectedLocation.id, { y: clamp(Number(event.target.value), -100000, 100000) })} /></label></div>
      {!!children.length && <button type="button" className="primary" onClick={() => onExplore(selectedLocation.id)}>Explore inside {selectedLocation.name} →</button>}
      {!!selectedLocation.source_paths.length && <div className="living-sources"><b>Canon sources</b>{selectedLocation.source_paths.map((path) => <button type="button" key={path} onClick={() => onOpenSource(path)}>{path}</button>)}</div>}
    </section>
  }

  if (selectedConnection) {
    return <section className="living-control-card living-inspector">
      <div className="living-card-title"><b>{selectedConnection.name}</b><button type="button" className="danger" onClick={onDeleteConnection}>Delete</button></div>
      <label>Name<input value={selectedConnection.name} onChange={(event) => onUpdateConnection(selectedConnection.id, { name: event.target.value })} /></label>
      <div className="living-two">
        <label>Distance<input type="number" min=".001" step=".1" value={selectedConnection.distance} onChange={(event) => onUpdateConnection(selectedConnection.id, { distance: Math.max(.001, Number(event.target.value) || .001) })} /></label>
        <label>Terrain ×<input type="number" min=".1" max="20" step=".1" value={selectedConnection.terrain_multiplier} onChange={(event) => onUpdateConnection(selectedConnection.id, { terrain_multiplier: clamp(Number(event.target.value), .1, 20) })} /></label>
      </div>
      {(['risk', 'drama', 'lore', 'relationship'] as const).map((key) => <label className="living-score" key={key}>{titleCase(key)}<input type="range" min="1" max="5" value={selectedConnection[key]} onChange={(event) => onUpdateConnection(selectedConnection.id, { [key]: Number(event.target.value) })} /><b>{selectedConnection[key]}</b></label>)}
      <div className="living-two"><label>Starts chapter<input type="number" min="0" value={selectedConnection.active_from_chapter} onChange={(event) => onUpdateConnection(selectedConnection.id, { active_from_chapter: Math.max(0, Number(event.target.value) || 0) })} /></label><label>Ends chapter<input type="number" min="0" value={selectedConnection.active_until_chapter ?? ''} onChange={(event) => onUpdateConnection(selectedConnection.id, { active_until_chapter: event.target.value ? Math.max(0, Number(event.target.value)) : null })} placeholder="Open" /></label></div>
      <label className="living-inline-check"><input type="checkbox" checked={selectedConnection.bidirectional} onChange={(event) => onUpdateConnection(selectedConnection.id, { bidirectional: event.target.checked })} /> Bidirectional</label>
      <textarea value={selectedConnection.notes} onChange={(event) => onUpdateConnection(selectedConnection.id, { notes: event.target.value })} placeholder="Road conditions, hazards, portal rules, story opportunities…" />
    </section>
  }

  return <section className="living-control-card living-no-selection"><b>Select something on the atlas.</b><p>Places reveal hierarchy, canon, terrain and source material. Routes expose travel constraints and story opportunities.</p></section>
}
