import { useState } from 'react'

import WriteBookmarks from './WriteBookmarks'
import { openProjectPath, projectFiles, readProjectFile, saveProjectFile } from './write-workspace-store'

type SearchHit = { path: string; score: number; excerpt: string }
type Props = { slug: string; currentPath: string; onClose: () => void }
const API = 'http://127.0.0.1:8000/api'

function escaped(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

export default function WriteSearchDrawer({ slug, currentPath, onClose }: Props) {
  const [query, setQuery] = useState('')
  const [replacement, setReplacement] = useState('')
  const [hits, setHits] = useState<SearchHit[]>([])
  const [preview, setPreview] = useState<Array<{ path: string; count: number }>>([])
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState('')

  async function search() {
    if (!query.trim()) return
    setBusy(true)
    try {
      const response = await fetch(`${API}/projects/${slug}/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: query.trim(), limit: 30 }),
      })
      const body = await response.json()
      if (!response.ok) throw new Error(body.detail || `${response.status} ${response.statusText}`)
      setHits(body as SearchHit[])
      setStatus(`${(body as SearchHit[]).length} search result${(body as SearchHit[]).length === 1 ? '' : 's'}`)
    } catch (cause) {
      setStatus((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function previewReplace() {
    if (!query.trim()) return
    setBusy(true)
    try {
      const matcher = new RegExp(escaped(query.trim()), 'gi')
      const files = (await projectFiles(slug)).filter((path) => /\.(md|txt)$/i.test(path))
      const next: Array<{ path: string; count: number }> = []
      for (const path of files) {
        const text = await readProjectFile(slug, path)
        const count = [...text.matchAll(matcher)].length
        if (count) next.push({ path, count })
      }
      setPreview(next)
      setStatus(`${next.reduce((sum, item) => sum + item.count, 0)} replacement${next.reduce((sum, item) => sum + item.count, 0) === 1 ? '' : 's'} across ${next.length} file${next.length === 1 ? '' : 's'}`)
    } catch (cause) {
      setStatus((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function applyReplace() {
    if (!query.trim() || !preview.length || busy) return
    setBusy(true)
    try {
      const checkpoint = await fetch(`${API}/projects/${slug}/project-checkpoints`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ label: `Before replace: ${query.trim().slice(0, 80)}`, note: `Project-wide replace with “${replacement}”` }),
      })
      if (!checkpoint.ok) throw new Error(`Could not create safety checkpoint (${checkpoint.status})`)
      const matcher = new RegExp(escaped(query.trim()), 'gi')
      for (const item of preview) {
        const text = await readProjectFile(slug, item.path)
        await saveProjectFile(slug, item.path, text.replace(matcher, replacement))
      }
      setStatus(`Applied ${preview.reduce((sum, item) => sum + item.count, 0)} replacements. Safety checkpoint created.`)
      setPreview([])
      await search()
    } catch (cause) {
      setStatus(`Replace stopped: ${(cause as Error).message}`)
    } finally {
      setBusy(false)
    }
  }

  return <aside className="write-search-drawer">
    <header><div><small>PROJECT NAVIGATION</small><strong>Search, Replace & Bookmarks</strong></div><button type="button" onClick={onClose}>×</button></header>
    <div className="write-search-controls"><input value={query} onChange={(event) => { setQuery(event.target.value); setPreview([]) }} placeholder="Search project" onKeyDown={(event) => { if (event.key === 'Enter') void search() }} /><button type="button" onClick={() => void search()} disabled={!query.trim() || busy}>Search</button></div>
    <div className="write-replace-controls"><input value={replacement} onChange={(event) => setReplacement(event.target.value)} placeholder="Replace with" /><button type="button" onClick={() => void previewReplace()} disabled={!query.trim() || busy}>Preview project replace</button>{preview.length > 0 && <button type="button" className="danger" onClick={() => void applyReplace()} disabled={busy}>Apply with checkpoint</button>}</div>
    {status && <div className="write-search-status">{status}</div>}
    {preview.length > 0 && <div className="write-replace-preview"><strong>Replacement preview</strong>{preview.map((item) => <div key={item.path}><span>{item.path}</span><b>{item.count}</b></div>)}</div>}
    <div className="write-search-results">{hits.map((hit) => <button type="button" key={`${hit.path}:${hit.excerpt}`} onClick={() => void openProjectPath(slug, hit.path)}><strong>{hit.path}</strong><p>{hit.excerpt}</p></button>)}</div>
    <WriteBookmarks slug={slug} currentPath={currentPath} />
  </aside>
}
