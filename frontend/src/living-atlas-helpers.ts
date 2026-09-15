import type { AtlasLocation, AtlasRoute, StoryAtlas } from './story-atlas-types'
import type { ProviderConfig } from './workspace-types'
import type { AtlasViewBox, AtlasViewMode, AtlasVisualStyle, AtlasWorldType } from './LivingAtlasCanvas'

export const SCALE_OPTIONS = [
  'cosmos',
  'galaxy',
  'dimension',
  'system',
  'world',
  'continent',
  'nation',
  'country',
  'state',
  'province',
  'county',
  'region',
  'city',
  'district',
  'street',
  'site',
  'facility',
  'building',
  'floor',
  'room',
  'area',
  'object',
] as const
export type AtlasScale = typeof SCALE_OPTIONS[number]
export type AtlasMapScale = 'auto' | AtlasScale
export type AtlasRenderScale = 'system' | 'world' | 'city' | 'site' | 'building'

export type AtlasPrefs = {
  worldType: AtlasWorldType
  visualStyle: AtlasVisualStyle
  viewMode: AtlasViewMode
  mapScale: AtlasMapScale
  showTerrain: boolean
  showRegions: boolean
  showLabels: boolean
  showCartography: boolean
  editCartography: boolean
}

export const EMPTY_ATLAS: StoryAtlas = {
  schema_version: 2,
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
  features: [],
  events: [],
}

export const DEFAULT_PREFS: AtlasPrefs = {
  worldType: 'fantasy',
  visualStyle: 'illustrated',
  viewMode: 'atlas',
  mapScale: 'auto',
  showTerrain: true,
  showRegions: true,
  showLabels: true,
  showCartography: true,
  editCartography: false,
}

export async function atlasRequest<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { ...init, headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) } })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || `${response.status} ${response.statusText}`)
  }
  return response.json() as Promise<T>
}

export function currentProvider(): ProviderConfig | null {
  try {
    const parsed = JSON.parse(localStorage.getItem('emberwriter.provider') || 'null') as ProviderConfig | null
    return parsed?.model?.trim() && parsed.base_url?.trim() ? parsed : null
  } catch {
    return null
  }
}

export function slugify(value: string) {
  return value.toLowerCase().trim().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'place'
}

export function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, Number.isFinite(value) ? value : min))
}

export function asList(value: string) {
  return value.split(',').map((item) => item.trim()).filter(Boolean)
}

export function tagValue(location: AtlasLocation, prefix: string) {
  return location.tags.find((tag) => tag.startsWith(prefix))?.slice(prefix.length) || ''
}

export function withTag(location: AtlasLocation, prefix: string, value: string) {
  const tags = location.tags.filter((tag) => !tag.startsWith(prefix))
  if (value) tags.push(`${prefix}${value}`)
  return tags
}

export function inferScale(location: Pick<AtlasLocation, 'kind' | 'tags'>): AtlasScale {
  const explicit = location.tags.find((tag) => tag.startsWith('scale:'))?.slice(6) || ''
  if (SCALE_OPTIONS.includes(explicit as AtlasScale)) return explicit as AtlasScale
  const kind = location.kind.toLowerCase()
  if (/\b(object|artifact|altar|statue|desk|bed|door|portal-stone)\b/.test(kind)) return 'object'
  if (/\b(area|alcove|corner|zone|section|garden|yard|courtyard)\b/.test(kind)) return 'area'
  if (/room|chamber|office|dorm|bedroom|kitchen|classroom|ward|lab/.test(kind)) return 'room'
  if (/floor|deck|level|storey|story/.test(kind)) return 'floor'
  if (/facility|hospital|school|academy|campus|station|airport|prison|ship|starship/.test(kind)) return 'facility'
  if (/building|house|tower|spire|keep|palace|castle|inn|tavern|temple/.test(kind)) return 'building'
  if (/street|road|avenue|lane|boulevard/.test(kind)) return 'street'
  if (/district|quarter|ward|neighborhood/.test(kind)) return 'district'
  if (/city|town|village|settlement/.test(kind)) return 'city'
  if (/county/.test(kind)) return 'county'
  if (/province/.test(kind)) return 'province'
  if (/state/.test(kind)) return 'state'
  if (/country/.test(kind)) return 'country'
  if (/nation|kingdom|empire|republic/.test(kind)) return 'nation'
  if (/region|territory/.test(kind)) return 'region'
  if (/continent|landmass/.test(kind)) return 'continent'
  if (/planet|world|moon/.test(kind)) return 'world'
  if (/system|star/.test(kind)) return 'system'
  if (/dimension|realm|plane/.test(kind)) return 'dimension'
  if (/galaxy/.test(kind)) return 'galaxy'
  if (/cosmos|universe/.test(kind)) return 'cosmos'
  return 'site'
}

export function childScaleFor(parent: AtlasScale): AtlasScale {
  const next: Record<AtlasScale, AtlasScale> = {
    cosmos: 'galaxy',
    galaxy: 'system',
    dimension: 'world',
    system: 'world',
    world: 'continent',
    continent: 'nation',
    nation: 'region',
    country: 'state',
    state: 'county',
    province: 'county',
    county: 'city',
    region: 'city',
    city: 'district',
    district: 'street',
    street: 'site',
    site: 'facility',
    facility: 'building',
    building: 'floor',
    floor: 'room',
    room: 'area',
    area: 'object',
    object: 'object',
  }
  return next[parent]
}

export function inferCanvasScale(scopeLocation: AtlasLocation | null, locations: AtlasLocation[]): AtlasScale {
  if (scopeLocation) return inferScale(scopeLocation)
  if (!locations.length) return 'world'
  const scales = locations.map(inferScale)
  const order: AtlasScale[] = ['cosmos', 'galaxy', 'dimension', 'system', 'world', 'continent', 'nation', 'country', 'state', 'province', 'county', 'region', 'city', 'district', 'street', 'site', 'facility', 'building', 'floor', 'room', 'area', 'object']
  return order.find((scale) => scales.includes(scale)) || 'site'
}

export function cartographyScale(scale: AtlasScale): AtlasRenderScale {
  if (['cosmos', 'galaxy', 'dimension', 'system'].includes(scale)) return 'system'
  if (['building', 'floor', 'room', 'area', 'object'].includes(scale)) return 'building'
  if (['site', 'facility'].includes(scale)) return 'site'
  if (['city', 'district', 'street'].includes(scale)) return 'city'
  return 'world'
}

export function baseView(locations: AtlasLocation[]): AtlasViewBox {
  if (!locations.length) return { x: -500, y: -340, w: 1000, h: 680 }
  const xs = locations.map((item) => item.x)
  const ys = locations.map((item) => item.y)
  const minX = Math.min(...xs)
  const maxX = Math.max(...xs)
  const minY = Math.min(...ys)
  const maxY = Math.max(...ys)
  const w = Math.max(520, maxX - minX + 330)
  const h = Math.max(360, maxY - minY + 250)
  return { x: (minX + maxX) / 2 - w / 2, y: (minY + maxY) / 2 - h / 2, w, h }
}

export function titleCase(value: string) {
  return value.replaceAll('-', ' ').replace(/\b\w/g, (character) => character.toUpperCase())
}

export function routeLabel(route: AtlasRoute, byId: Map<string, AtlasLocation>) {
  return route.location_ids.map((id) => byId.get(id)?.name || id).join(' → ')
}
