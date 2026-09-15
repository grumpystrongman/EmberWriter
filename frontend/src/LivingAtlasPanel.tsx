import { useEffect } from 'react'
import LivingAtlasCanvas from './LivingAtlasCanvas'
import LivingAtlasLeftDrawer from './LivingAtlasLeftDrawer'
import LivingAtlasRightDrawer from './LivingAtlasRightDrawer'
import { baseView, inferCanvasScale, titleCase } from './living-atlas-helpers'
import { useLivingAtlasCore } from './useLivingAtlasCore'
import { useLivingAtlasTools } from './useLivingAtlasTools'
import type { MemoryFact } from './MemoryPanel'
import type { WorkspaceProject } from './workspace-types'
import './living-atlas.css'
import './literary-cartography.css'
import './living-atlas-tools.css'

type Props = {
  apiBase: string
  project: WorkspaceProject
  facts: MemoryFact[]
  onOpenSource: (path: string, anchor?: string) => void
}

export default function LivingAtlasPanel({ apiBase, project, facts, onOpenSource }: Props) {
  const core = useLivingAtlasCore(apiBase, project, facts)
  const tools = useLivingAtlasTools({
    apiBase,
    project,
    atlas: core.atlas,
    setAtlas: core.setAtlas,
    locationById: core.locationById,
    chapter: core.chapter,
    character: core.character,
    respectKnowledge: core.respectKnowledge,
    dirty: core.dirty,
    setDirty: core.setDirty,
    busy: core.busy,
    setBusy: core.setBusy,
    setError: core.setError,
    setNotice: core.setNotice,
    saveAtlas: core.saveAtlas,
    uniqueId: core.uniqueId,
    selectConnection: core.selectConnection,
  })

  useEffect(() => { tools.initializeRoutes() }, [core.atlas.locations.length])

  const automaticScale = inferCanvasScale(core.scopeLocation, core.scopedLocations)
  const currentScale = core.prefs.mapScale === 'auto' ? automaticScale : core.prefs.mapScale

  return <div className={`living-atlas-shell ${core.leftOpen ? 'left-open' : ''} ${core.rightOpen ? 'right-open' : ''}`}>
    <main className="living-atlas-stage">
      <div className="living-atlas-topbar">
        <div className="living-atlas-titleblock">
          <span className="living-kicker">WORLD · LIVING ATLAS</span>
          <div className="living-breadcrumb">
            <button type="button" onClick={core.goRoot}>World</button>
            {core.breadcrumbs.map((item) => <span key={item.id}><i>›</i><button type="button" onClick={() => core.explore(item.id)}>{item.name}</button></span>)}
          </div>
        </div>
        <div className="living-atlas-primary-actions">
          <button type="button" className={core.leftOpen ? 'active' : ''} onClick={() => core.setLeftOpen((value) => !value)} aria-label="Toggle atlas library">☰</button>
          <button type="button" onClick={() => core.zoom(.78)} aria-label="Zoom in">＋</button>
          <button type="button" onClick={() => core.zoom(1.28)} aria-label="Zoom out">−</button>
          <button type="button" onClick={() => core.setView(baseView(core.scopedLocations))}>Fit</button>
          <button type="button" className={core.prefs.viewMode === 'topology' ? 'active' : ''} onClick={() => core.setPrefs((current) => ({ ...current, viewMode: current.viewMode === 'atlas' ? 'topology' : 'atlas' }))}>{core.prefs.viewMode === 'atlas' ? 'Topology' : 'Atlas'}</button>
          <button type="button" onClick={() => void core.buildFromStory()} disabled={core.busy}>✦ Refresh canon</button>
          <button type="button" className={core.dirty ? 'primary' : ''} onClick={() => void core.saveAtlas()} disabled={core.busy || !core.dirty}>{core.dirty ? 'Save Atlas' : 'Saved'}</button>
        </div>
      </div>

      <div className="living-map-frame">
        <LivingAtlasCanvas
          atlas={core.atlas}
          locations={core.scopedLocations}
          connections={core.mapConnections}
          state={core.state}
          selectedLocationId={core.selectedLocationId}
          selectedConnectionId={core.selectedConnectionId}
          highlightedConnectionIds={tools.highlightedConnectionIds}
          showLabels={core.prefs.showLabels}
          showTerrain={core.prefs.showTerrain}
          showRegions={core.prefs.showRegions}
          worldType={core.prefs.worldType}
          visualStyle={core.prefs.visualStyle}
          viewMode={core.prefs.viewMode}
          mapScale={currentScale}
          backgroundHref={core.backgroundHref}
          view={core.view}
          onViewChange={core.setView}
          onSelectLocation={core.selectLocation}
          onSelectConnection={core.selectConnection}
          onMoveLocation={(id, x, y) => core.updateLocation(id, { x, y, position_status: 'canon' })}
          onExplore={core.explore}
        />

        {!core.scopedLocations.length && <div className="living-empty-map">
          <strong>{core.scopeLocation ? `${core.scopeLocation.name} has no mapped interior yet.` : 'Your atlas has no mapped places yet.'}</strong>
          <p>Add a place, build from the story, or assign existing places inside a parent location.</p>
          <button type="button" onClick={() => core.setLeftOpen(true)}>Open atlas library</button>
        </div>}

        <div className="living-map-hud living-world-pill"><b>{titleCase(core.prefs.worldType)}</b><span>{titleCase(core.prefs.visualStyle)} · {titleCase(currentScale)} map</span></div>
        <div className="living-map-hud living-legend"><span><i className="canon" />Canon</span><span><i className="inferred" />Inferred</span><span><i className="suggested" />Suggested</span><span><em />Planned route</span></div>
        <button type="button" className="living-map-hud living-inspector-toggle" onClick={() => core.setRightOpen((value) => !value)}>{core.rightOpen ? 'Close tools' : 'Story tools ›'}</button>

        <div className="living-timeline">
          <div><b>{core.chapter ? `Chapter ${core.chapter}` : 'Setup'}</b><span>{core.character || 'Author view'}</span></div>
          <input type="range" min={0} max={Math.max(1, core.maxChapter)} value={Math.min(core.chapter, Math.max(1, core.maxChapter))} onChange={(event) => core.setChapter(Number(event.target.value))} />
          <select value={core.character} onChange={(event) => core.setCharacter(event.target.value)}><option value="">Author / omniscient</option>{core.characters.map((name) => <option key={name}>{name}</option>)}</select>
        </div>
      </div>
    </main>

    <LivingAtlasLeftDrawer
      atlas={core.atlas}
      scopedLocations={core.scopedLocations}
      allVisibleLocations={core.visibleLocations}
      selectedLocationId={core.selectedLocationId}
      scopeId={core.scopeId}
      scopeLocation={core.scopeLocation}
      prefs={core.prefs}
      visuals={core.visuals}
      showInferred={core.showInferred}
      respectKnowledge={core.respectKnowledge}
      newPlaceName={core.newPlaceName}
      parentIdFor={core.parentIdFor}
      onClose={() => core.setLeftOpen(false)}
      onPrefs={(patch) => core.setPrefs((current) => ({ ...current, ...patch }))}
      onMapArtwork={core.updateMapArtwork}
      onShowInferred={core.setShowInferred}
      onRespectKnowledge={core.setRespectKnowledge}
      onNewPlaceName={core.setNewPlaceName}
      onAddPlace={core.addLocation}
      onSelectLocation={core.selectLocation}
      onExplore={core.explore}
      onUp={core.goUp}
    />

    <LivingAtlasRightDrawer
      apiBase={apiBase}
      projectSlug={project.slug}
      tab={core.rightTab}
      atlas={core.atlas}
      visibleLocations={core.visibleLocations}
      locationById={core.locationById}
      selectedLocation={core.selectedLocation}
      selectedConnection={core.selectedConnection}
      visuals={core.visuals}
      parentIdFor={core.parentIdFor}
      busy={core.busy}
      routeOrigin={tools.routeOrigin}
      routeDestination={tools.routeDestination}
      travelMode={tools.travelMode}
      newRouteDistance={tools.newRouteDistance}
      routes={tools.routes}
      activeRoute={tools.activeRoute}
      eventAction={tools.eventAction}
      eventTarget={tools.eventTarget}
      eventChapter={tools.eventChapter}
      eventValue={tools.eventValue}
      eventSummary={tools.eventSummary}
      eventOptions={tools.eventOptions}
      advicePrompt={tools.advicePrompt}
      advice={tools.advice}
      onClose={() => core.setRightOpen(false)}
      onTab={core.setRightTab}
      onUpdateLocation={core.updateLocation}
      onUpdateConnection={core.updateConnection}
      onDeleteLocation={core.deleteLocation}
      onDeleteConnection={core.deleteConnection}
      onExplore={core.explore}
      onOpenSource={(path) => onOpenSource(path)}
      onOrigin={tools.setRouteOrigin}
      onDestination={tools.setRouteDestination}
      onTravelMode={tools.setTravelMode}
      onDistance={tools.setNewRouteDistance}
      onCreateRoute={tools.addConnection}
      onCompareRoutes={() => void tools.compareRoutes()}
      onActiveRoute={tools.setActiveRoute}
      onEventAction={tools.changeEventAction}
      onEventTarget={tools.setEventTarget}
      onEventChapter={tools.setEventChapter}
      onEventValue={tools.setEventValue}
      onEventSummary={tools.setEventSummary}
      onAddEvent={tools.addEvent}
      onDeleteEvent={tools.deleteEvent}
      onAdvicePrompt={tools.setAdvicePrompt}
      onAskAtlas={() => void tools.askAtlas()}
    />

    {(core.error || core.notice) && <button type="button" className={`living-toast ${core.error ? 'error' : ''}`} onClick={core.clearMessage}>{core.error || core.notice}</button>}
  </div>
}