import { useState } from 'react'
import type { AtlasLocation, StoryAtlas, VisualAsset } from './story-atlas-types'
import type { AtlasMapScale, AtlasPrefs, AtlasScale } from './living-atlas-helpers'
import type { AtlasVisualStyle, AtlasWorldType } from './LivingAtlasCanvas'
import { childScaleFor, inferScale, SCALE_OPTIONS, titleCase } from './living-atlas-helpers'

type Props = {
  atlas: StoryAtlas
  scopedLocations: AtlasLocation[]
  allVisibleLocations: AtlasLocation[]
  selectedLocationId: string
  scopeId: string
  scopeLocation: AtlasLocation | null
  prefs: AtlasPrefs
  visuals: VisualAsset[]
  showInferred: boolean
  respectKnowledge: boolean
  newPlaceName: string
  parentIdFor: (location: AtlasLocation) => string
  onClose: () => void
  onPrefs: (patch: Partial<AtlasPrefs>) => void
  onMapArtwork: (assetId: string) => void
  onShowInferred: (value: boolean) => void
  onRespectKnowledge: (value: boolean) => void
  onNewPlaceName: (value: string) => void
  onAddPlace: (scale: AtlasScale) => void
  onSelectLocation: (id: string) => void
  onExplore: (id: string) => void
  onUp: () => void
}

export default function LivingAtlasLeftDrawer({
  atlas,
  scopedLocations,
  allVisibleLocations,
  selectedLocationId,
  scopeId,
  scopeLocation,
  prefs,
  visuals,
  showInferred,
  respectKnowledge,
  newPlaceName,
  parentIdFor,
  onClose,
  onPrefs,
  onMapArtwork,
  onShowInferred,
  onRespectKnowledge,
  onNewPlaceName,
  onAddPlace,
  onSelectLocation,
  onExplore,
  onUp,
}: Props) {
  const [newPlaceScale, setNewPlaceScale] = useState<'auto' | AtlasScale>('auto')
  const suggestedScale = scopeLocation ? childScaleFor(inferScale(scopeLocation)) : 'world'
  const resolvedNewPlaceScale = newPlaceScale === 'auto' ? suggestedScale : newPlaceScale
  const addPlace = () => onAddPlace(resolvedNewPlaceScale)

  return <aside className="living-atlas-drawer living-left-drawer">
    <div className="living-drawer-heading">
      <div><span>Atlas library</span><b>{scopedLocations.length} visible · {atlas.locations.length} total</b></div>
      <button type="button" onClick={onClose}>×</button>
    </div>
    <div className="living-drawer-scroll">
      <section className="living-control-card">
        <label>World type
          <select value={prefs.worldType} onChange={(event) => onPrefs({ worldType: event.target.value as AtlasWorldType })}>
            <option value="fantasy">Fantasy realm</option>
            <option value="modern">Modern Earth</option>
            <option value="historical">Historical</option>
            <option value="space">Outer space</option>
            <option value="dimensional">Dimensions / planes</option>
            <option value="hybrid">Hybrid</option>
          </select>
        </label>
        <label>Map level
          <select value={prefs.mapScale} onChange={(event) => onPrefs({ mapScale: event.target.value as AtlasMapScale })}>
            <option value="auto">Auto from hierarchy</option>
            {SCALE_OPTIONS.map((scale) => <option key={scale} value={scale}>{titleCase(scale)}</option>)}
          </select>
        </label>
        <label>Cartography
          <select value={prefs.visualStyle} onChange={(event) => onPrefs({ visualStyle: event.target.value as AtlasVisualStyle })}>
            <option value="illustrated">Illustrated atlas</option>
            <option value="parchment">Parchment</option>
            <option value="manuscript">Ink manuscript</option>
            <option value="star-chart">Star chart</option>
            <option value="schematic">Clean schematic</option>
          </select>
        </label>
        <label>Map artwork
          <select value={atlas.map.background_asset_id || ''} onChange={(event) => onMapArtwork(event.target.value)}>
            <option value="">Procedural literary map</option>
            {visuals.map((asset) => <option key={asset.asset_id} value={asset.asset_id}>{asset.title} · {asset.canon_status}</option>)}
          </select>
        </label>
        <div className="living-toggle-grid">
          <label><input type="checkbox" checked={prefs.showTerrain} onChange={(event) => onPrefs({ showTerrain: event.target.checked })} /> Terrain</label>
          <label><input type="checkbox" checked={prefs.showRegions} onChange={(event) => onPrefs({ showRegions: event.target.checked })} /> Regions</label>
          <label><input type="checkbox" checked={prefs.showLabels} onChange={(event) => onPrefs({ showLabels: event.target.checked })} /> Labels</label>
          <label><input type="checkbox" checked={showInferred} onChange={(event) => onShowInferred(event.target.checked)} /> Inferred / suggested</label>
          <label><input type="checkbox" checked={respectKnowledge} onChange={(event) => onRespectKnowledge(event.target.checked)} /> POV knowledge</label>
        </div>
      </section>

      <section className="living-control-card">
        <div className="living-card-title"><b>{scopeLocation ? `Inside ${scopeLocation.name}` : 'Places'}</b><span>Build at any granularity, then drill into containers</span></div>
        {scopeId && <button type="button" className="living-up-button" onClick={onUp}>← Up one level</button>}
        <div className="living-add-row">
          <input value={newPlaceName} onChange={(event) => onNewPlaceName(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') addPlace() }} placeholder="Add place or area…" />
          <button type="button" onClick={addPlace}>＋</button>
        </div>
        <label>New item level
          <select value={newPlaceScale} onChange={(event) => setNewPlaceScale(event.target.value as 'auto' | AtlasScale)}>
            <option value="auto">Auto · {titleCase(suggestedScale)}</option>
            {SCALE_OPTIONS.map((scale) => <option key={scale} value={scale}>{titleCase(scale)}</option>)}
          </select>
        </label>
        <small>Author-created items become canon immediately. You can change their parent, level, artwork, coordinates, and canon state in Details.</small>
        <div className="living-place-list">
          {scopedLocations.map((location) => {
            const children = allVisibleLocations.filter((item) => parentIdFor(item) === location.id).length
            const origin = location.tags.find((tag) => tag.startsWith('origin:'))?.slice(7) || (location.source_paths.length ? 'manuscript' : location.canon_status)
            return <button type="button" key={location.id} className={selectedLocationId === location.id ? 'active' : ''} onClick={() => onSelectLocation(location.id)}>
              <i className={location.canon_status} />
              <span><b>{location.name}</b><small>{titleCase(inferScale(location))} · {location.kind}{children ? ` · ${children} inside` : ''} · {titleCase(origin)}</small></span>
              {children > 0 && <em onClick={(event) => { event.stopPropagation(); onExplore(location.id) }}>›</em>}
            </button>
          })}
          {!scopedLocations.length && <p className="living-list-empty">Nothing is mapped at this level yet.</p>}
        </div>
      </section>
    </div>
  </aside>
}
