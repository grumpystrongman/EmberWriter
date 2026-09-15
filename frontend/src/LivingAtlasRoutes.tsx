import type { AtlasLocation, AtlasPreference, AtlasRoute, StoryAtlas } from './story-atlas-types'
import { routeLabel, titleCase } from './living-atlas-helpers'

type Props = {
  atlas: StoryAtlas
  locationById: Map<string, AtlasLocation>
  routeOrigin: string
  routeDestination: string
  travelMode: string
  newRouteDistance: string
  routes: AtlasRoute[]
  activeRoute: AtlasPreference | ''
  busy: boolean
  onOrigin: (value: string) => void
  onDestination: (value: string) => void
  onTravelMode: (value: string) => void
  onDistance: (value: string) => void
  onCreateRoute: () => void
  onCompareRoutes: () => void
  onActiveRoute: (value: AtlasPreference) => void
}

export default function LivingAtlasRoutes({
  atlas,
  locationById,
  routeOrigin,
  routeDestination,
  travelMode,
  newRouteDistance,
  routes,
  activeRoute,
  busy,
  onOrigin,
  onDestination,
  onTravelMode,
  onDistance,
  onCreateRoute,
  onCompareRoutes,
  onActiveRoute,
}: Props) {
  return <section className="living-control-card living-routes-panel">
    <div className="living-card-title"><b>Story GPS</b><span>Travel that obeys geography and chapter state</span></div>
    <label>Origin<select value={routeOrigin} onChange={(event) => onOrigin(event.target.value)}><option value="">Choose…</option>{atlas.locations.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
    <label>Destination<select value={routeDestination} onChange={(event) => onDestination(event.target.value)}><option value="">Choose…</option>{atlas.locations.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
    <div className="living-two">
      <label>Travel mode<select value={travelMode} onChange={(event) => onTravelMode(event.target.value)}>{Object.keys(atlas.travel_profiles).map((mode) => <option key={mode}>{mode}</option>)}</select></label>
      <label>New-route distance<input type="number" min=".1" step=".1" value={newRouteDistance} onChange={(event) => onDistance(event.target.value)} /></label>
    </div>
    <div className="living-route-buttons">
      <button type="button" onClick={onCreateRoute} disabled={!routeOrigin || !routeDestination || routeOrigin === routeDestination}>Create route</button>
      <button type="button" className="primary" onClick={onCompareRoutes} disabled={busy || !routeOrigin || !routeDestination}>Compare paths</button>
    </div>
    <div className="living-route-results">
      {routes.map((route) => <button type="button" key={route.preference} className={activeRoute === route.preference ? 'active' : ''} onClick={() => onActiveRoute(route.preference)}>
        <b>{titleCase(route.preference)}</b>
        <span>{route.total_distance.toFixed(1)} {atlas.map.units} · {route.total_days < 1 ? `${route.total_hours.toFixed(1)} hr` : `${route.total_days.toFixed(1)} days`}</span>
        <small>Risk {route.risk_score.toFixed(1)} · Drama {route.drama_score.toFixed(1)} · Lore {route.lore_score.toFixed(1)}</small>
        <p>{routeLabel(route, locationById)}</p>
        {route.warnings.map((warning) => <em key={warning}>{warning}</em>)}
      </button>)}
      {!routes.length && <p className="living-panel-hint">Pick an origin and destination. EmberWriter can then compare the fastest, safest, dramatic, lore-rich and relationship-focused paths.</p>}
    </div>
  </section>
}
