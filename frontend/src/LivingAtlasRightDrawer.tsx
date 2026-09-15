import LivingAtlasDetails from './LivingAtlasDetails'
import LivingAtlasDirector from './LivingAtlasDirector'
import LivingAtlasEvents from './LivingAtlasEvents'
import LivingAtlasRoutes from './LivingAtlasRoutes'
import type { AtlasAdvice, AtlasConnection, AtlasEventAction, AtlasLocation, AtlasPreference, AtlasRoute, StoryAtlas, VisualAsset } from './story-atlas-types'

export type LivingAtlasRightTab = 'details' | 'routes' | 'events' | 'director'

type Props = {
  apiBase: string
  projectSlug: string
  tab: LivingAtlasRightTab
  atlas: StoryAtlas
  visibleLocations: AtlasLocation[]
  locationById: Map<string, AtlasLocation>
  selectedLocation: AtlasLocation | null
  selectedConnection: AtlasConnection | null
  visuals: VisualAsset[]
  parentIdFor: (location: AtlasLocation) => string
  busy: boolean
  routeOrigin: string
  routeDestination: string
  travelMode: string
  newRouteDistance: string
  routes: AtlasRoute[]
  activeRoute: AtlasPreference | ''
  eventAction: AtlasEventAction
  eventTarget: string
  eventChapter: string
  eventValue: string
  eventSummary: string
  eventOptions: Array<{ id: string; name: string }>
  advicePrompt: string
  advice: AtlasAdvice | null
  onClose: () => void
  onTab: (value: LivingAtlasRightTab) => void
  onUpdateLocation: (id: string, patch: Partial<AtlasLocation>) => void
  onUpdateConnection: (id: string, patch: Partial<AtlasConnection>) => void
  onDeleteLocation: () => void
  onDeleteConnection: () => void
  onExplore: (id: string) => void
  onOpenSource: (path: string) => void
  onOrigin: (value: string) => void
  onDestination: (value: string) => void
  onTravelMode: (value: string) => void
  onDistance: (value: string) => void
  onCreateRoute: () => void
  onCompareRoutes: () => void
  onActiveRoute: (value: AtlasPreference) => void
  onEventAction: (value: AtlasEventAction) => void
  onEventTarget: (value: string) => void
  onEventChapter: (value: string) => void
  onEventValue: (value: string) => void
  onEventSummary: (value: string) => void
  onAddEvent: () => void
  onDeleteEvent: (id: string) => void
  onAdvicePrompt: (value: string) => void
  onAskAtlas: () => void
}

export default function LivingAtlasRightDrawer(props: Props) {
  return <aside className="living-atlas-drawer living-right-drawer">
    <div className="living-drawer-heading"><div><span>Story tools</span><b>Spatial canon, routes, history & AI</b></div><button type="button" onClick={props.onClose}>×</button></div>
    <div className="living-tool-tabs">
      <button type="button" className={props.tab === 'details' ? 'active' : ''} onClick={() => props.onTab('details')}>Details</button>
      <button type="button" className={props.tab === 'routes' ? 'active' : ''} onClick={() => props.onTab('routes')}>Routes</button>
      <button type="button" className={props.tab === 'events' ? 'active' : ''} onClick={() => props.onTab('events')}>History</button>
      <button type="button" className={props.tab === 'director' ? 'active' : ''} onClick={() => props.onTab('director')}>Director</button>
    </div>
    <div className="living-drawer-scroll living-right-scroll">
      {props.tab === 'details' && <LivingAtlasDetails
        apiBase={props.apiBase}
        projectSlug={props.projectSlug}
        selectedLocation={props.selectedLocation}
        selectedConnection={props.selectedConnection}
        locations={props.atlas.locations}
        visibleLocations={props.visibleLocations}
        visuals={props.visuals}
        parentIdFor={props.parentIdFor}
        onUpdateLocation={props.onUpdateLocation}
        onUpdateConnection={props.onUpdateConnection}
        onDeleteLocation={props.onDeleteLocation}
        onDeleteConnection={props.onDeleteConnection}
        onExplore={props.onExplore}
        onOpenSource={props.onOpenSource}
      />}
      {props.tab === 'routes' && <LivingAtlasRoutes
        atlas={props.atlas}
        locationById={props.locationById}
        routeOrigin={props.routeOrigin}
        routeDestination={props.routeDestination}
        travelMode={props.travelMode}
        newRouteDistance={props.newRouteDistance}
        routes={props.routes}
        activeRoute={props.activeRoute}
        busy={props.busy}
        onOrigin={props.onOrigin}
        onDestination={props.onDestination}
        onTravelMode={props.onTravelMode}
        onDistance={props.onDistance}
        onCreateRoute={props.onCreateRoute}
        onCompareRoutes={props.onCompareRoutes}
        onActiveRoute={props.onActiveRoute}
      />}
      {props.tab === 'events' && <LivingAtlasEvents
        atlas={props.atlas}
        action={props.eventAction}
        target={props.eventTarget}
        chapter={props.eventChapter}
        value={props.eventValue}
        summary={props.eventSummary}
        options={props.eventOptions}
        onAction={props.onEventAction}
        onTarget={props.onEventTarget}
        onChapter={props.onEventChapter}
        onValue={props.onEventValue}
        onSummary={props.onEventSummary}
        onAdd={props.onAddEvent}
        onDelete={props.onDeleteEvent}
      />}
      {props.tab === 'director' && <LivingAtlasDirector prompt={props.advicePrompt} advice={props.advice} busy={props.busy} onPrompt={props.onAdvicePrompt} onAsk={props.onAskAtlas} />}
    </div>
  </aside>
}
