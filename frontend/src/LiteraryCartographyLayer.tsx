import type { AtlasConnection, AtlasLocation } from './story-atlas-types'
import type { AtlasViewBox, AtlasWorldType } from './LivingAtlasCanvas'

type Props = {
  locations: AtlasLocation[]
  connections: AtlasConnection[]
  locationById: Map<string, AtlasLocation>
  view: AtlasViewBox
  scale: string
  worldType: AtlasWorldType
  showTerrain: boolean
}

type Bounds = { minX: number; minY: number; maxX: number; maxY: number; width: number; height: number; cx: number; cy: number }

function hash(value: string) {
  let result = 2166136261
  for (let index = 0; index < value.length; index += 1) {
    result ^= value.charCodeAt(index)
    result = Math.imul(result, 16777619)
  }
  return Math.abs(result >>> 0)
}

function unit(seed: string, index = 0) {
  return (hash(`${seed}:${index}`) % 10000) / 10000
}

function boundsFor(locations: AtlasLocation[], view: AtlasViewBox): Bounds {
  if (!locations.length) return { minX: view.x + view.w * .16, minY: view.y + view.h * .16, maxX: view.x + view.w * .84, maxY: view.y + view.h * .84, width: view.w * .68, height: view.h * .68, cx: view.x + view.w / 2, cy: view.y + view.h / 2 }
  const xs = locations.map((item) => item.x)
  const ys = locations.map((item) => item.y)
  const rawMinX = Math.min(...xs)
  const rawMaxX = Math.max(...xs)
  const rawMinY = Math.min(...ys)
  const rawMaxY = Math.max(...ys)
  const width = Math.max(view.w * .36, rawMaxX - rawMinX)
  const height = Math.max(view.h * .34, rawMaxY - rawMinY)
  const cx = (rawMinX + rawMaxX) / 2
  const cy = (rawMinY + rawMaxY) / 2
  return { minX: cx - width / 2, maxX: cx + width / 2, minY: cy - height / 2, maxY: cy + height / 2, width, height, cx, cy }
}

function organicBoundary(bounds: Bounds, seed: string, pad = 0) {
  const rx = Math.max(70, bounds.width / 2 + pad)
  const ry = Math.max(55, bounds.height / 2 + pad)
  const points = Array.from({ length: 18 }, (_, index) => {
    const angle = (Math.PI * 2 * index) / 18
    const jitter = .82 + unit(seed, index) * .28
    return { x: bounds.cx + Math.cos(angle) * rx * jitter, y: bounds.cy + Math.sin(angle) * ry * jitter }
  })
  let d = `M ${(points[0].x + points[1].x) / 2} ${(points[0].y + points[1].y) / 2}`
  for (let index = 1; index <= points.length; index += 1) {
    const point = points[index % points.length]
    const next = points[(index + 1) % points.length]
    d += ` Q ${point.x} ${point.y} ${(point.x + next.x) / 2} ${(point.y + next.y) / 2}`
  }
  return `${d} Z`
}

function routePath(connection: AtlasConnection, byId: Map<string, AtlasLocation>) {
  const from = byId.get(connection.from_id)
  const to = byId.get(connection.to_id)
  if (!from || !to) return ''
  const dx = to.x - from.x
  const dy = to.y - from.y
  const length = Math.max(1, Math.hypot(dx, dy))
  const bend = ((hash(connection.id) % 31) - 15) / 100
  const mx = (from.x + to.x) / 2 - (dy / length) * length * bend
  const my = (from.y + to.y) / 2 + (dx / length) * length * bend
  return `M${from.x} ${from.y} Q${mx} ${my} ${to.x} ${to.y}`
}

function Tree({ x, y, size = 1 }: { x: number; y: number; size?: number }) {
  return <g className="carto-tree" transform={`translate(${x} ${y}) scale(${size})`}><path d="M0 -13 8 -2 4 -2 10 8 -10 8 -4 -2 -8 -2Z" /><path d="M0 7V13" /></g>
}

function Mountain({ x, y, size = 1 }: { x: number; y: number; size?: number }) {
  return <g className="carto-mountain" transform={`translate(${x} ${y}) scale(${size})`}><path d="M-18 12 -4 -14 2 -3 8 -11 20 12Z" /><path d="M-4 -14 0 -7 2 -3M8 -11 11 -5" /></g>
}

function WorldCartography({ locations, bounds, seed }: { locations: AtlasLocation[]; bounds: Bounds; seed: string }) {
  const riverX = bounds.minX + bounds.width * (.36 + unit(seed, 77) * .28)
  const mountains = Array.from({ length: 9 }, (_, index) => ({
    x: bounds.minX + bounds.width * (.18 + index * .075),
    y: bounds.minY + bounds.height * (.3 + Math.sin(index * .8) * .08),
    size: .85 + unit(seed, index + 90) * .45,
  }))
  const trees = Array.from({ length: 22 }, (_, index) => ({
    x: bounds.minX + bounds.width * (.13 + unit(seed, index + 130) * .74),
    y: bounds.minY + bounds.height * (.55 + unit(seed, index + 180) * .28),
    size: .48 + unit(seed, index + 230) * .36,
  }))
  return <g className="carto-world">
    <path className="carto-land-shadow" d={organicBoundary(bounds, `${seed}:shadow`, 34)} />
    <path className="carto-landmass" d={organicBoundary(bounds, seed, 20)} />
    <path className="carto-coastline" d={organicBoundary(bounds, seed, 20)} />
    <path className="carto-contour" d={organicBoundary(bounds, `${seed}:contour`, -28)} />
    <path className="carto-river" d={`M${riverX} ${bounds.minY - 12} C${riverX - bounds.width * .1} ${bounds.cy - bounds.height * .2}, ${riverX + bounds.width * .11} ${bounds.cy + bounds.height * .06}, ${riverX - bounds.width * .04} ${bounds.maxY + 24}`} />
    <g className="carto-mountain-range">{mountains.map((item, index) => <Mountain key={index} {...item} />)}</g>
    <g className="carto-forest-belt">{trees.map((item, index) => <Tree key={index} {...item} />)}</g>
    {locations.filter((location) => /sea|ocean|lake|river/.test(`${location.kind} ${location.terrain.join(' ')}`.toLowerCase())).map((location) => <g className="carto-water-ripples" key={location.id} transform={`translate(${location.x} ${location.y})`}><path d="M-30 -8q10-7 20 0t20 0t20 0M-26 2q9-6 18 0t18 0t18 0M-20 12q7-5 14 0t14 0t14 0" /></g>)}
  </g>
}

function buildingFootprint(location: AtlasLocation) {
  const kind = `${location.kind} ${location.tags.join(' ')}`.toLowerCase()
  if (/courtyard|square|plaza|arena/.test(kind)) return <g className="carto-landmark open"><rect x="-30" y="-22" width="60" height="44" rx="6" /><rect x="-21" y="-13" width="42" height="26" rx="4" /></g>
  if (/tower|spire|keep|citadel/.test(kind)) return <g className="carto-landmark tower"><circle r="24" /><circle r="13" /><path d="M-18 -18 0 -29 18 -18M-18 18 0 29 18 18" /></g>
  if (/gate|portal|crossing/.test(kind)) return <g className="carto-landmark gate"><path d="M-22 13V-2Q-22-20 0-20Q22-20 22-2V13M-10 13V0Q-10-9 0-9Q10-9 10 0V13" /></g>
  if (/dorm|house|inn|shop|office/.test(kind)) return <g className="carto-landmark building"><rect x="-27" y="-18" width="54" height="36" rx="3" /><path d="M-32 -18 0 -30 32 -18" /><path d="M-8 18V3H8V18" /></g>
  if (/academy|school|palace|hall|temple|building/.test(kind)) return <g className="carto-landmark building grand"><path d="M-38 21V-13L0-29 38-13V21Z" /><rect x="-25" y="-8" width="15" height="29" /><rect x="10" y="-8" width="15" height="29" /><path d="M-5 21V-3H5V21" /></g>
  return <g className="carto-landmark minor"><rect x="-19" y="-14" width="38" height="28" rx="4" /></g>
}

function SettlementCartography({ locations, connections, byId, bounds, seed, site }: { locations: AtlasLocation[]; connections: AtlasConnection[]; byId: Map<string, AtlasLocation>; bounds: Bounds; seed: string; site: boolean }) {
  const cols = site ? 6 : 9
  const rows = site ? 4 : 7
  const blocks = Array.from({ length: cols * rows }, (_, index) => {
    const col = index % cols
    const row = Math.floor(index / cols)
    const cellW = bounds.width / cols
    const cellH = bounds.height / rows
    const x = bounds.minX + cellW * (col + .5) + (unit(seed, index) - .5) * cellW * .24
    const y = bounds.minY + cellH * (row + .5) + (unit(seed, index + 50) - .5) * cellH * .22
    const tooClose = locations.some((location) => Math.hypot(location.x - x, location.y - y) < Math.min(cellW, cellH) * .55)
    return { x, y, w: cellW * (.46 + unit(seed, index + 100) * .22), h: cellH * (.38 + unit(seed, index + 150) * .22), angle: (unit(seed, index + 200) - .5) * 10, skip: tooClose || unit(seed, index + 250) < .16 }
  })
  const edgeTrees = Array.from({ length: site ? 32 : 20 }, (_, index) => {
    const side = index % 4
    const t = unit(seed, index + 310)
    if (side === 0) return { x: bounds.minX - 22 + unit(seed, index + 350) * 10, y: bounds.minY + t * bounds.height }
    if (side === 1) return { x: bounds.maxX + 22 - unit(seed, index + 350) * 10, y: bounds.minY + t * bounds.height }
    if (side === 2) return { x: bounds.minX + t * bounds.width, y: bounds.minY - 20 + unit(seed, index + 350) * 10 }
    return { x: bounds.minX + t * bounds.width, y: bounds.maxY + 20 - unit(seed, index + 350) * 10 }
  })
  return <g className={site ? 'carto-site' : 'carto-city'}>
    <path className="carto-settlement-ground" d={organicBoundary(bounds, `${seed}:ground`, site ? 40 : 58)} />
    <path className="carto-wall" d={organicBoundary(bounds, `${seed}:wall`, site ? 44 : 64)} />
    {!site && <path className="carto-inner-wall" d={organicBoundary(bounds, `${seed}:inner`, -10)} />}
    <g className="carto-street-grid">
      {Array.from({ length: cols + 1 }, (_, index) => <path key={`v${index}`} d={`M${bounds.minX + (bounds.width / cols) * index} ${bounds.minY} Q${bounds.cx + (index % 2 ? 18 : -18)} ${bounds.cy} ${bounds.minX + (bounds.width / cols) * index} ${bounds.maxY}`} />)}
      {Array.from({ length: rows + 1 }, (_, index) => <path key={`h${index}`} d={`M${bounds.minX} ${bounds.minY + (bounds.height / rows) * index} Q${bounds.cx} ${bounds.cy + (index % 2 ? 14 : -14)} ${bounds.maxX} ${bounds.minY + (bounds.height / rows) * index}`} />)}
    </g>
    <g className="carto-blocks">{blocks.filter((item) => !item.skip).map((item, index) => <rect key={index} x={item.x - item.w / 2} y={item.y - item.h / 2} width={item.w} height={item.h} rx="3" transform={`rotate(${item.angle} ${item.x} ${item.y})`} />)}</g>
    {connections.map((connection) => { const d = routePath(connection, byId); return d ? <path key={connection.id} d={d} className="carto-primary-road" /> : null })}
    <g className="carto-edge-trees">{edgeTrees.map((item, index) => <Tree key={index} x={item.x} y={item.y} size={.52 + unit(seed, index + 390) * .2} />)}</g>
    <g className="carto-landmarks">{locations.map((location) => <g key={location.id} transform={`translate(${location.x} ${location.y})`}>{buildingFootprint(location)}</g>)}</g>
  </g>
}

function InteriorCartography({ locations, bounds, seed }: { locations: AtlasLocation[]; bounds: Bounds; seed: string }) {
  const roomW = Math.max(70, bounds.width / Math.max(2, Math.ceil(Math.sqrt(Math.max(1, locations.length)))))
  const roomH = Math.max(55, bounds.height / Math.max(2, Math.ceil(Math.sqrt(Math.max(1, locations.length)))))
  return <g className="carto-interior">
    <rect className="carto-floorplate" x={bounds.minX - 70} y={bounds.minY - 70} width={bounds.width + 140} height={bounds.height + 140} rx="12" />
    <path className="carto-corridor" d={`M${bounds.minX - 35} ${bounds.cy}H${bounds.maxX + 35}M${bounds.cx} ${bounds.minY - 35}V${bounds.maxY + 35}`} />
    {locations.map((location, index) => <g key={location.id} className="carto-room" transform={`translate(${location.x} ${location.y}) rotate(${(unit(seed, index) - .5) * 3})`}><rect x={-roomW * .34} y={-roomH * .32} width={roomW * .68} height={roomH * .64} rx="2" /><path d={`M0 ${roomH * .32}v-12`} /></g>)}
  </g>
}

function SpaceCartography({ locations, bounds, seed }: { locations: AtlasLocation[]; bounds: Bounds; seed: string }) {
  const orbitCount = Math.max(3, Math.min(7, locations.length + 1))
  return <g className="carto-space-detail">
    <ellipse className="carto-nebula" cx={bounds.cx} cy={bounds.cy} rx={bounds.width * .56} ry={bounds.height * .42} transform={`rotate(${unit(seed, 2) * 35 - 18} ${bounds.cx} ${bounds.cy})`} />
    {Array.from({ length: orbitCount }, (_, index) => <ellipse key={index} className="carto-orbit" cx={bounds.cx} cy={bounds.cy} rx={70 + index * Math.max(38, bounds.width / (orbitCount * 2.2))} ry={40 + index * Math.max(24, bounds.height / (orbitCount * 2.8))} transform={`rotate(${index * 7 - 12} ${bounds.cx} ${bounds.cy})`} />)}
    <circle className="carto-star-core" cx={bounds.cx} cy={bounds.cy} r="16" />
  </g>
}

export default function LiteraryCartographyLayer({ locations, connections, locationById, view, scale, worldType, showTerrain }: Props) {
  if (!locations.length) return null
  const bounds = boundsFor(locations, view)
  const seed = `${locations.map((item) => item.id).sort().join('|')}:${scale}:${worldType}`
  if (worldType === 'space' || scale === 'cosmos' || scale === 'system') return <SpaceCartography locations={locations} bounds={bounds} seed={seed} />
  if (scale === 'room' || scale === 'building') return <InteriorCartography locations={locations} bounds={bounds} seed={seed} />
  if (scale === 'city' || scale === 'district') return <SettlementCartography locations={locations} connections={connections} byId={locationById} bounds={bounds} seed={seed} site={false} />
  if (scale === 'site') return <SettlementCartography locations={locations} connections={connections} byId={locationById} bounds={bounds} seed={seed} site />
  return <>
    <WorldCartography locations={locations} bounds={bounds} seed={seed} />
    {showTerrain && <g className="carto-map-edge-lines"><path d={`M${view.x + 22} ${view.y + view.h - 42}q35-14 70 0t70 0t70 0`} /><path d={`M${view.x + view.w - 250} ${view.y + 34}q28-11 56 0t56 0t56 0`} /></g>}
  </>
}
