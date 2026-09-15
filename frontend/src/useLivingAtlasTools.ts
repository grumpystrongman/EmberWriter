import { useMemo, useState } from 'react'
import type { Dispatch, SetStateAction } from 'react'
import type { WorkspaceProject } from './workspace-types'
import type { AtlasAdvice, AtlasConnection, AtlasEventAction, AtlasLocation, AtlasPreference, AtlasRoute, AtlasRouteCompare, StoryAtlas } from './story-atlas-types'
import { atlasRequest, currentProvider } from './living-atlas-helpers'

type CoreBridge = {
  apiBase: string
  project: WorkspaceProject
  atlas: StoryAtlas
  setAtlas: Dispatch<SetStateAction<StoryAtlas>>
  locationById: Map<string, AtlasLocation>
  chapter: number
  character: string
  respectKnowledge: boolean
  dirty: boolean
  setDirty: (value: boolean) => void
  busy: boolean
  setBusy: (value: boolean) => void
  setError: (value: string) => void
  setNotice: (value: string) => void
  saveAtlas: () => Promise<boolean>
  uniqueId: (base: string, existing: Set<string>) => string
  selectConnection: (id: string) => void
}

export function useLivingAtlasTools(core: CoreBridge) {
  const [routeOrigin, setRouteOrigin] = useState('')
  const [routeDestination, setRouteDestination] = useState('')
  const [travelMode, setTravelMode] = useState('walk')
  const [newRouteDistance, setNewRouteDistance] = useState('10')
  const [routes, setRoutes] = useState<AtlasRoute[]>([])
  const [activeRoute, setActiveRoute] = useState<AtlasPreference | ''>('')
  const [eventAction, setEventAction] = useState<AtlasEventAction>('connection_close')
  const [eventTarget, setEventTarget] = useState('')
  const [eventChapter, setEventChapter] = useState('0')
  const [eventValue, setEventValue] = useState('')
  const [eventSummary, setEventSummary] = useState('')
  const [advicePrompt, setAdvicePrompt] = useState('Audit this journey for spatial, travel-time, and world-state continuity problems.')
  const [advice, setAdvice] = useState<AtlasAdvice | null>(null)

  const highlightedConnectionIds = useMemo(
    () => new Set(routes.find((item) => item.preference === activeRoute)?.segments.map((item) => item.connection_id) || []),
    [routes, activeRoute],
  )
  const eventOptions = useMemo(
    () => eventAction.startsWith('connection_')
      ? core.atlas.connections.map((item) => ({ id: item.id, name: item.name }))
      : core.atlas.locations.map((item) => ({ id: item.id, name: item.name })),
    [eventAction, core.atlas.connections, core.atlas.locations],
  )

  function initializeRoutes() {
    if (routeOrigin || !core.atlas.locations.length) return
    setRouteOrigin(core.atlas.locations[0]?.id || '')
    setRouteDestination(core.atlas.locations[1]?.id || '')
  }

  function addConnection() {
    if (!routeOrigin || !routeDestination || routeOrigin === routeDestination) return
    const distance = Number(newRouteDistance)
    if (!Number.isFinite(distance) || distance <= 0) { core.setError('Route distance must be greater than zero.'); return }
    const from = core.locationById.get(routeOrigin)
    const to = core.locationById.get(routeDestination)
    const name = `${from?.name || routeOrigin} → ${to?.name || routeDestination}`
    const id = core.uniqueId(name, new Set(core.atlas.connections.map((item) => item.id)))
    const connection: AtlasConnection = {
      id,
      from_id: routeOrigin,
      to_id: routeDestination,
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
    core.setAtlas((current) => ({ ...current, connections: [...current.connections, connection] }))
    core.setDirty(true)
    core.selectConnection(id)
  }

  async function compareRoutes() {
    if (!routeOrigin || !routeDestination || routeOrigin === routeDestination) { core.setError('Choose two different locations for route planning.'); return }
    if (core.dirty && !(await core.saveAtlas())) return
    core.setBusy(true); core.setError('')
    try {
      const response = await atlasRequest<AtlasRouteCompare>(`${core.apiBase}/projects/${core.project.slug}/atlas/routes/compare`, {
        method: 'POST',
        body: JSON.stringify({ origin_id: routeOrigin, destination_id: routeDestination, mode: travelMode, chapter: core.chapter, character: core.character, respect_character_knowledge: core.respectKnowledge }),
      })
      setRoutes(response.routes)
      setActiveRoute(response.routes[0]?.preference || '')
      if (!response.routes.length) core.setNotice('No route is available under the current chapter and character-knowledge filters.')
    } catch (cause) { core.setError((cause as Error).message) } finally { core.setBusy(false) }
  }

  function addEvent() {
    const chapter = Math.max(0, Number.parseInt(eventChapter, 10) || 0)
    if (!eventTarget) return
    const id = core.uniqueId(`${eventAction}-${eventTarget}-${chapter}`, new Set(core.atlas.events.map((item) => item.id)))
    core.setAtlas((current) => ({
      ...current,
      events: [...current.events, { id, chapter, action: eventAction, target_id: eventTarget, summary: eventSummary.trim(), value: eventValue.trim(), source_path: '' }],
    }))
    setEventSummary(''); setEventValue(''); core.setDirty(true)
  }

  function deleteEvent(id: string) {
    core.setAtlas((current) => ({ ...current, events: current.events.filter((item) => item.id !== id) }))
    core.setDirty(true)
  }

  async function askAtlas() {
    const provider = currentProvider()
    if (!provider) { core.setError('Choose an AI model before asking the Spatial Story Director.'); return }
    if (core.dirty && !(await core.saveAtlas())) return
    core.setBusy(true); core.setError('')
    try {
      setAdvice(await atlasRequest<AtlasAdvice>(`${core.apiBase}/projects/${core.project.slug}/atlas/advise`, {
        method: 'POST',
        body: JSON.stringify({ prompt: advicePrompt, provider, chapter: core.chapter, character: core.character, origin_id: routeOrigin, destination_id: routeDestination, mode: travelMode, preference: activeRoute || 'dramatic' }),
      }))
    } catch (cause) { core.setError((cause as Error).message) } finally { core.setBusy(false) }
  }

  function changeEventAction(value: AtlasEventAction) { setEventAction(value); setEventTarget('') }

  return { routeOrigin, setRouteOrigin, routeDestination, setRouteDestination, travelMode, setTravelMode, newRouteDistance, setNewRouteDistance, routes, activeRoute, setActiveRoute, highlightedConnectionIds, eventAction, changeEventAction, eventTarget, setEventTarget, eventChapter, setEventChapter, eventValue, setEventValue, eventSummary, setEventSummary, eventOptions, advicePrompt, setAdvicePrompt, advice, initializeRoutes, addConnection, compareRoutes, addEvent, deleteEvent, askAtlas }
}
