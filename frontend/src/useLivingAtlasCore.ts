import { useEffect, useMemo, useState } from 'react'
import type { MemoryFact } from './MemoryPanel'
import type { WorkspaceProject } from './workspace-types'
import type { AtlasCartographicFeature, AtlasConnection, AtlasGeographyResult, AtlasLocation, AtlasState, StoryAtlas, VisualAsset } from './story-atlas-types'
import type { AtlasViewBox } from './LivingAtlasCanvas'
import type { LivingAtlasRightTab } from './LivingAtlasRightDrawer'
import { atlasRequest, baseView, clamp, currentProvider, DEFAULT_PREFS, EMPTY_ATLAS, inferScale, slugify, tagValue, type AtlasPrefs } from './living-atlas-helpers'

export function useLivingAtlasCore(apiBase: string, project: WorkspaceProject, facts: MemoryFact[]) {
  const [atlas, setAtlas] = useState<StoryAtlas>(EMPTY_ATLAS)
  const [state, setState] = useState<AtlasState | null>(null)
  const [visuals, setVisuals] = useState<VisualAsset[]>([])
  const [prefs, setPrefs] = useState<AtlasPrefs>(DEFAULT_PREFS)
  const [view, setView] = useState<AtlasViewBox>({ x: -500, y: -340, w: 1000, h: 680 })
  const [scopeId, setScopeId] = useState('')
  const [selectedLocationId, setSelectedLocationId] = useState('')
  const [selectedConnectionId, setSelectedConnectionId] = useState('')
  const [selectedFeatureId, setSelectedFeatureId] = useState('')
  const [chapter, setChapter] = useState(0)
  const [character, setCharacter] = useState('')
  const [respectKnowledge, setRespectKnowledge] = useState(true)
  const [showInferred, setShowInferred] = useState(true)
  const [leftOpen, setLeftOpen] = useState(false)
  const [rightOpen, setRightOpen] = useState(false)
  const [rightTab, setRightTab] = useState<LivingAtlasRightTab>('details')
  const [dirty, setDirty] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [newPlaceName, setNewPlaceName] = useState('')

  const maxChapter = useMemo(() => Math.max(0, ...facts.map((fact) => fact.chapter_order || 0)), [facts])
  const characters = useMemo(() => {
    const names = new Set<string>()
    for (const fact of facts) if (fact.kind.startsWith('character_') || fact.kind === 'relationship') names.add(fact.subject)
    return Array.from(names).filter(Boolean).sort((a, b) => a.localeCompare(b))
  }, [facts])
  const locationById = useMemo(() => new Map(atlas.locations.map((item) => [item.id, item])), [atlas.locations])
  const locationByName = useMemo(() => new Map(atlas.locations.map((item) => [item.name.trim().toLowerCase(), item.id])), [atlas.locations])

  function parentIdFor(location: AtlasLocation) {
    const explicit = tagValue(location, 'parent:')
    if (explicit && explicit !== location.id && locationById.has(explicit)) return explicit
    const inferred = locationByName.get(location.region.trim().toLowerCase()) || ''
    return inferred !== location.id ? inferred : ''
  }

  const visibleLocations = atlas.locations.filter((item) => showInferred || item.canon_status === 'canon')
  const scopedLocations = visibleLocations.filter((item) => parentIdFor(item) === scopeId)
  const scopeLocation = scopeId ? locationById.get(scopeId) || null : null
  const selectedLocation = selectedLocationId ? locationById.get(selectedLocationId) || null : null
  const selectedConnection = atlas.connections.find((item) => item.id === selectedConnectionId) || null
  const selectedFeature = atlas.features.find((item) => item.id === selectedFeatureId) || null
  const scopedFeatures = atlas.features
    .filter((item) => item.scope_id === scopeId)
    .filter((item) => showInferred || item.canon_status === 'canon')
    .sort((a, b) => a.layer - b.layer || a.id.localeCompare(b.id))
  const scopedIds = new Set(scopedLocations.map((item) => item.id))
  const mapConnections = atlas.connections.filter((item) => scopedIds.has(item.from_id) && scopedIds.has(item.to_id) && (showInferred || item.canon_status === 'canon') && (!character || !respectKnowledge || state?.connection_known[item.id] !== false))
  const breadcrumbs: AtlasLocation[] = []
  let cursor = scopeLocation
  const seen = new Set<string>()
  while (cursor && !seen.has(cursor.id)) {
    seen.add(cursor.id)
    breadcrumbs.unshift(cursor)
    const parent = parentIdFor(cursor)
    cursor = parent ? locationById.get(parent) || null : null
  }
  const backgroundHref = atlas.map.background_asset_id ? `${apiBase}/projects/${project.slug}/visual-assets/${atlas.map.background_asset_id}` : ''

  useEffect(() => { void loadAtlas() }, [project.slug])
  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(`emberwriter.living-atlas.${project.slug}`) || 'null') as Partial<AtlasPrefs> | null
      if (saved) setPrefs((current) => ({ ...current, ...saved }))
    } catch { /* ignore damaged local preferences */ }
  }, [project.slug])
  useEffect(() => { localStorage.setItem(`emberwriter.living-atlas.${project.slug}`, JSON.stringify(prefs)) }, [project.slug, prefs])
  useEffect(() => { const next = Math.max(0, maxChapter); setChapter((current) => current === 0 ? next : Math.min(current, next || current)) }, [maxChapter])
  useEffect(() => { void loadState() }, [project.slug, chapter, character, atlas.events.length, atlas.connections.length, atlas.locations.length])

  async function loadAtlas() {
    setBusy(true); setError('')
    try {
      const [loaded, assets] = await Promise.all([
        atlasRequest<StoryAtlas>(`${apiBase}/projects/${project.slug}/atlas`),
        atlasRequest<VisualAsset[]>(`${apiBase}/projects/${project.slug}/visual-assets`),
      ])
      const normalized = { ...loaded, features: loaded.features || [] }
      setAtlas(normalized); setVisuals(assets); setDirty(false); setScopeId(''); setSelectedLocationId(''); setSelectedConnectionId(''); setSelectedFeatureId('')
      setView(baseView(normalized.locations.filter((item) => !tagValue(item, 'parent:'))))
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  async function loadState() {
    try {
      const params = new URLSearchParams({ chapter: String(chapter), character })
      setState(await atlasRequest<AtlasState>(`${apiBase}/projects/${project.slug}/atlas/state?${params}`))
    } catch (cause) { setError((cause as Error).message) }
  }

  async function saveAtlas() {
    setBusy(true); setError('')
    try {
      const saved = await atlasRequest<StoryAtlas>(`${apiBase}/projects/${project.slug}/atlas`, { method: 'PUT', body: JSON.stringify(atlas) })
      setAtlas(saved); setDirty(false); setNotice('Living Atlas saved. Topology and cartographic geometry are now persisted with the project.'); return true
    } catch (cause) { setError((cause as Error).message); return false } finally { setBusy(false) }
  }

  function updateLocation(id: string, patch: Partial<AtlasLocation>) {
    setAtlas((current) => ({ ...current, locations: current.locations.map((item) => item.id === id ? { ...item, ...patch } : item) })); setDirty(true)
  }
  function updateConnection(id: string, patch: Partial<AtlasConnection>) {
    setAtlas((current) => ({ ...current, connections: current.connections.map((item) => item.id === id ? { ...item, ...patch } : item) })); setDirty(true)
  }
  function updateFeature(id: string, patch: Partial<AtlasCartographicFeature>) {
    setAtlas((current) => ({ ...current, features: current.features.map((item) => item.id === id ? { ...item, ...patch } : item) })); setDirty(true)
  }
  function moveFeaturePoint(featureId: string, pointIndex: number, x: number, y: number) {
    setAtlas((current) => ({
      ...current,
      features: current.features.map((feature) => {
        if (feature.id !== featureId || !feature.points[pointIndex]) return feature
        const points = feature.points.map((point, index) => index === pointIndex ? { x, y } : point)
        return { ...feature, points, canon_status: feature.canon_status === 'canon' ? 'canon' : 'suggested' }
      }),
    })); setDirty(true)
  }
  function deleteFeature(id: string) {
    setAtlas((current) => ({ ...current, features: current.features.filter((item) => item.id !== id) }));
    if (selectedFeatureId === id) setSelectedFeatureId('')
    setDirty(true)
  }
  function updateMapArtwork(assetId: string) {
    setAtlas((current) => ({ ...current, map: { ...current.map, background_asset_id: assetId || null } })); setDirty(true)
  }
  function uniqueId(base: string, existing: Set<string>) {
    let value = slugify(base); let index = 2
    while (existing.has(value)) value = `${slugify(base)}-${index++}`
    return value
  }

  function addLocation() {
    const name = newPlaceName.trim(); if (!name) return
    const id = uniqueId(name, new Set(atlas.locations.map((item) => item.id)))
    const parentScale = scopeLocation ? inferScale(scopeLocation) : 'world'
    const scale = parentScale === 'building' ? 'room' : parentScale === 'city' ? 'district' : parentScale === 'region' ? 'city' : 'site'
    const tags = [`scale:${scale}`]; if (scopeId) tags.push(`parent:${scopeId}`)
    const location: AtlasLocation = { id, name, kind: scale, x: view.x + view.w / 2, y: view.y + view.h / 2, region: scopeLocation?.name || '', summary: '', terrain: [], tags, canon_status: 'suggested', position_status: 'suggested', confidence: 1, source_paths: [], known_by: [], image_asset_id: null }
    setAtlas((current) => ({ ...current, locations: [...current.locations, location] })); setSelectedLocationId(id); setSelectedFeatureId(''); setNewPlaceName(''); setDirty(true); setRightOpen(true); setRightTab('details')
  }

  function deleteLocation() {
    if (!selectedLocation) return
    const id = selectedLocation.id
    setAtlas((current) => ({ ...current, locations: current.locations.filter((item) => item.id !== id).map((item) => ({ ...item, tags: item.tags.filter((tag) => tag !== `parent:${id}`) })), connections: current.connections.filter((item) => item.from_id !== id && item.to_id !== id), features: current.features.filter((item) => item.scope_id !== id), events: current.events.filter((item) => item.target_id !== id) }))
    setSelectedLocationId(''); setDirty(true)
  }
  function deleteConnection() {
    if (!selectedConnection) return
    const id = selectedConnection.id
    setAtlas((current) => ({ ...current, connections: current.connections.filter((item) => item.id !== id), events: current.events.filter((item) => item.target_id !== id) }))
    setSelectedConnectionId(''); setDirty(true)
  }

  async function buildFromStory() {
    const provider = currentProvider(); if (!provider) { setError('Choose an AI model before building geography from the manuscript.'); return }
    setBusy(true); setError('')
    try {
      const response = await atlasRequest<{ atlas: StoryAtlas; added_locations: number; added_connections: number }>(`${apiBase}/projects/${project.slug}/atlas/bootstrap`, { method: 'POST', body: JSON.stringify({ provider, reset: false }) })
      setAtlas(response.atlas); setScopeId(''); setView(baseView(response.atlas.locations)); setDirty(false); setNotice(`Story geography refreshed: ${response.added_locations} places and ${response.added_connections} routes added.`)
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  async function suggestCartography(prompt: string) {
    const provider = currentProvider(); if (!provider) { setError('Choose an AI model before asking Ember to read the manuscript and suggest map geometry.'); return }
    setBusy(true); setError('')
    try {
      const response = await atlasRequest<AtlasGeographyResult>(`${apiBase}/projects/${project.slug}/atlas/geography/suggest`, { method: 'POST', body: JSON.stringify({ provider, scope_id: scopeId, prompt, max_features: 100 }) })
      setAtlas(response.atlas); setDirty(false); setNotice(`Ember suggested ${response.added_features} cartographic features from the manuscript. They remain suggested until you promote them.`)
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  async function importGeoJson(text: string, sourceName: string) {
    let geojson: unknown
    try { geojson = JSON.parse(text) } catch { setError('GeoJSON is not valid JSON.'); return }
    if (!geojson || typeof geojson !== 'object' || Array.isArray(geojson)) { setError('GeoJSON must be a JSON object.'); return }
    setBusy(true); setError('')
    try {
      const response = await atlasRequest<AtlasGeographyResult>(`${apiBase}/projects/${project.slug}/atlas/geography/import-geojson`, { method: 'POST', body: JSON.stringify({ geojson, scope_id: scopeId, source_name: sourceName || 'GeoJSON import', replace_imported: false }) })
      setAtlas(response.atlas); setDirty(false); setNotice(`Imported ${response.added_features} real-geography features${response.skipped_features ? `; skipped ${response.skipped_features} unsupported shapes` : ''}.`)
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  async function generateFantasy(seed: number, continents: number, detail: number) {
    setBusy(true); setError('')
    try {
      const response = await atlasRequest<AtlasGeographyResult>(`${apiBase}/projects/${project.slug}/atlas/geography/generate-fantasy`, { method: 'POST', body: JSON.stringify({ scope_id: scopeId, seed, continents, detail, replace_generated: true }) })
      setAtlas(response.atlas); setDirty(false); setNotice(`Generated ${response.added_features} editable classic-fantasy cartographic features from seed ${response.seed ?? seed}.`)
    } catch (cause) { setError((cause as Error).message) } finally { setBusy(false) }
  }

  function zoom(factor: number) {
    setView((current) => { const w = clamp(current.w * factor, 100, 200000); const h = clamp(current.h * factor, 75, 140000); return { x: current.x + (current.w - w) / 2, y: current.y + (current.h - h) / 2, w, h } })
  }
  function selectLocation(id: string) { setSelectedLocationId(id); setSelectedConnectionId(''); setSelectedFeatureId(''); setRightOpen(true); setRightTab('details') }
  function selectConnection(id: string) { setSelectedConnectionId(id); setSelectedLocationId(''); setSelectedFeatureId(''); setRightOpen(true); setRightTab('details') }
  function selectFeature(id: string) { setSelectedFeatureId(id); setSelectedLocationId(''); setSelectedConnectionId('') }
  function explore(id: string) {
    const children = visibleLocations.filter((item) => parentIdFor(item) === id)
    if (!children.length) { selectLocation(id); return }
    setScopeId(id); setSelectedLocationId(''); setSelectedConnectionId(''); setSelectedFeatureId(''); setView(baseView(children))
  }
  function goUp() { const parent = scopeLocation ? parentIdFor(scopeLocation) : ''; setScopeId(parent); setSelectedFeatureId(''); setView(baseView(visibleLocations.filter((item) => parentIdFor(item) === parent))) }
  function goRoot() { setScopeId(''); setSelectedFeatureId(''); setView(baseView(visibleLocations.filter((item) => !parentIdFor(item)))) }
  function clearMessage() { setError(''); setNotice('') }

  return { atlas, setAtlas, state, visuals, prefs, setPrefs, view, setView, scopeId, scopeLocation, breadcrumbs, selectedLocationId, selectedConnectionId, selectedFeatureId, selectedLocation, selectedConnection, selectedFeature, scopedFeatures, chapter, setChapter, character, setCharacter, characters, maxChapter, respectKnowledge, setRespectKnowledge, showInferred, setShowInferred, leftOpen, setLeftOpen, rightOpen, setRightOpen, rightTab, setRightTab, dirty, setDirty, busy, setBusy, error, setError, notice, setNotice, clearMessage, newPlaceName, setNewPlaceName, visibleLocations, scopedLocations, mapConnections, locationById, backgroundHref, parentIdFor, saveAtlas, updateLocation, updateConnection, updateFeature, moveFeaturePoint, deleteFeature, updateMapArtwork, addLocation, deleteLocation, deleteConnection, buildFromStory, suggestCartography, importGeoJson, generateFantasy, zoom, explore, selectLocation, selectConnection, selectFeature, goUp, goRoot, uniqueId }
}
