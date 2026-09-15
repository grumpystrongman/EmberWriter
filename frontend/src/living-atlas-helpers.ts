import type { AtlasLocation, AtlasRoute, StoryAtlas } from './story-atlas-types'
import type { ProviderConfig } from './workspace-types'
import type { AtlasViewBox, AtlasViewMode, AtlasVisualStyle, AtlasWorldType } from './LivingAtlasCanvas'

export type AtlasPrefs = {
  worldType: AtlasWorldType
  visualStyle: AtlasVisualStyle
  viewMode: AtlasViewMode
  showTerrain: boolean
  showRegions: boolean
  showLabels: boolean
}

export const EMPTY_ATLAS: StoryAtlas = {
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

export const DEFAULT_PREFS: AtlasPrefs = {
  worldType: 'fantasy',
  visualStyle: 'illustrated',
  viewMode: 'atlas',
  showTerrain: true,
  showRegions: true,
  showLabels: true,
}

export const SCALE_OPTIONS = ['cosmos', 'dimension', 'system', 'world', 'continent', 'region', 'city', 'district', 'site', 'building', 'room'] as const

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

export function inferScale(location: Pick<AtlasLocation, 'kind' | 'tags'>) {
  const explicit = location.tags.find((tag) => tag.startsWith('scale:'))?.slice(6) || ''
  if (SCALE_OPTIONS.includes(explicit as typeof SCALE_OPTIONS[number])) return explicit
  const kind = location.kind.toLowerCase()
  if (/room|chamber|office|dorm/.test(kind)) return 'room'
  if (/building|house|tower|spire|keep|palace|academy/.test(kind)) return 'building'
  if (/district|quarter|ward/.test(kind)) return 'district'
  if (/city|town|village/.test(kind)) return 'city'
  if (/region|county|province|kingdom|territory/.test(kind)) return 'region'
  if (/planet|world|moon/.test(kind)) return 'world'
  if (/system|star/.test(kind)) return 'system'
  if (/dimension|realm|plane/.test(kind)) return 'dimension'
  return 'site'
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
