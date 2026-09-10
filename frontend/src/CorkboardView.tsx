import { useMemo, useState, type DragEvent } from 'react'

import type { BinderNode, BinderState } from './BinderPanel'
import './workspace.css'

type Props = {
  state: BinderState
  selectedId: string | null
  disabled: boolean
  onOpen: (path: string) => void
  onSelect: (nodeId: string) => void
  onUpdate: (nodeId: string, patch: Record<string, unknown>) => Promise<void>
  onReorder: (parentId: string | null, nodeIds: string[]) => Promise<void>
  onClose: () => void
}

function textMeta(node: BinderNode, key: string): string {
  const value = node.custom_metadata[key]
  return typeof value === 'string' ? value : ''
}

export default function CorkboardView({
  state,
  selectedId,
  disabled,
  onOpen,
  onSelect,
  onUpdate,
  onReorder,
  onClose,
}: Props) {
  const [draggedId, setDraggedId] = useState<string | null>(null)
  const nodes = useMemo(() => new Map(state.nodes.map((node) => [node.id, node])), [state.nodes])
  const selected = selectedId ? nodes.get(selectedId) || null : null
  const scope = selected && ['folder', 'trash'].includes(selected.kind)
    ? selected
    : selected?.parent_id
      ? nodes.get(selected.parent_id) || null
      : state.roots.map((id) => nodes.get(id)).find((node) => node?.title === 'Draft') || null

  const cards = useMemo(
    () => state.nodes
      .filter((node) => node.parent_id === scope?.id)
      .sort((a, b) => a.position - b.position),
    [scope?.id, state.nodes],
  )

  async function dropOn(targetId: string) {
    if (!draggedId || draggedId === targetId || !scope) return
    const ids = cards.map((card) => card.id)
    const from = ids.indexOf(draggedId)
    const to = ids.indexOf(targetId)
    if (from < 0 || to < 0) return
    ids.splice(from, 1)
    ids.splice(to, 0, draggedId)
    setDraggedId(null)
    await onReorder(scope.id, ids)
  }

  function dragOver(event: DragEvent<HTMLDivElement>) {
    event.preventDefault()
    event.dataTransfer.dropEffect = 'move'
  }

  async function updateCustom(node: BinderNode, key: string, value: string) {
    const current = textMeta(node, key)
    if (value === current) return
    await onUpdate(node.id, {
      custom_metadata: { ...node.custom_metadata, [key]: value },
    })
  }

  const totalWords = cards.reduce((sum, card) => sum + card.word_count, 0)
  const included = cards.filter((card) => card.include_in_compile).length

  return (
    <section className="binder-workspace" aria-label="Corkboard">
      <header className="workspace-header">
        <div>
          <small>Corkboard</small>
          <h1>{scope?.title || 'Draft'}</h1>
          <p>{cards.length} cards · {totalWords.toLocaleString()} words · {included} compile</p>
        </div>
        <button type="button" className="quiet" onClick={onClose}>Back to Editor</button>
      </header>

      {cards.length === 0 ? (
        <div className="workspace-empty">
          <strong>No cards in this Binder section.</strong>
          <span>Create or move documents into this folder from the Binder.</span>
        </div>
      ) : (
        <div className="corkboard-grid">
          {cards.map((card, index) => {
            const missing = Boolean(card.custom_metadata.source_missing)
            const pov = textMeta(card, 'pov')
            const location = textMeta(card, 'location')
            return (
              <div
                key={card.id}
                className={`index-card ${selectedId === card.id ? 'selected' : ''} ${draggedId === card.id ? 'dragging' : ''}`}
                draggable={!disabled}
                onDragStart={(event) => {
                  setDraggedId(card.id)
                  event.dataTransfer.effectAllowed = 'move'
                  event.dataTransfer.setData('text/plain', card.id)
                }}
                onDragEnd={() => setDraggedId(null)}
                onDragOver={dragOver}
                onDrop={() => void dropOn(card.id)}
                onClick={() => onSelect(card.id)}
                onDoubleClick={() => { if (card.path && !missing) onOpen(card.path) }}
              >
                <div className="card-topline">
                  <span className="card-number">{index + 1}</span>
                  <span>{card.kind}</span>
                  {card.label && <span className="card-label">{card.label}</span>}
                </div>
                <input
                  className="card-title"
                  defaultValue={card.title}
                  aria-label="Card title"
                  onClick={(event) => event.stopPropagation()}
                  onBlur={(event) => {
                    const value = event.target.value.trim()
                    if (value && value !== card.title) void onUpdate(card.id, { title: value })
                  }}
                />
                <textarea
                  className="card-synopsis"
                  defaultValue={card.synopsis}
                  placeholder="Scene synopsis…"
                  onClick={(event) => event.stopPropagation()}
                  onBlur={(event) => {
                    if (event.target.value !== card.synopsis) void onUpdate(card.id, { synopsis: event.target.value })
                  }}
                />
                <div className="card-meta-row">
                  <input
                    defaultValue={pov}
                    placeholder="POV"
                    onClick={(event) => event.stopPropagation()}
                    onBlur={(event) => void updateCustom(card, 'pov', event.target.value.trim())}
                  />
                  <input
                    defaultValue={location}
                    placeholder="Location"
                    onClick={(event) => event.stopPropagation()}
                    onBlur={(event) => void updateCustom(card, 'location', event.target.value.trim())}
                  />
                </div>
                <div className="card-footer">
                  <span>{missing ? 'source missing' : `${card.word_count.toLocaleString()} words`}</span>
                  <span>{card.status || 'No status'}</span>
                  {card.target_words ? <span>{Math.min(999, Math.round((card.word_count / card.target_words) * 100))}% target</span> : null}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </section>
  )
}
