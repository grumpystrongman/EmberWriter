import { useMemo } from 'react'

import type { BinderNode, BinderState } from './BinderPanel'
import './workspace.css'

type Props = {
  state: BinderState
  selectedId: string | null
  disabled: boolean
  onOpen: (path: string) => void
  onSelect: (nodeId: string) => void
  onUpdate: (nodeId: string, patch: Record<string, unknown>) => Promise<void>
  onClose: () => void
}

type OutlineRow = {
  node: BinderNode
  depth: number
}

function textMeta(node: BinderNode, key: string): string {
  const value = node.custom_metadata[key]
  return typeof value === 'string' ? value : ''
}

export default function OutlinerView({
  state,
  selectedId,
  disabled,
  onOpen,
  onSelect,
  onUpdate,
  onClose,
}: Props) {
  const nodes = useMemo(() => new Map(state.nodes.map((node) => [node.id, node])), [state.nodes])
  const selected = selectedId ? nodes.get(selectedId) || null : null
  const draft = state.roots.map((id) => nodes.get(id)).find((node) => node?.title === 'Draft') || null
  const scope = selected && ['folder', 'trash'].includes(selected.kind)
    ? selected
    : selected?.parent_id
      ? nodes.get(selected.parent_id) || draft
      : draft

  const children = useMemo(() => {
    const map = new Map<string, BinderNode[]>()
    for (const node of state.nodes) {
      if (!node.parent_id) continue
      const list = map.get(node.parent_id) || []
      list.push(node)
      map.set(node.parent_id, list)
    }
    for (const list of map.values()) list.sort((a, b) => a.position - b.position)
    return map
  }, [state.nodes])

  const rows = useMemo(() => {
    const result: OutlineRow[] = []
    if (!scope) return result
    function visit(parentId: string, depth: number) {
      for (const node of children.get(parentId) || []) {
        result.push({ node, depth })
        if (node.kind === 'folder') visit(node.id, depth + 1)
      }
    }
    visit(scope.id, 0)
    return result
  }, [children, scope])

  const totalWords = rows.reduce((sum, row) => sum + row.node.word_count, 0)
  const totalTarget = rows.reduce((sum, row) => sum + (row.node.target_words || 0), 0)
  const compileWords = rows
    .filter((row) => row.node.include_in_compile)
    .reduce((sum, row) => sum + row.node.word_count, 0)

  async function updateCustom(node: BinderNode, key: string, value: string) {
    if (value === textMeta(node, key)) return
    await onUpdate(node.id, {
      custom_metadata: { ...node.custom_metadata, [key]: value },
    })
  }

  return (
    <section className="binder-workspace outliner-workspace" aria-label="Outliner">
      <header className="workspace-header">
        <div>
          <small>Outliner</small>
          <h1>{scope?.title || 'Draft'}</h1>
          <p>
            {rows.length} items · {totalWords.toLocaleString()} words · {compileWords.toLocaleString()} compile words
            {totalTarget ? ` · ${totalTarget.toLocaleString()} target` : ''}
          </p>
        </div>
        <button type="button" className="quiet" onClick={onClose}>Back to Editor</button>
      </header>

      <div className="outliner-scroll">
        <table className="outliner-table">
          <thead>
            <tr>
              <th>Title</th>
              <th>Synopsis</th>
              <th>Status</th>
              <th>Label</th>
              <th>POV</th>
              <th>Location</th>
              <th>Timeline</th>
              <th>Words</th>
              <th>Target</th>
              <th>Compile</th>
              <th>Keywords</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ node, depth }) => {
              const missing = Boolean(node.custom_metadata.source_missing)
              const progress = node.target_words
                ? Math.min(999, Math.round((node.word_count / node.target_words) * 100))
                : null
              return (
                <tr
                  key={node.id}
                  className={`${selectedId === node.id ? 'selected' : ''} ${missing ? 'missing' : ''}`}
                  onClick={() => onSelect(node.id)}
                >
                  <td className="outliner-title-cell">
                    <button
                      type="button"
                      className="outliner-open"
                      style={{ paddingLeft: `${0.4 + depth * 1.05}rem` }}
                      onClick={(event) => {
                        event.stopPropagation()
                        onSelect(node.id)
                        if (node.path && !missing) onOpen(node.path)
                      }}
                    >
                      <span>{node.kind === 'folder' ? '▸' : '▤'}</span>
                      <strong>{node.title}</strong>
                    </button>
                  </td>
                  <td>
                    <textarea
                      defaultValue={node.synopsis}
                      placeholder="Synopsis"
                      disabled={disabled}
                      onClick={(event) => event.stopPropagation()}
                      onBlur={(event) => {
                        if (event.target.value !== node.synopsis) void onUpdate(node.id, { synopsis: event.target.value })
                      }}
                    />
                  </td>
                  <td><input defaultValue={node.status} disabled={disabled} onClick={(event) => event.stopPropagation()} onBlur={(event) => { if (event.target.value !== node.status) void onUpdate(node.id, { status: event.target.value }) }} /></td>
                  <td><input defaultValue={node.label} disabled={disabled} onClick={(event) => event.stopPropagation()} onBlur={(event) => { if (event.target.value !== node.label) void onUpdate(node.id, { label: event.target.value }) }} /></td>
                  <td><input defaultValue={textMeta(node, 'pov')} disabled={disabled} onClick={(event) => event.stopPropagation()} onBlur={(event) => void updateCustom(node, 'pov', event.target.value.trim())} /></td>
                  <td><input defaultValue={textMeta(node, 'location')} disabled={disabled} onClick={(event) => event.stopPropagation()} onBlur={(event) => void updateCustom(node, 'location', event.target.value.trim())} /></td>
                  <td><input defaultValue={textMeta(node, 'timeline')} disabled={disabled} onClick={(event) => event.stopPropagation()} onBlur={(event) => void updateCustom(node, 'timeline', event.target.value.trim())} /></td>
                  <td className="number-cell">{missing ? 'Missing' : node.word_count.toLocaleString()}</td>
                  <td>
                    <div className="target-cell">
                      <input
                        type="number"
                        min="0"
                        defaultValue={node.target_words ?? ''}
                        disabled={disabled}
                        onClick={(event) => event.stopPropagation()}
                        onBlur={(event) => {
                          const value = event.target.value ? Number(event.target.value) : null
                          if (value !== node.target_words) void onUpdate(node.id, { target_words: value })
                        }}
                      />
                      {progress !== null && <small>{progress}%</small>}
                    </div>
                  </td>
                  <td className="compile-cell">
                    <input
                      type="checkbox"
                      checked={node.include_in_compile}
                      disabled={disabled}
                      onClick={(event) => event.stopPropagation()}
                      onChange={(event) => void onUpdate(node.id, { include_in_compile: event.target.checked })}
                    />
                  </td>
                  <td>
                    <input
                      defaultValue={node.keywords.join(', ')}
                      disabled={disabled}
                      onClick={(event) => event.stopPropagation()}
                      onBlur={(event) => {
                        const keywords = event.target.value.split(',').map((item) => item.trim()).filter(Boolean)
                        if (keywords.join('\u0000') !== node.keywords.join('\u0000')) void onUpdate(node.id, { keywords })
                      }}
                    />
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </section>
  )
}
