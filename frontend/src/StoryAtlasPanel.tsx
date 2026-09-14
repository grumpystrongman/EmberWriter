import { useEffect, useMemo, useRef, useState } from 'react'
import type { PointerEvent as ReactPointerEvent } from 'react'

import type { MemoryFact } from './MemoryPanel'
import type { ProviderConfig, WorkspaceProject } from './workspace-types'
import type {
  AtlasAdvice,
  AtlasConnection,
  AtlasEventAction,
  AtlasLocation,
  AtlasPreference,
  AtlasRoute,
  AtlasRouteCompare,
  AtlasState,
  StoryAtlas,
  VisualAsset,
} from './story-atlas-types'

type Props = {
  apiBase: string
  project: WorkspaceProject
  facts: MemoryFact[]
  onOpenSource: (path: string, anchor?: string) => void
}

type ViewBox = { x: number; y: number; w: number; h: number }

const EMPTY_ATLAS: StoryAtlas = {
  schema_version: 1,
  map: { title: 'Story Atlas', units: 'miles', background_asset_id: null },
  travel_profiles: {
    walk: { speed_mph: 3, hours_per_day: 8 },
    horse: { speed_mph: 5, hours_per_day: 9 },
    wagon: { speed_mph: 3.5, hours_per_day: 8 },
    boat: { speed_mph: 4, hours_per_day: 10 },
    airship: { speed_mph: 25, hours_per_day: 16 },
    portal: { speed_mph: 10000, hours_per_day: 24 },
  },
  locations: [],
  connections: [],
  events: [],
}

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

function currentProvider(): ProviderConfig | null {
  try {
    const parsed = JSON.parse(localStorage.getItem('emberwriter.provider') || 'null') as ProviderConfig | null
    return parsed?.model?.trim() && parsed.base_url?.trim() ? parsed : null
  } catch {
    return null
  }
}

function slugify(value: string) {
  return value.toLowerCase().trim().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'place'
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, Number.isFinite(value) ? value : min))
}

function asList(value: string) {
  return value.split(',').map((item) => item.trim()).filter(Boolean)
}

function baseView(atlas: StoryAtlas): ViewBox {
  if (!atlas.locations.length) return { x: -500, y: -350, w: 1000, h: 700 }
  const xs = atlas.locations.map((item) => item.x)
  const ys = atlas.locations.map((item) => item.y)
  const minX = Math.min(...xs)
  const maxX = Math.max(...xs)
  const minY = Math.min(...ys)
  const maxY = Math.max(...ys)
  const width = Math.max(500, maxX - minX + 280)
  const height = Math.max(360, maxY - minY + 220)
  return { x: (minX + maxX) / 2 - width / 2, y: (minY + maxY) / 2 - height / 2, w: width, h: height }
}

function statusLabel(value: string) {
  return value.charAt(0).toUpperCase() + value.slice(1)
}

function routeLabel(route: AtlasRoute, locationById: Map<string, AtlasLocation>) {
  return route.location_ids.map((id) => locationById.get(id)?.name || id).join(' → ')
}

export default function StoryAtlasPanel({ apiBase, project, facts, onOpenSource }: Props) {
  const [atlas, setAtlas] = useState<StoryAtlas>(EMPTY_ATLAS)
  const [state, setState] = useState<AtlasState | null>(null)
  const [visuals, setVisuals] = useState<VisualAsset[]>([])
  const [dirty, setDirty] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [selectedLocationId, setSelectedLocationId] = useState('')
  const [selectedConnectionId, setSelectedConnectionId] = useState('')
  const [chapter, setChapter] = useState(0)
  const [character, setCharacter] = useState('')
  const [respectKnowledge, setRespectKnowledge] = useState(true)
  const [showInferred, setShowInferred] = useState(true)
  const [showClosed, setShowClosed] = useState(true)
  const [showLabels, setShowLabels] = useState(true)
  const [view, setView] = useState<ViewBox>({ x: -500, y: -350, w: 1000, h: 700 })
  const [routeOrigin, setRouteOrigin] = useState('')
  const [routeDestination, setRouteDestination] = useState('')
  const [travelMode, setTravelMode] = useState('walk')
  const [routes, setRoutes] = useState<AtlasRoute[]>([])
  const [activeRoute, setActiveRoute] = useState<AtlasPreference | ''>('')
  const [advicePrompt, setAdvicePrompt] = useState('Make this journey more dramatic without breaking continuity.')
  const [advice, setAdvice] = useState<AtlasAdvice | null>(null)
  const [newPlaceName, setNewPlaceName] = useState('')
  const [newRouteFrom, setNewRouteFrom] = useState('')
  const [newRouteTo, setNewRouteTo] = useState('')
  const [newRouteDistance, setNewRouteDistance] = useState('10')
  const [newEventAction, setNewEventAction] = useState<AtlasEventAction>('connection_close')
  const [newEventTarget, setNewEventTarget] = useState('')
  const [newEventChapter, setNewEventChapter] = useState('0')
  const [newEventValue, setNewEventValue] = useState('')
  const [newEventSummary, setNewEventSummary] = useState('')
  const svgRef = useRef<SVGSVGElement | null>(null)
  const dragRef = useRef<{ pointerId: number; x: number; y: number; view: ViewBox } | null>(null)

  const maxChapter = useMemo(() => Math.max(0, ...facts.map((fact) => fact.chapter_order || 0)), [facts])
  const characters = useMemo(() => {
    const names = new Set<string>()
    for (const fact of facts) {
      if (fact.kind.startsWith('character_') || fact.kind === 'relationship') names.add(fact.subject)
    }
    return Array.from(names).filter(Boolean).sort((a, b) => a.localeCompare(b))
  }, [facts])
  const locationById = useMemo(() => new Map(atlas.locations.map((item) => [item.id, item])), [atlas.locations])
  const selectedLocation = atlas.locations.find((item) => item.id === selectedLocationId) || null
  const selectedConnection = atlas.connections.find((item) => item.id === selectedConnectionId) || null
  const highlightedConnectionIds = useMemo(() => {
    const route = routes.find((item) => item.preference === activeRoute)
    return new Set(route?.segments.map((item) => item.connection_id) || [])
  }, [routes, activeRoute])
  const visibleLocations = useMemo(
    () => atlas.locations.filter((item) => showInferred || item.canon_status === 'canon'),
    [atlas.locations, showInferred],
  )
  const visibleLocationIds = useMemo(() => new Set(visibleLocations.map((item) => item.id)), [visibleLocations])

  useEffect(() => { void loadAtlas() }, [project.slug])
  useEffect(() => {
    const next = Math.max(0, maxChapter)
    setChapter((current) => current === 0 ? next : Math.min(current, next || current))
  }, [maxChapter])
  useEffect(() => { void loadState() }, [project.slug, chapter, character, atlas.events.length, atlas.connections.length, atlas.locations.length])

  async function loadAtlas() {
    setBusy(true)
    setError('')
    try {
      const [loaded, assets] = await Promise.all([
        request<StoryAtlas>(`${apiBase}/projects/${project.slug}/atlas`),
        request<VisualAsset[]>(`${apiBase}/projects/${project.slug}/visual-assets`),
      ])
      setAtlas(loaded)
      setVisuals(assets)
      setDirty(false)
      const first = loaded.locations[0]?.id || ''
      setSelectedLocationId(first)
      setSelectedConnectionId('')
      setRouteOrigin(first)
      setRouteDestination(loaded.locations[1]?.id || '')
      setNewRouteFrom(first)
      setNewRouteTo(loaded.locations[1]?.id || '')
      setView(baseView(loaded))
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function loadState() {
    try {
      const params = new URLSearchParams({ chapter: String(chapter), character })
      setState(await request<AtlasState>(`${apiBase}/projects/${project.slug}/atlas/state?${params}`))
    } catch (cause) {
      setError((cause as Error).message)
    }
  }

  async function saveAtlas() {
    setBusy(true)
    setError('')
    try {
      const saved = await request<StoryAtlas>(`${apiBase}/projects/${project.slug}/atlas`, {
        method: 'PUT',
        body: JSON.stringify(atlas),
      })
      setAtlas(saved)
      setDirty(false)
      setNotice('Atlas saved. Routes and AI now use this version.')
      return true
    } catch (cause) {
      setError((cause as Error).message)
      return false
    } finally {
      setBusy(false)
    }
  }

  function updateLocation(id: string, patch: Partial<AtlasLocation>) {
    setAtlas((current) => ({ ...current, locations: current.locations.map((item) => item.id === id ? { ...item, ...patch } : item) }))
    setDirty(true)
  }

  function updateConnection(id: string, patch: Partial<AtlasConnection>) {
    setAtlas((current) => ({ ...current, connections: current.connections.map((item) => item.id === id ? { ...item, ...patch } : item) }))
    setDirty(true)
  }

  function uniqueId(base: string, existing: Set<string>) {
    let value = slugify(base)
    let index = 2
    while (existing.has(value)) value = `${slugify(base)}-${index++}`
    return value
  }

  function addLocation() {
    const name = newPlaceName.trim()
    if (!name) return
    const id = uniqueId(name, new Set(atlas.locations.map((item) => item.id)))
    const location: AtlasLocation = {
      id,
      name,
      kind: 'location',
      x: view.x + view.w / 2,
      y: view.y + view.h / 2,
      region: '',
      summary: '',
      terrain: [],
      tags: [],
      canon_status: 'suggested',
      position_status: 'suggested',
      confidence: 1,
      source_paths: [],
      known_by: [],
      image_asset_id: null,
    }
    setAtlas((current) => ({ ...current, locations: [...current.locations, location] }))
    setSelectedLocationId(id)
    setSelectedConnectionId('')
    setNewPlaceName('')
    setDirty(true)
  }

  function deleteSelectedLocation() {
    if (!selectedLocation) return
    const locationId = selectedLocation.id
    setAtlas((current) => ({
      ...current,
      locations: current.locations.filter((item) => item.id !== locationId),
      connections: current.connections.filter((item) => item.from_id !== locationId && item.to_id !== locationId),
      events: current.events.filter((item) => item.target_id !== locationId),
    }))
    setSelectedLocationId('')
    setDirty(true)
  }

  function addConnection() {
    if (!newRouteFrom || !newRouteTo || newRouteFrom === newRouteTo) return
    const distance = Number(newRouteDistance)
    if (!Number.isFinite(distance) || distance <= 0) {
      setError('Route distance must be greater than zero.')
      return
    }
    const from = locationById.get(newRouteFrom)
    const to = locationById.get(newRouteTo)
    const name = `${from?.name || newRouteFrom} → ${to?.name || newRouteTo}`
    const id = uniqueId(name, new Set(atlas.connections.map((item) => item.id)))
    const connection: AtlasConnection = {
      id,
      from_id: newRouteFrom,
      to_id: newRouteTo,
      name,
      distance,
      bidirectional: true,
      mode_multipliers: {},
      terrain_multiplier: 1,
      risk: 2,
      drama: 2,
      lore: 2,
      relationship: 1,
      active_from_chapter: 0,
      active_until_chapter: null,
      canon_status: 'suggested',
      confidence: 1,
      known_by: [],
      source_paths: [],
      notes: '',
    }
    setAtlas((current) => ({ ...current, connections: [...current.connections, connection] }))
    setSelectedConnectionId(id)
    setSelectedLocationId('')
    setDirty(true)
  }

  function deleteSelectedConnection() {
    if (!selectedConnection) return
    const id = selectedConnection.id
    setAtlas((current) => ({
      ...current,
      connections: current.connections.filter((item) => item.id !== id),
      events: current.events.filter((item) => item.target_id !== id),
    }))
    setSelectedConnectionId('')
    setDirty(true)
  }

  function addEvent() {
    const chapterNumber = Math.max(0, Number.parseInt(newEventChapter, 10) || 0)
    if (!newEventTarget) {
      setError('Choose a location or route for the world-state event.')
      return
    }
    const base = `${newEventAction}-${newEventTarget}-${chapterNumber}`
    const id = uniqueId(base, new Set(atlas.events.map((item) => item.id)))
    setAtlas((current) => ({
      ...current,
      events: [...current.events, {
        id,
        chapter: chapterNumber,
        action: newEventAction,
        target_id: newEventTarget,
        summary: newEventSummary.trim(),
        value: newEventValue.trim(),
        source_path: '',
      }],
    }))
    setNewEventSummary('')
    setNewEventValue('')
    setDirty(true)
  }

  async function buildFromStory(reset = false) {
    const provider = currentProvider()
    if (!provider) {
      setError('Choose an AI model before building the Story Atlas from the manuscript.')
      return
    }
    setBusy(true)
    setError('')
    try {
      const response = await request<{ atlas: StoryAtlas; added_locations: number; added_connections: number; warnings: string[] }>(
        `${apiBase}/projects/${project.slug}/atlas/bootstrap`,
        { method: 'POST', body: JSON.stringify({ provider, reset }) },
      )
      setAtlas(response.atlas)
      setDirty(false)
      setView(baseView(response.atlas))
      setNotice(`Atlas updated: ${response.added_locations} places and ${response.added_connections} routes added.${response.warnings.length ? ` ${response.warnings.join(' ')}` : ''}`)
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function compareRouteOptions() {
    if (!routeOrigin || !routeDestination || routeOrigin === routeDestination) {
      setError('Choose two different locations for route planning.')
      return
    }
    if (dirty && !(await saveAtlas())) return
    setBusy(true)
    setError('')
    try {
      const response = await request<AtlasRouteCompare>(`${apiBase}/projects/${project.slug}/atlas/routes/compare`, {
        method: 'POST',
        body: JSON.stringify({
          origin_id: routeOrigin,
          destination_id: routeDestination,
          mode: travelMode,
          chapter,
          character,
          respect_character_knowledge: respectKnowledge,
        }),
      })
      setRoutes(response.routes)
      setActiveRoute(response.routes[0]?.preference || '')
      if (!response.routes.length) setNotice('No route is available with the current chapter, travel mode, and knowledge filter.')
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function askAtlas(prompt = advicePrompt) {
    const provider = currentProvider()
    if (!provider) {
      setError('Choose an AI model before asking the Story Atlas for story advice.')
      return
    }
    if (dirty && !(await saveAtlas())) return
    setBusy(true)
    setError('')
    try {
      const response = await request<AtlasAdvice>(`${apiBase}/projects/${project.slug}/atlas/advise`, {
        method: 'POST',
        body: JSON.stringify({
          prompt,
          provider,
          chapter,
          character,
          origin_id: routeOrigin,
          destination_id: routeDestination,
          mode: travelMode,
          preference: activeRoute || 'dramatic',
        }),
      })
      setAdvice(response)
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  function resetView() {
    setView(baseView(atlas))
  }

  function zoom(factor: number) {
    setView((current) => {
      const width = clamp(current.w * factor, 120, 200000)
      const height = clamp(current.h * factor, 90, 140000)
      return { x: current.x + (current.w - width) / 2, y: current.y + (current.h - height) / 2, w: width, h: height }
    })
  }

  function pan(dx: number, dy: number) {
    setView((current) => ({ ...current, x: current.x + current.w * dx, y: current.y + current.h * dy }))
  }

  function pointerDown(event: ReactPointerEvent<SVGSVGElement>) {
    if (event.button !== 0) return
    dragRef.current = { pointerId: event.pointerId, x: event.clientX, y: event.clientY, view }
    event.currentTarget.setPointerCapture(event.pointerId)
  }

  function pointerMove(event: ReactPointerEvent<SVGSVGElement>) {
    const drag = dragRef.current
    const svg = svgRef.current
    if (!drag || drag.pointerId !== event.pointerId || !svg) return
    const rect = svg.getBoundingClientRect()
    if (!rect.width || !rect.height) return
    const dx = (event.clientX - drag.x) * drag.view.w / rect.width
    const dy = (event.clientY - drag.y) * drag.view.h / rect.height
    setView({ ...drag.view, x: drag.view.x - dx, y: drag.view.y - dy })
  }

  function pointerUp(event: ReactPointerEvent<SVGSVGElement>) {
    if (dragRef.current?.pointerId === event.pointerId) dragRef.current = null
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId)
  }

  const mapConnections = atlas.connections.filter((connection) => {
    if (!visibleLocationIds.has(connection.from_id) || !visibleLocationIds.has(connection.to_id)) return false
    const open = state?.connection_open[connection.id] ?? true
    if (!showClosed && !open) return false
    if (character && respectKnowledge && state && state.connection_known[connection.id] === false) return false
    return showInferred || connection.canon_status === 'canon'
  })

  const eventTargetOptions = newEventAction.startsWith('connection_')
    ? atlas.connections.map((item) => ({ id: item.id, name: item.name }))
    : atlas.locations.map((item) => ({ id: item.id, name: item.name }))

  return (
    <div className="atlas-workspace">
      <section className="atlas-toolbar-card">
        <div className="atlas-toolbar-main">
          <div>
            <strong>Story Atlas</strong>
            <span>{atlas.locations.length} places · {atlas.connections.length} routes · {atlas.events.length} world events</span>
          </div>
          <div className="atlas-toolbar-actions">
            <button type="button" onClick={() => void buildFromStory(false)} disabled={busy}>✦ Build from story</button>
            <button type="button" onClick={() => void saveAtlas()} disabled={busy || !dirty} className={dirty ? 'primary' : ''}>{dirty ? 'Save Atlas' : 'Saved'}</button>
            <button type="button" onClick={() => void loadAtlas()} disabled={busy}>↻</button>
          </div>
        </div>
        <div className="atlas-context-strip">
          <label>Chapter <input type="range" min={0} max={Math.max(1, maxChapter)} value={Math.min(chapter, Math.max(1, maxChapter))} onChange={(event) => setChapter(Number(event.target.value))} /><b>{chapter || 'Setup'}</b></label>
          <label>Viewpoint <select value={character} onChange={(event) => setCharacter(event.target.value)}><option value="">Author / omniscient</option>{characters.map((name) => <option key={name}>{name}</option>)}</select></label>
          <label className="atlas-check"><input type="checkbox" checked={respectKnowledge} onChange={(event) => setRespectKnowledge(event.target.checked)} /> Respect character knowledge</label>
          <label className="atlas-check"><input type="checkbox" checked={showInferred} onChange={(event) => setShowInferred(event.target.checked)} /> Inferred geography</label>
          <label className="atlas-check"><input type="checkbox" checked={showClosed} onChange={(event) => setShowClosed(event.target.checked)} /> Closed routes</label>
          <label className="atlas-check"><input type="checkbox" checked={showLabels} onChange={(event) => setShowLabels(event.target.checked)} /> Labels</label>
        </div>
      </section>

      <div className="atlas-grid">
        <aside className="atlas-side atlas-left">
          <section className="atlas-panel">
            <div className="atlas-panel-heading"><strong>Places</strong><span>{visibleLocations.length}</span></div>
            <div className="atlas-add-row"><input value={newPlaceName} onChange={(event) => setNewPlaceName(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') addLocation() }} placeholder="Add a place…" /><button type="button" onClick={addLocation} disabled={!newPlaceName.trim()}>+</button></div>
            <div className="atlas-place-list">
              {visibleLocations.map((location) => {
                const known = !character || !respectKnowledge || !state || state.location_known[location.id] !== false
                return <button type="button" key={location.id} className={selectedLocationId === location.id ? 'active' : ''} onClick={() => { setSelectedLocationId(location.id); setSelectedConnectionId('') }} disabled={!known}><span className={`atlas-dot ${location.canon_status}`} /> <span><b>{known ? location.name : 'Unknown location'}</b><small>{location.kind}{state?.location_control[location.id] ? ` · ${state.location_control[location.id]}` : ''}</small></span></button>
              })}
              {!visibleLocations.length && <p className="atlas-empty">No mapped places yet. Build from Story Memory or add one manually.</p>}
            </div>
          </section>

          <section className="atlas-panel atlas-route-builder">
            <div className="atlas-panel-heading"><strong>Add route</strong></div>
            <select value={newRouteFrom} onChange={(event) => setNewRouteFrom(event.target.value)}><option value="">From…</option>{atlas.locations.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select>
            <select value={newRouteTo} onChange={(event) => setNewRouteTo(event.target.value)}><option value="">To…</option>{atlas.locations.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select>
            <label>Distance ({atlas.map.units}) <input type="number" min="0.1" step="0.1" value={newRouteDistance} onChange={(event) => setNewRouteDistance(event.target.value)} /></label>
            <button type="button" onClick={addConnection} disabled={!newRouteFrom || !newRouteTo || newRouteFrom === newRouteTo}>Create route</button>
          </section>
        </aside>

        <main className="atlas-map-column">
          <section className="atlas-map-card">
            <div className="atlas-map-actions" aria-label="Map controls">
              <button type="button" onClick={() => zoom(0.75)} aria-label="Zoom in">＋</button>
              <button type="button" onClick={() => zoom(1.33)} aria-label="Zoom out">−</button>
              <button type="button" onClick={resetView}>Fit</button>
              <button type="button" onClick={() => pan(-0.12, 0)} aria-label="Pan left">←</button>
              <button type="button" onClick={() => pan(0.12, 0)} aria-label="Pan right">→</button>
              <button type="button" onClick={() => pan(0, -0.12)} aria-label="Pan up">↑</button>
              <button type="button" onClick={() => pan(0, 0.12)} aria-label="Pan down">↓</button>
            </div>
            <svg ref={svgRef} className="atlas-map" viewBox={`${view.x} ${view.y} ${view.w} ${view.h}`} onPointerDown={pointerDown} onPointerMove={pointerMove} onPointerUp={pointerUp} onPointerCancel={pointerUp} role="img" aria-label="Interactive fictional world map. Drag to pan or use map controls.">
              <defs>
                <pattern id="atlas-grid" width="80" height="80" patternUnits="userSpaceOnUse"><path d="M 80 0 L 0 0 0 80" fill="none" className="atlas-grid-line" /></pattern>
              </defs>
              <rect x={view.x - view.w} y={view.y - view.h} width={view.w * 3} height={view.h * 3} className="atlas-map-bg" />
              <rect x={view.x - view.w} y={view.y - view.h} width={view.w * 3} height={view.h * 3} fill="url(#atlas-grid)" />
              {mapConnections.map((connection) => {
                const from = locationById.get(connection.from_id)
                const to = locationById.get(connection.to_id)
                if (!from || !to) return null
                const open = state?.connection_open[connection.id] ?? true
                const highlighted = highlightedConnectionIds.has(connection.id)
                return <g key={connection.id} className={`atlas-link ${connection.canon_status} ${open ? '' : 'closed'} ${highlighted ? 'highlighted' : ''}`} onPointerDown={(event) => event.stopPropagation()} onClick={() => { setSelectedConnectionId(connection.id); setSelectedLocationId('') }}>
                  <line x1={from.x} y1={from.y} x2={to.x} y2={to.y} />
                  <line className="atlas-link-hit" x1={from.x} y1={from.y} x2={to.x} y2={to.y} />
                  {showLabels && <text x={(from.x + to.x) / 2} y={(from.y + to.y) / 2 - 8}>{connection.name}</text>}
                </g>
              })}
              {visibleLocations.map((location) => {
                const known = !character || !respectKnowledge || !state || state.location_known[location.id] !== false
                if (!known) return null
                const selected = selectedLocationId === location.id
                return <g key={location.id} className={`atlas-node ${location.canon_status} ${selected ? 'selected' : ''}`} transform={`translate(${location.x} ${location.y})`} onPointerDown={(event) => event.stopPropagation()} onClick={() => { setSelectedLocationId(location.id); setSelectedConnectionId('') }}>
                  <circle r={selected ? 15 : 11} />
                  <circle className="atlas-node-ring" r={selected ? 24 : 18} />
                  {showLabels && <><text className="atlas-node-label" x="20" y="-3">{location.name}</text><text className="atlas-node-kind" x="20" y="13">{location.kind}</text></>}
                </g>
              })}
            </svg>
            <div className="atlas-map-legend"><span><i className="canon" /> Canon</span><span><i className="inferred" /> Inferred</span><span><i className="suggested" /> Suggested</span><span><em /> Selected route</span><small>Map geometry is story-relative, not Earth GPS.</small></div>
          </section>

          <section className="atlas-route-planner atlas-panel">
            <div className="atlas-panel-heading"><div><strong>Story GPS</strong><small>Compare plausible paths by time, danger, drama, lore, or relationship opportunity.</small></div><button type="button" className="primary" onClick={() => void compareRouteOptions()} disabled={busy || atlas.locations.length < 2}>Compare routes</button></div>
            <div className="atlas-route-controls">
              <select value={routeOrigin} onChange={(event) => setRouteOrigin(event.target.value)}><option value="">Origin…</option>{atlas.locations.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select>
              <span>→</span>
              <select value={routeDestination} onChange={(event) => setRouteDestination(event.target.value)}><option value="">Destination…</option>{atlas.locations.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select>
              <select value={travelMode} onChange={(event) => setTravelMode(event.target.value)}>{Object.keys(atlas.travel_profiles).map((mode) => <option key={mode}>{mode}</option>)}</select>
            </div>
            {!!routes.length && <div className="atlas-route-cards">{routes.map((route) => <button type="button" key={route.preference} className={activeRoute === route.preference ? 'active' : ''} onClick={() => setActiveRoute(route.preference)}><strong>{statusLabel(route.preference)}</strong><span>{route.total_distance.toFixed(1)} {atlas.map.units} · {route.total_days < 1 ? `${route.total_hours.toFixed(1)} hr` : `${route.total_days.toFixed(1)} days`}</span><small>Risk {route.risk_score.toFixed(1)} · Drama {route.drama_score.toFixed(1)} · Lore {route.lore_score.toFixed(1)}</small><p>{routeLabel(route, locationById)}</p>{route.warnings.map((warning) => <em key={warning}>{warning}</em>)}</button>)}</div>}
          </section>

          <section className="atlas-ai-card atlas-panel">
            <div className="atlas-panel-heading"><div><strong>Spatial Story Director</strong><small>AI reasons over the saved graph, chapter state, route options, and Story Memory. Suggestions never become canon automatically.</small></div><button type="button" onClick={() => void askAtlas()} disabled={busy || !advicePrompt.trim()}>✦ Ask Atlas</button></div>
            <textarea value={advicePrompt} onChange={(event) => setAdvicePrompt(event.target.value)} placeholder="I need them at the fortress by dawn, but the journey is dragging…" />
            <div className="atlas-suggestion-chips"><button type="button" onClick={() => { setAdvicePrompt('Find the strongest place for an ambush along this route and explain why the geography supports it.'); void askAtlas('Find the strongest place for an ambush along this route and explain why the geography supports it.') }}>Ambush</button><button type="button" onClick={() => { setAdvicePrompt('Give me a slower route that creates a believable private conversation and relationship turning point.'); void askAtlas('Give me a slower route that creates a believable private conversation and relationship turning point.') }}>Relationship beat</button><button type="button" onClick={() => { setAdvicePrompt('Audit this journey for spatial or timeline continuity problems.'); void askAtlas('Audit this journey for spatial or timeline continuity problems.') }}>Continuity audit</button></div>
            {advice && <div className="atlas-advice"><p>{advice.summary}</p>{advice.continuity_warnings.map((warning) => <div className="atlas-warning" key={warning}>⚠ {warning}</div>)}<div className="atlas-advice-grid">{advice.ideas.map((idea) => <article key={`${idea.title}-${idea.rationale}`}><strong>{idea.title}</strong><p>{idea.rationale}</p><small>{idea.story_effect}</small>{idea.proposed_changes.length > 0 && <ul>{idea.proposed_changes.map((change) => <li key={change}>{change}</li>)}</ul>}</article>)}</div></div>}
          </section>
        </main>

        <aside className="atlas-side atlas-right">
          {selectedLocation && <section className="atlas-panel atlas-inspector">
            <div className="atlas-panel-heading"><strong>Place inspector</strong><button type="button" className="danger" onClick={deleteSelectedLocation}>Delete</button></div>
            {selectedLocation.image_asset_id && <img className="atlas-location-image" src={`${apiBase}/projects/${project.slug}/visual-assets/${selectedLocation.image_asset_id}`} alt={`Reference for ${selectedLocation.name}`} />}
            <label>Name <input value={selectedLocation.name} onChange={(event) => updateLocation(selectedLocation.id, { name: event.target.value })} /></label>
            <div className="atlas-two"><label>Kind <input value={selectedLocation.kind} onChange={(event) => updateLocation(selectedLocation.id, { kind: event.target.value })} /></label><label>Region <input value={selectedLocation.region} onChange={(event) => updateLocation(selectedLocation.id, { region: event.target.value })} /></label></div>
            <textarea value={selectedLocation.summary} onChange={(event) => updateLocation(selectedLocation.id, { summary: event.target.value })} placeholder="Scene-useful geography, atmosphere, constraints…" />
            <div className="atlas-two"><label>X <input type="number" value={selectedLocation.x} onChange={(event) => updateLocation(selectedLocation.id, { x: clamp(Number(event.target.value), -100000, 100000) })} /></label><label>Y <input type="number" value={selectedLocation.y} onChange={(event) => updateLocation(selectedLocation.id, { y: clamp(Number(event.target.value), -100000, 100000) })} /></label></div>
            <div className="atlas-two"><label>Canon <select value={selectedLocation.canon_status} onChange={(event) => updateLocation(selectedLocation.id, { canon_status: event.target.value as AtlasLocation['canon_status'] })}><option value="canon">Canon</option><option value="inferred">Inferred</option><option value="suggested">Suggested</option></select></label><label>Position <select value={selectedLocation.position_status} onChange={(event) => updateLocation(selectedLocation.id, { position_status: event.target.value as AtlasLocation['position_status'] })}><option value="canon">Canon</option><option value="inferred">Inferred</option><option value="suggested">Suggested</option></select></label></div>
            <label>Known by <input value={selectedLocation.known_by.join(', ')} onChange={(event) => updateLocation(selectedLocation.id, { known_by: asList(event.target.value) })} placeholder="Blank = everyone" /></label>
            <label>Terrain <input value={selectedLocation.terrain.join(', ')} onChange={(event) => updateLocation(selectedLocation.id, { terrain: asList(event.target.value) })} /></label>
            <label>Reference image <select value={selectedLocation.image_asset_id || ''} onChange={(event) => updateLocation(selectedLocation.id, { image_asset_id: event.target.value || null })}><option value="">None</option>{visuals.map((asset) => <option key={asset.asset_id} value={asset.asset_id}>{asset.title} · {asset.canon_status}</option>)}</select></label>
            {!!selectedLocation.source_paths.length && <div className="atlas-source-list"><strong>Sources</strong>{selectedLocation.source_paths.map((path) => <button type="button" key={path} onClick={() => onOpenSource(path)}>{path}</button>)}</div>}
          </section>}

          {selectedConnection && <section className="atlas-panel atlas-inspector">
            <div className="atlas-panel-heading"><strong>Route inspector</strong><button type="button" className="danger" onClick={deleteSelectedConnection}>Delete</button></div>
            <label>Name <input value={selectedConnection.name} onChange={(event) => updateConnection(selectedConnection.id, { name: event.target.value })} /></label>
            <div className="atlas-two"><label>Distance <input type="number" min="0.1" step="0.1" value={selectedConnection.distance} onChange={(event) => updateConnection(selectedConnection.id, { distance: Math.max(0.1, Number(event.target.value) || 0.1) })} /></label><label>Terrain × <input type="number" min="0.1" max="20" step="0.1" value={selectedConnection.terrain_multiplier} onChange={(event) => updateConnection(selectedConnection.id, { terrain_multiplier: clamp(Number(event.target.value), 0.1, 20) })} /></label></div>
            <div className="atlas-score-grid">{(['risk', 'drama', 'lore', 'relationship'] as const).map((key) => <label key={key}>{statusLabel(key)} <input type="range" min="1" max="5" value={selectedConnection[key]} onChange={(event) => updateConnection(selectedConnection.id, { [key]: Number(event.target.value) })} /><b>{selectedConnection[key]}</b></label>)}</div>
            <div className="atlas-two"><label>Starts ch. <input type="number" min="0" value={selectedConnection.active_from_chapter} onChange={(event) => updateConnection(selectedConnection.id, { active_from_chapter: Math.max(0, Number(event.target.value) || 0) })} /></label><label>Ends ch. <input type="number" min="0" value={selectedConnection.active_until_chapter ?? ''} onChange={(event) => updateConnection(selectedConnection.id, { active_until_chapter: event.target.value ? Math.max(0, Number(event.target.value)) : null })} placeholder="open" /></label></div>
            <label className="atlas-check"><input type="checkbox" checked={selectedConnection.bidirectional} onChange={(event) => updateConnection(selectedConnection.id, { bidirectional: event.target.checked })} /> Bidirectional</label>
            <label>Known by <input value={selectedConnection.known_by.join(', ')} onChange={(event) => updateConnection(selectedConnection.id, { known_by: asList(event.target.value) })} placeholder="Blank = everyone" /></label>
            <textarea value={selectedConnection.notes} onChange={(event) => updateConnection(selectedConnection.id, { notes: event.target.value })} placeholder="Road conditions, hazards, scene opportunities…" />
          </section>}

          {!selectedLocation && !selectedConnection && <section className="atlas-panel atlas-empty-inspector"><strong>Select a place or route</strong><p>Click the map to inspect canon, position, character knowledge, route scoring, and reference imagery.</p></section>}

          <section className="atlas-panel atlas-world-events">
            <div className="atlas-panel-heading"><strong>World-state event</strong><span>Chapter-aware</span></div>
            <div className="atlas-two"><select value={newEventAction} onChange={(event) => { setNewEventAction(event.target.value as AtlasEventAction); setNewEventTarget('') }}><option value="connection_close">Close route</option><option value="connection_open">Open route</option><option value="location_reveal">Reveal place</option><option value="location_control">Change control</option><option value="note">Story note</option></select><input type="number" min="0" value={newEventChapter} onChange={(event) => setNewEventChapter(event.target.value)} placeholder="Chapter" /></div>
            <select value={newEventTarget} onChange={(event) => setNewEventTarget(event.target.value)}><option value="">Target…</option>{eventTargetOptions.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select>
            {(newEventAction === 'location_reveal' || newEventAction === 'location_control' || newEventAction === 'note') && <input value={newEventValue} onChange={(event) => setNewEventValue(event.target.value)} placeholder={newEventAction === 'location_reveal' ? 'Reveal to character(s), comma separated' : newEventAction === 'location_control' ? 'Faction / controller' : 'Value'} />}
            <input value={newEventSummary} onChange={(event) => setNewEventSummary(event.target.value)} placeholder="What changes in the story?" />
            <button type="button" onClick={addEvent} disabled={!newEventTarget}>Add event</button>
            <div className="atlas-event-list">{[...atlas.events].sort((a, b) => b.chapter - a.chapter).slice(0, 12).map((event) => <div key={event.id}><b>Ch {event.chapter}</b><span>{event.action.replaceAll('_', ' ')}</span><small>{event.summary || event.value || event.target_id}</small><button type="button" onClick={() => { setAtlas((current) => ({ ...current, events: current.events.filter((item) => item.id !== event.id) })); setDirty(true) }}>×</button></div>)}</div>
          </section>
        </aside>
      </div>

      {(error || notice) && <div className={error ? 'center-error' : 'atlas-notice'}>{error || notice}</div>}
    </div>
  )
}
