import { useEffect, useState } from 'react'

import { openProjectPath, readProjectFile, saveProjectFile } from './write-workspace-store'

type Bookmark = { id: string; path: string; label: string; anchor: string; created_at: string }
type Props = { slug: string; currentPath: string }
const PATH = 'planning/write-bookmarks.json'

export default function WriteBookmarks({ slug, currentPath }: Props) {
  const [items, setItems] = useState<Bookmark[]>([])
  const [label, setLabel] = useState('')

  useEffect(() => {
    void readProjectFile(slug, PATH)
      .then((content) => {
        const parsed = JSON.parse(content) as { bookmarks?: Bookmark[] }
        setItems(Array.isArray(parsed.bookmarks) ? parsed.bookmarks : [])
      })
      .catch(() => setItems([]))
  }, [slug])

  async function persist(next: Bookmark[]) {
    setItems(next)
    await saveProjectFile(slug, PATH, JSON.stringify({ schema_version: 1, bookmarks: next }, null, 2))
  }

  async function add() {
    if (!currentPath) return
    const anchor = window.getSelection()?.toString().trim().slice(0, 500) || ''
    const item: Bookmark = {
      id: `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`,
      path: currentPath,
      label: label.trim() || currentPath.split('/').at(-1) || currentPath,
      anchor,
      created_at: new Date().toISOString(),
    }
    await persist([item, ...items])
    setLabel('')
  }

  return <section className="write-bookmarks">
    <div className="write-drawer-heading"><strong>Bookmarks</strong><span>{items.length}</span></div>
    <div className="write-bookmark-add"><input value={label} onChange={(event) => setLabel(event.target.value)} placeholder="Bookmark label" /><button type="button" onClick={() => void add()} disabled={!currentPath}>+ Bookmark current</button></div>
    <div className="write-bookmark-list">{items.map((item) => <article key={item.id}><button type="button" onClick={() => void openProjectPath(slug, item.path)}><strong>{item.label}</strong><small>{item.path}</small>{item.anchor && <span>“{item.anchor.slice(0, 100)}{item.anchor.length > 100 ? '…' : ''}”</span>}</button><button type="button" onClick={() => void persist(items.filter((candidate) => candidate.id !== item.id))}>×</button></article>)}</div>
  </section>
}
