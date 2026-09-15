import { useMemo, useRef, useState } from 'react'
import type { PointerEvent as ReactPointerEvent, WheelEvent as ReactWheelEvent } from 'react'

import type { AtlasConnection, AtlasLocation, AtlasState, StoryAtlas } from './story-atlas-types'

export type AtlasViewBox = { x: number; y: number; w: number; h: number }
export type AtlasWorldType = 'fantasy' | 'modern' | 'historical' | 'space' | 'dimensional' | 'hybrid'
export type AtlasVisualStyle = 'illustrated' | 'parchment' | 'star-chart' | 'manuscript' | 'schematic'
export type AtlasViewMode = 'atlas' | 'topology'

type Props = {
  atlas: StoryAtlas
  locations: AtlasLocation[]
  connections: AtlasConnection[]
  state: AtlasState | null
  selectedLocationId: string
  selectedConnectionId: string
  highlightedConnectionIds: Set<string>
  showLabels: boolean
  showTerrain: boolean
  showRegions: boolean
  worldType: AtlasWorldType
  visualStyle: AtlasVisualStyle
  viewMode: AtlasViewMode
  backgroundHref: string
  view: AtlasViewBox
  onViewChange: (view: AtlasViewBox) => void
  onSelectLocation: (id: string) => void
  onSelectConnection: (id: string) => void
  onMoveLocation: (id: string, x: number, y: number) => void
  onExplore: (id: string) => void
}

type DragState =
  | { mode: 'pan'; pointerId: number; clientX: number; clientY: number; view: AtlasViewBox }
  | { mode: 'node'; pointerId: number; clientX: number; clientY: number; view: AtlasViewBox; location: AtlasLocation }

function hash(value: string) {
  let result = 2166136261
  for (let index = 0; index < value.length; index += 1) {
    result ^= value.charCodeAt(index)
    result = Math.imul(result, 16777619)
  }
  return Math.abs(result >>> 0)
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value))
}

function curvePath(from: AtlasLocation, to: AtlasLocation, seed: string) {
  const dx = to.x - from.x
  const dy = to.y - from.y
  const length = Math.max(1, Math.hypot(dx, dy))
  const bend = ((hash(seed) % 41) - 20) / 100
  const mx = (from.x + to.x) / 2 - (dy / length) * length * bend
  const my = (from.y + to.y) / 2 + (dx / length) * length * bend
  return `M ${from.x} ${from.y} Q ${mx} ${my} ${to.x} ${to.y}`
}

function iconPath(location: AtlasLocation) {
  const kind = `${location.kind} ${location.tags.join(' ')}`.toLowerCase()
  if (/(castle|fort|keep|palace|citadel|tower|spire)/.test(kind)) return 'M -11 9 L -11 -5 L -7 -5 L -7 -11 L -2 -11 L -2 -5 L 3 -5 L 3 -11 L 8 -11 L 8 -5 L 11 -5 L 11 9 Z'
  if (/(gate|portal|crossing|wormhole)/.test(kind)) return 'M -10 9 L -10 0 A 10 10 0 0 1 10 0 L 10 9 L 5 9 L 5 0 A 5 5 0 0 0 -5 0 L -5 9 Z'
  if (/(forest|wood|grove)/.test(kind)) return 'M 0 -12 L 8 1 L 4 1 L 10 10 L -10 10 L -4 1 L -8 1 Z'
  if (/(mountain|peak|ridge)/.test(kind)) return 'M -13 10 L -2 -11 L 3 -2 L 7 -8 L 14 10 Z'
  if (/(city|town|village|district|academy|school)/.test(kind)) return 'M -11 10 L -11 0 L -5 0 L -5 -7 L 0 -7 L 0 -2 L 5 -2 L 5 -10 L 11 -10 L 11 10 Z'
  if (/(planet|world|moon)/.test(kind)) return 'M 0 -11 A 11 11 0 1 1 0 11 A 11 11 0 1 1 0 -11 M -16 3 Q 0 10 16 3'
  return 'M 0 -11 L 9 0 L 0 11 L -9 0 Z'
}

function TerrainGlyph({ location, index }: { location: AtlasLocation; index: number }) {
  const terrain = location.terrain[index % Math.max(1, location.terrain.length)]?.toLowerCase() || ''
  const seed = hash(`${location.id}-${index}`)
  const angle = (seed % 360) * Math.PI / 180
  const radius = 34 + (seed % 30)
  const x = location.x + Math.cos(angle) * radius
  const y = location.y + Math.sin(angle) * radius
  if (/forest|wood|grove|jungle/.test(terrain)) {
    return <g className="living-terrain forest" transform={`translate(${x} ${y}) scale(.75)`}><path d="M0 -12 7 0 3 0 9 9 -9 9 -3 0 -7 0Z" /><path d="M0 8V15" /></g>
  }
  if (/mountain|ridge|hill|cliff/.test(terrain)) {
    return <g className="living-terrain mountain" transform={`translate(${x} ${y}) scale(.8)`}><path d="M-14 10 -3 -10 2 -2 6 -8 15 10Z" /><path d="M-3 -10 0 -4 2 -2" /></g>
  }
  if (/river|water|lake|sea|marsh|swamp/.test(terrain)) {
    return <g className="living-terrain water" transform={`translate(${x} ${y})`}><path d="M-15 -4 Q-8 -9 -1 -4 T13 -4 M-15 4 Q-8 -1 -1 4 T13 4" /></g>
  }
  if (/desert|sand|dune/.test(terrain)) {
    return <g className="living-terrain dune" transform={`translate(${x} ${y})`}><path d="M-15 5 Q-5 -7 4 4 Q9 9 16 2" /></g>
  }
  return null
}

export default function LivingAtlasCanvas({
  atlas,
  locations,
  connections,
  state,
  selectedLocationId,
  selectedConnectionId,
  highlightedConnectionIds,
  showLabels,
  showTerrain,
  showRegions,
  worldType,
  visualStyle,
  viewMode,
  backgroundHref,
  view,
  onViewChange,
  onSelectLocation,
  onSelectConnection,
  onMoveLocation,
  onExplore,
}: Props) {
  const svgRef = useRef<SVGSVGElement | null>(null)
  const dragRef = useRef<DragState | null>(null)
  const [draggingNode, setDraggingNode] = useState('')
  const locationById = useMemo(() => new Map(atlas.locations.map((item) => [item.id, item])), [atlas.locations])
  const visibleIds = useMemo(() => new Set(locations.map((item) => item.id)), [locations])
  const regionLabels = useMemo(() => {
    const regions = new Map<string, { x: number; y: number; count: number }>()
    for (const location of locations) {
      if (!location.region.trim()) continue
      const current = regions.get(location.region) || { x: 0, y: 0, count: 0 }
      current.x += location.x
      current.y += location.y
      current.count += 1
      regions.set(location.region, current)
    }
    return Array.from(regions.entries()).map(([name, item]) => ({ name, x: item.x / item.count, y: item.y / item.count }))
  }, [locations])

  function pointerToWorld(clientX: number, clientY: number, targetView: AtlasViewBox) {
    const rect = svgRef.current?.getBoundingClientRect()
    if (!rect?.width || !rect.height) return { x: 0, y: 0 }
    return {
      x: targetView.x + ((clientX - rect.left) / rect.width) * targetView.w,
      y: targetView.y + ((clientY - rect.top) / rect.height) * targetView.h,
    }
  }

  function startPan(event: ReactPointerEvent<SVGSVGElement>) {
    if (event.button !== 0) return
    dragRef.current = { mode: 'pan', pointerId: event.pointerId, clientX: event.clientX, clientY: event.clientY, view }
    event.currentTarget.setPointerCapture(event.pointerId)
  }

  function startNodeDrag(event: ReactPointerEvent<SVGGElement>, location: AtlasLocation) {
    if (event.button !== 0) return
    event.stopPropagation()
    dragRef.current = { mode: 'node', pointerId: event.pointerId, clientX: event.clientX, clientY: event.clientY, view, location }
    setDraggingNode(location.id)
    svgRef.current?.setPointerCapture(event.pointerId)
    onSelectLocation(location.id)
  }

  function movePointer(event: ReactPointerEvent<SVGSVGElement>) {
    const drag = dragRef.current
    const rect = svgRef.current?.getBoundingClientRect()
    if (!drag || drag.pointerId !== event.pointerId || !rect?.width || !rect.height) return
    if (drag.mode === 'pan') {
      const dx = (event.clientX - drag.clientX) * drag.view.w / rect.width
      const dy = (event.clientY - drag.clientY) * drag.view.h / rect.height
      onViewChange({ ...drag.view, x: drag.view.x - dx, y: drag.view.y - dy })
      return
    }
    const origin = pointerToWorld(drag.clientX, drag.clientY, drag.view)
    const next = pointerToWorld(event.clientX, event.clientY, drag.view)
    onMoveLocation(drag.location.id, drag.location.x + next.x - origin.x, drag.location.y + next.y - origin.y)
  }

  function endPointer(event: ReactPointerEvent<SVGSVGElement>) {
    if (dragRef.current?.pointerId === event.pointerId) dragRef.current = null
    setDraggingNode('')
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId)
  }

  function wheel(event: ReactWheelEvent<SVGSVGElement>) {
    event.preventDefault()
    const factor = event.deltaY > 0 ? 1.14 : 0.86
    const anchor = pointerToWorld(event.clientX, event.clientY, view)
    const width = clamp(view.w * factor, 100, 200000)
    const height = clamp(view.h * factor, 75, 140000)
    const rx = (anchor.x - view.x) / view.w
    const ry = (anchor.y - view.y) / view.h
    onViewChange({ x: anchor.x - width * rx, y: anchor.y - height * ry, w: width, h: height })
  }

  return (
    <svg
      ref={svgRef}
      className={`living-atlas-map world-${worldType} style-${visualStyle} mode-${viewMode}`}
      viewBox={`${view.x} ${view.y} ${view.w} ${view.h}`}
      onPointerDown={startPan}
      onPointerMove={movePointer}
      onPointerUp={endPointer}
      onPointerCancel={endPointer}
      onWheel={wheel}
      role="img"
      aria-label="Interactive Living Atlas. Drag the map to pan, drag places to position them, use the mouse wheel to zoom, and double click a place to explore inside it."
    >
      <defs>
        <filter id="living-paper-noise" x="-20%" y="-20%" width="140%" height="140%">
          <feTurbulence type="fractalNoise" baseFrequency=".018" numOctaves="3" seed="7" result="noise" />
          <feColorMatrix in="noise" type="saturate" values="0" result="mono" />
          <feBlend in="SourceGraphic" in2="mono" mode="soft-light" />
        </filter>
        <filter id="living-glow" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="3" result="blur" /><feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
        <pattern id="living-grid" width="70" height="70" patternUnits="userSpaceOnUse"><path d="M70 0H0V70" className="living-grid-line" fill="none" /></pattern>
        <pattern id="living-starmap" width="130" height="130" patternUnits="userSpaceOnUse"><circle cx="16" cy="22" r="1.3" /><circle cx="73" cy="42" r=".8" /><circle cx="112" cy="86" r="1.1" /><circle cx="48" cy="111" r=".6" /></pattern>
        <radialGradient id="living-vignette" cx="50%" cy="45%" r="72%"><stop offset="45%" stopColor="transparent" /><stop offset="100%" stopColor="rgba(0,0,0,.58)" /></radialGradient>
      </defs>

      <rect x={view.x - view.w} y={view.y - view.h} width={view.w * 3} height={view.h * 3} className="living-map-ground" />
      {backgroundHref && viewMode === 'atlas' && <image href={backgroundHref} x={view.x} y={view.y} width={view.w} height={view.h} preserveAspectRatio="xMidYMid slice" className="living-background-art" />}
      {viewMode === 'topology' && <rect x={view.x - view.w} y={view.y - view.h} width={view.w * 3} height={view.h * 3} fill="url(#living-grid)" />}
      {viewMode === 'atlas' && worldType === 'space' && <rect x={view.x - view.w} y={view.y - view.h} width={view.w * 3} height={view.h * 3} fill="url(#living-starmap)" className="living-stars" />}
      {viewMode === 'atlas' && worldType === 'dimensional' && <g className="living-dimensional-rings"><circle cx={view.x + view.w * .72} cy={view.y + view.h * .32} r={view.w * .13} /><circle cx={view.x + view.w * .72} cy={view.y + view.h * .32} r={view.w * .09} /><circle cx={view.x + view.w * .72} cy={view.y + view.h * .32} r={view.w * .05} /></g>}

      {showRegions && viewMode === 'atlas' && regionLabels.map((region) => <text key={region.name} x={region.x} y={region.y - 55} className="living-region-label">{region.name}</text>)}

      {showTerrain && viewMode === 'atlas' && locations.flatMap((location) => location.terrain.slice(0, 4).map((_, index) => <TerrainGlyph key={`${location.id}-${index}`} location={location} index={index} />))}

      {connections.map((connection) => {
        if (!visibleIds.has(connection.from_id) || !visibleIds.has(connection.to_id)) return null
        const from = locationById.get(connection.from_id)
        const to = locationById.get(connection.to_id)
        if (!from || !to) return null
        const open = state?.connection_open[connection.id] ?? true
        const highlighted = highlightedConnectionIds.has(connection.id)
        const selected = selectedConnectionId === connection.id
        const path = curvePath(from, to, connection.id)
        return <g key={connection.id} className={`living-route ${connection.canon_status} ${open ? '' : 'closed'} ${highlighted ? 'highlighted' : ''} ${selected ? 'selected' : ''}`} onPointerDown={(event) => event.stopPropagation()} onClick={() => onSelectConnection(connection.id)}>
          <path d={path} className="living-route-shadow" />
          <path d={path} className="living-route-line" />
          <path d={path} className="living-route-hit" />
          {showLabels && viewMode === 'topology' && <text x={(from.x + to.x) / 2} y={(from.y + to.y) / 2 - 8}>{connection.name}</text>}
        </g>
      })}

      {locations.map((location) => {
        const selected = selectedLocationId === location.id
        const known = !state || state.location_known[location.id] !== false
        if (!known) return null
        return <g
          key={location.id}
          className={`living-place ${location.canon_status} ${selected ? 'selected' : ''} ${draggingNode === location.id ? 'dragging' : ''}`}
          transform={`translate(${location.x} ${location.y})`}
          onPointerDown={(event) => startNodeDrag(event, location)}
          onDoubleClick={(event) => { event.stopPropagation(); onExplore(location.id) }}
        >
          <circle className="living-place-aura" r={selected ? 31 : 25} />
          <path d={iconPath(location)} className="living-place-icon" />
          {showLabels && <g className="living-place-copy"><text className="living-place-name" x="20" y="-5">{location.name}</text><text className="living-place-kind" x="20" y="10">{location.kind}</text></g>}
        </g>
      })}

      <g className="living-compass" transform={`translate(${view.x + view.w - 56} ${view.y + 58})`}><circle r="27" /><path d="M0 -22 5 0 0 22 -5 0Z" /><text x="0" y="-31">N</text></g>
      <rect x={view.x} y={view.y} width={view.w} height={view.h} fill="url(#living-vignette)" className="living-vignette" />
    </svg>
  )
}
