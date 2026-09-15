export type AtlasStatus = 'canon' | 'inferred' | 'suggested'
export type AtlasPreference = 'fastest' | 'safest' | 'balanced' | 'dramatic' | 'lore' | 'relationship'
export type AtlasEventAction = 'connection_open' | 'connection_close' | 'location_reveal' | 'location_control' | 'note'
export type AtlasGeometryType = 'point' | 'line' | 'polygon'

export type AtlasTravelProfile = {
  speed_mph: number
  hours_per_day: number
}

export type AtlasPoint = { x: number; y: number }

export type AtlasCartographicFeature = {
  id: string
  name: string
  kind: string
  geometry_type: AtlasGeometryType
  points: AtlasPoint[]
  scope_id: string
  layer: number
  canon_status: AtlasStatus
  confidence: number
  source: string
  source_ref: string
  source_crs: string
  source_paths: string[]
  notes: string
  properties: Record<string, string | number | boolean>
}

export type AtlasLocation = {
  id: string
  name: string
  kind: string
  x: number
  y: number
  region: string
  summary: string
  terrain: string[]
  tags: string[]
  canon_status: AtlasStatus
  position_status: AtlasStatus
  confidence: number
  source_paths: string[]
  known_by: string[]
  image_asset_id: string | null
}

export type AtlasConnection = {
  id: string
  from_id: string
  to_id: string
  name: string
  distance: number
  bidirectional: boolean
  mode_multipliers: Record<string, number>
  terrain_multiplier: number
  risk: number
  drama: number
  lore: number
  relationship: number
  active_from_chapter: number
  active_until_chapter: number | null
  canon_status: AtlasStatus
  confidence: number
  known_by: string[]
  source_paths: string[]
  notes: string
}

export type AtlasEvent = {
  id: string
  chapter: number
  action: AtlasEventAction
  target_id: string
  summary: string
  value: string
  source_path: string
}

export type StoryAtlas = {
  schema_version: number
  map: { title: string; units: string; background_asset_id: string | null }
  travel_profiles: Record<string, AtlasTravelProfile>
  locations: AtlasLocation[]
  connections: AtlasConnection[]
  features: AtlasCartographicFeature[]
  events: AtlasEvent[]
}

export type AtlasState = {
  chapter: number
  character: string
  connection_open: Record<string, boolean>
  location_known: Record<string, boolean>
  connection_known: Record<string, boolean>
  location_control: Record<string, string>
  notes: Array<{ id: string; target_id: string; chapter: number; summary: string; value: string }>
}

export type AtlasRouteSegment = {
  connection_id: string
  from_id: string
  to_id: string
  name: string
  distance: number
  travel_hours: number
  risk: number
  drama: number
  lore: number
  relationship: number
}

export type AtlasRoute = {
  preference: AtlasPreference
  mode: string
  origin_id: string
  destination_id: string
  chapter: number
  character: string
  segments: AtlasRouteSegment[]
  location_ids: string[]
  total_distance: number
  total_hours: number
  total_days: number
  risk_score: number
  drama_score: number
  lore_score: number
  relationship_score: number
  warnings: string[]
}

export type AtlasRouteCompare = {
  routes: AtlasRoute[]
  unavailable_preferences: AtlasPreference[]
}

export type AtlasAdvice = {
  summary: string
  ideas: Array<{
    title: string
    rationale: string
    story_effect: string
    route_ids: string[]
    proposed_changes: string[]
  }>
  continuity_warnings: string[]
}

export type AtlasGeographyResult = {
  atlas: StoryAtlas
  added_features: number
  skipped_features?: number
  seed?: number
  warnings?: string[]
}

export type VisualAsset = {
  asset_id: string
  title: string
  kind: string
  relative_path: string
  source: string
  prompt: string
  negative_prompt: string
  width: number
  height: number
  generated_at: string
  canon_status: 'reference' | 'concept' | 'canonical'
  linked_entities: string[]
  notes: string
  reference_asset_id: string | null
}
