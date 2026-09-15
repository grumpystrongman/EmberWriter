import { useRef } from 'react'
import type { PointerEvent as ReactPointerEvent } from 'react'

import type { AtlasCartographicFeature } from './story-atlas-types'
import type { AtlasViewBox } from './LivingAtlasCanvas'

type Props = {
  features: AtlasCartographicFeature[]
  view: AtlasViewBox
  selectedFeatureId: string
  edit: boolean
  onSelect: (id: string) => void
  onMovePoint: (featureId: string, pointIndex: number, x: number, y: number) => void
}

type PointDrag = { featureId: string; pointIndex: number; pointerId: number }

function featurePath(feature: AtlasCartographicFeature) {
  if (!feature.points.length) return ''
  if (feature.geometry_type === 'point') return ''
  const commands = feature.points.map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`).join(' ')
  return feature.geometry_type === 'polygon' ? `${commands} Z` : commands
}

function kindClass(kind: string) {
  return kind.toLowerCase().replace(/[^a-z0-9-]+/g, '-')
}

function worldPoint(event: ReactPointerEvent<SVGCircleElement>) {
  const svg = event.currentTarget.ownerSVGElement
  if (!svg) return null
  const matrix = svg.getScreenCTM()
  if (!matrix) return null
  const point = svg.createSVGPoint()
  point.x = event.clientX
  point.y = event.clientY
  const transformed = point.matrixTransform(matrix.inverse())
  return { x: transformed.x, y: transformed.y }
}

export default function LivingAtlasFeatureOverlay({ features, view, selectedFeatureId, edit, onSelect, onMovePoint }: Props) {
  const drag = useRef<PointDrag | null>(null)

  function startPoint(event: ReactPointerEvent<SVGCircleElement>, featureId: string, pointIndex: number) {
    if (!edit || event.button !== 0) return
    event.preventDefault()
    event.stopPropagation()
    drag.current = { featureId, pointIndex, pointerId: event.pointerId }
    event.currentTarget.setPointerCapture(event.pointerId)
    onSelect(featureId)
  }

  function movePoint(event: ReactPointerEvent<SVGCircleElement>) {
    if (!drag.current || drag.current.pointerId !== event.pointerId) return
    event.preventDefault()
    event.stopPropagation()
    const point = worldPoint(event)
    if (!point) return
    onMovePoint(drag.current.featureId, drag.current.pointIndex, point.x, point.y)
  }

  function endPoint(event: ReactPointerEvent<SVGCircleElement>) {
    if (drag.current?.pointerId === event.pointerId) drag.current = null
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId)
  }

  return <svg className={`atlas-feature-overlay ${edit ? 'editing' : ''}`} viewBox={`${view.x} ${view.y} ${view.w} ${view.h}`} aria-label="Editable cartographic feature layer">
    {features.map((feature) => {
      const selected = feature.id === selectedFeatureId
      const classes = `atlas-persisted-feature ${feature.geometry_type} ${feature.canon_status} kind-${kindClass(feature.kind)} ${selected ? 'selected' : ''}`
      const path = featurePath(feature)
      const first = feature.points[0]
      return <g key={feature.id} className={classes} onPointerDown={(event) => event.stopPropagation()} onClick={(event) => { event.stopPropagation(); onSelect(feature.id) }}>
        {feature.geometry_type === 'point'
          ? <circle className="atlas-feature-point" cx={first.x} cy={first.y} r={selected ? 10 : 7} />
          : <path className="atlas-feature-shape" d={path} />}
        {selected && feature.name && <text className="atlas-feature-label" x={first.x + 12} y={first.y - 10}>{feature.name}</text>}
        {selected && edit && feature.points.map((point, index) => <circle
          key={`${feature.id}-${index}`}
          className="atlas-feature-handle"
          cx={point.x}
          cy={point.y}
          r={6}
          onPointerDown={(event) => startPoint(event, feature.id, index)}
          onPointerMove={movePoint}
          onPointerUp={endPoint}
          onPointerCancel={endPoint}
        />)}
      </g>
    })}
  </svg>
}
