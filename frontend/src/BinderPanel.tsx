import { useEffect, useMemo, useState } from 'react'

import CorkboardView from './CorkboardView'
import OutlinerView from './OutlinerView'
import './binder.css'

export type BinderNodeKind = 'folder' | 'document' | 'research' | 'character' | 'location' | 'note' | 'trash'

export type BinderNode = {
  id: string
  title: string
  kind: BinderNodeKind
  parent_id: string | null
  position: number
  path: string | null
  synopsis: string
  label: string
  status: string
  keywords: string[]
  include_in_compile: boolean
  target_words: number | null
  custom_metadata: Record<string, unknown>
  previous_parent_id: string | null
  created_at: string
  updated_at: string
  word_count: number
}

export type BinderCollection = {
  id: string
  name: string
  node_ids: string[]
  query: string
  created_at: string
  updated_at: string
}

export type BinderState = {
  schema_version: number
  roots: string[]
  nodes: BinderNode[]
  collections: BinderCollection[]
}

type CreateInput = {
  title: string
  kind: BinderNodeKind
  parent_id: string | null
}

type Props = {
  apiBase: string
  slug: string
  state: BinderState
  activePath: string
  disabled: boolean
  onOpen: (path: string) => void
  onCreate: (input: CreateInput) => Promise<void>
  onUpdate: (nodeId: string, patch: Record<string, unknown>) => Promise<void>
  onReorder: (parentId: string | null, nodeIds: string[]) => Promise<void>
  onTrash: (nodeId: string) => Promise<void>
  onRestore: (nodeId: string) => Promise<void>
  onSync: () => Promise<void>
}

type WorkspaceMode = 'tree' | 'corkboard' | 'outliner'

function icon(kind: BinderNodeKind) {
  if (kind === 'trash') return '⌫'
  if (kind === 'folder') return '▸'
  if (kind === 'character') return '◉'
  if (kind === 'location') return '⌖'
  if (kind === 'research') return '◇'
  if (kind === 'note') return '✎'
  return '▤'
}

function textMeta(node: BinderNode, key: string): string {
  const value = node.custom_metadata[key]
  return typeof value === 'string' ? value : ''
}

export default function BinderPanel({
  apiBase,
  slug,
  state,
  activePath,
  disabled,
  onOpen,
  onCreate,
  onUpdate,
  onReorder,
  onTrash,
  onRestore,
  onSync,
}: Props) {
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set(state.roots))
  const [selectedId, setSelectedId] = useState<string | null>(state.roots[0] || null)
  const [newTitle, setNewTitle] = useState('')
  const [newKind, setNewKind] = useState<BinderNodeKind>('document')
  const [workspace, setWorkspace] = useState<WorkspaceMode>('tree')
  const nodes = useMemo(() => new Map(state.nodes.map((node) => [node.id, node])), [state.nodes])
  const selected = selectedId ? nodes.get(selectedId) || null : null

  const childrenByParent = useMemo(() => {
    const map = new Map<string | null, BinderNode[]>()
    for (const node of state.nodes) {
      const list = map.get(node.parent_id) || []
      list.push(node)
      map.set(node.parent_id, list)
    }
    for (const list of map.values()) list.sort((a, b) => a.position - b.position)
    return map
  }, [state.nodes])

  useEffect(() => {
    setExpanded((current) => {
      const next = new Set(current)
      for (const root of state.roots) next.add(root)
      return next
    })
    if (selectedId && !nodes.has(selectedId)) setSelectedId(state.roots[0] || null)
  }, [state.roots, nodes, selectedId])

  useEffect(() => {
    setSelectedId(state.roots[0] || null)
    setWorkspace('tree')
  }, [slug])

  function toggle(nodeId: string) {
    setExpanded((current) => {
      const next = new Set(current)
      if (next.has(nodeId)) next.delete(nodeId)
      else next.add(nodeId)
      return next
    })
  }

  function select(node: BinderNode) {
    setSelectedId(node.id)
    if (node.path && !node.custom_metadata.source_missing) onOpen(node.path)
  }

  function openFromWorkspace(path: string) {
    setWorkspace('tree')
    onOpen(path)
  }

  async function create() {
    const title = newTitle.trim()
    if (!title) return
    let parentId = selected?.id || state.roots[0] || null
    if (selected && !['folder', 'trash'].includes(selected.kind)) parentId = selected.parent_id
    await onCreate({ title, kind: newKind, parent_id: parentId })
    if (parentId) setExpanded((current) => new Set(current).add(parentId))
    setNewTitle('')
  }

  async function move(node: BinderNode, direction: -1 | 1) {
    const siblings = childrenByParent.get(node.parent_id) || []
    const index = siblings.findIndex((item) => item.id === node.id)
    const nextIndex = index + direction
    if (index < 0 || nextIndex < 0 || nextIndex >= siblings.length) return
    const reordered = siblings.map((item) => item.id)
    ;[reordered[index], reordered[nextIndex]] = [reordered[nextIndex], reordered[index]]
    await onReorder(node.parent_id, reordered)
  }

  async function updateCustomMetadata(node: BinderNode, key: string, value: string) {
    if (value === textMeta(node, key)) return
    await onUpdate(node.id, {
      custom_metadata: { ...node.custom_metadata, [key]: value },
    })
  }

  function renderNode(node: BinderNode, depth: number): React.ReactNode {
    const children = childrenByParent.get(node.id) || []
    const canExpand = children.length > 0 || node.kind === 'folder' || node.kind === 'trash'
    const isExpanded = expanded.has(node.id)
    const missing = Boolean(node.custom_metadata.source_missing)
    return (
      <div key={node.id}>
        <div
          className={`binder-row ${selectedId === node.id ? 'selected' : ''} ${activePath && node.path === activePath ? 'active' : ''} ${missing ? 'missing' : ''}`}
          style={{ paddingLeft: `${0.35 + depth * 0.9}rem` }}
        >
          <button
            type="button"
            className="binder-disclosure"
            onClick={() => canExpand && toggle(node.id)}
            aria-label={isExpanded ? 'Collapse' : 'Expand'}
          >
            {canExpand ? (isExpanded ? '⌄' : '›') : ''}
          </button>
          <button type="button" className="binder-node-button" onClick={() => select(node)}>
            <span className="binder-icon">{icon(node.kind)}</span>
            <span className="binder-node-copy">
              <strong>{node.title}</strong>
              {(node.word_count > 0 || missing) && <small>{missing ? 'source missing' : `${node.word_count.toLocaleString()} words`}</small>}
            </span>
          </button>
        </div>
        {canExpand && isExpanded && children.map((child) => renderNode(child, depth + 1))}
      </div>
    )
  }

  const rootNodes = state.roots.map((id) => nodes.get(id)).filter((node): node is BinderNode => Boolean(node))
  const trashRoot = rootNodes.find((node) => node.kind === 'trash')
  const selectedIsInTrash = selected?.parent_id === trashRoot?.id
  const selectedIsRoot = Boolean(selected && state.roots.includes(selected.id))

  return (
    <div className="binder-panel">
      <div className="binder-heading">
        <div><strong>Binder</strong><small>{state.nodes.length} items</small></div>
        <button type="button" className="quiet" disabled={disabled} onClick={() => void onSync()}>Sync</button>
      </div>

      <div className="binder-view-tabs" aria-label="Binder views">
        <button type="button" className={workspace === 'tree' ? 'active' : ''} onClick={() => setWorkspace('tree')}>Tree</button>
        <button type="button" className={workspace === 'corkboard' ? 'active' : ''} onClick={() => setWorkspace('corkboard')}>Corkboard</button>
        <button type="button" className={workspace === 'outliner' ? 'active' : ''} onClick={() => setWorkspace('outliner')}>Outliner</button>
      </div>

      <div className="binder-tree">
        {rootNodes.map((node) => renderNode(node, 0))}
      </div>

      <div className="binder-create">
        <select value={newKind} onChange={(event) => setNewKind(event.target.value as BinderNodeKind)}>
          <option value="document">Document</option>
          <option value="folder">Folder</option>
          <option value="research">Research</option>
          <option value="character">Character</option>
          <option value="location">Location</option>
          <option value="note">Note</option>
        </select>
        <input
          value={newTitle}
          onChange={(event) => setNewTitle(event.target.value)}
          onKeyDown={(event) => { if (event.key === 'Enter') void create() }}
          placeholder="New Binder item"
        />
        <button type="button" disabled={disabled || !newTitle.trim()} onClick={() => void create()}>+</button>
      </div>

      {selected && (
        <details className="binder-inspector" open={!selectedIsRoot}>
          <summary>Inspector <small>{selected.kind}</small></summary>
          {!selectedIsRoot && <div key={`${selected.id}-${selected.updated_at}`}>
            <label>Title</label>
            <input
              defaultValue={selected.title}
              onBlur={(event) => {
                const value = event.target.value.trim()
                if (value && value !== selected.title) void onUpdate(selected.id, { title: value })
              }}
            />
            <label>Synopsis</label>
            <textarea
              defaultValue={selected.synopsis}
              onBlur={(event) => {
                if (event.target.value !== selected.synopsis) void onUpdate(selected.id, { synopsis: event.target.value })
              }}
              placeholder="What this document or scene is for…"
            />
            <div className="binder-meta-grid">
              <label>Status<input defaultValue={selected.status} onBlur={(event) => { if (event.target.value !== selected.status) void onUpdate(selected.id, { status: event.target.value }) }} /></label>
              <label>Label<input defaultValue={selected.label} onBlur={(event) => { if (event.target.value !== selected.label) void onUpdate(selected.id, { label: event.target.value }) }} /></label>
            </div>
            <div className="binder-meta-grid">
              <label>POV<input defaultValue={textMeta(selected, 'pov')} onBlur={(event) => void updateCustomMetadata(selected, 'pov', event.target.value.trim())} /></label>
              <label>Location<input defaultValue={textMeta(selected, 'location')} onBlur={(event) => void updateCustomMetadata(selected, 'location', event.target.value.trim())} /></label>
            </div>
            <div className="binder-meta-grid">
              <label>Timeline<input defaultValue={textMeta(selected, 'timeline')} onBlur={(event) => void updateCustomMetadata(selected, 'timeline', event.target.value.trim())} placeholder="Day 3 · Night" /></label>
              <label>Scene type<input defaultValue={textMeta(selected, 'scene_type')} onBlur={(event) => void updateCustomMetadata(selected, 'scene_type', event.target.value.trim())} placeholder="Action, reveal…" /></label>
            </div>
            <label>Keywords</label>
            <input
              defaultValue={selected.keywords.join(', ')}
              onBlur={(event) => {
                const keywords = event.target.value.split(',').map((item) => item.trim()).filter(Boolean)
                if (keywords.join('\u0000') !== selected.keywords.join('\u0000')) void onUpdate(selected.id, { keywords })
              }}
              placeholder="POV, thread, location…"
            />
            <div className="binder-meta-grid">
              <label>Word target<input type="number" min="0" defaultValue={selected.target_words ?? ''} onBlur={(event) => { const value = event.target.value ? Number(event.target.value) : null; if (value !== selected.target_words) void onUpdate(selected.id, { target_words: value }) }} /></label>
              <label className="binder-check"><input type="checkbox" checked={selected.include_in_compile} onChange={(event) => void onUpdate(selected.id, { include_in_compile: event.target.checked })} />Compile</label>
            </div>
            {selected.path && <small className="binder-path">{selected.path}</small>}
            <div className="binder-actions">
              <button type="button" disabled={disabled} onClick={() => void move(selected, -1)}>↑</button>
              <button type="button" disabled={disabled} onClick={() => void move(selected, 1)}>↓</button>
              {selectedIsInTrash
                ? <button type="button" disabled={disabled} onClick={() => void onRestore(selected.id)}>Restore</button>
                : <button type="button" disabled={disabled} onClick={() => void onTrash(selected.id)}>Trash</button>}
            </div>
          </div>}
        </details>
      )}

      {state.collections.length > 0 && (
        <details className="binder-collections">
          <summary>Collections <small>{state.collections.length}</small></summary>
          {state.collections.map((collection) => (
            <div className="binder-collection" key={collection.id}>
              <strong>{collection.name}</strong>
              <small>{collection.node_ids.length} item{collection.node_ids.length === 1 ? '' : 's'}{collection.query ? ` · ${collection.query}` : ''}</small>
            </div>
          ))}
        </details>
      )}

      {workspace === 'corkboard' && (
        <CorkboardView
          apiBase={apiBase}
          slug={slug}
          state={state}
          selectedId={selectedId}
          disabled={disabled}
          onOpen={openFromWorkspace}
          onSelect={setSelectedId}
          onUpdate={onUpdate}
          onReorder={onReorder}
          onClose={() => setWorkspace('tree')}
        />
      )}

      {workspace === 'outliner' && (
        <OutlinerView
          state={state}
          selectedId={selectedId}
          disabled={disabled}
          onOpen={openFromWorkspace}
          onSelect={setSelectedId}
          onUpdate={onUpdate}
          onClose={() => setWorkspace('tree')}
        />
      )}
    </div>
  )
}
