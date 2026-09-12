import { useEffect, useMemo, useState } from 'react'

import RichTextEditor from './RichTextEditor'
import { projectFiles, readProjectFile, saveProjectFile } from './write-workspace-store'

type Props = { slug: string; primaryPath: string; onClose: () => void }

export default function SplitEditorPane({ slug, primaryPath, onClose }: Props) {
  const [files, setFiles] = useState<string[]>([])
  const [path, setPath] = useState('')
  const [content, setContent] = useState('')
  const [dirty, setDirty] = useState(false)
  const [status, setStatus] = useState('Choose a document')

  const choices = useMemo(() => files.filter((file) => file !== primaryPath && /\.(md|txt)$/i.test(file)), [files, primaryPath])

  useEffect(() => {
    void projectFiles(slug).then(setFiles)
  }, [slug])

  useEffect(() => {
    if (!dirty || !path) return
    const timer = window.setTimeout(() => {
      void saveProjectFile(slug, path, content)
        .then(() => { setDirty(false); setStatus(`Saved ${path}`) })
        .catch((cause) => setStatus(`Save failed: ${(cause as Error).message}`))
    }, 900)
    return () => window.clearTimeout(timer)
  }, [content, dirty, path, slug])

  async function open(next: string) {
    if (dirty && path) await saveProjectFile(slug, path, content)
    setPath(next)
    if (!next) {
      setContent('')
      setDirty(false)
      return
    }
    try {
      setContent(await readProjectFile(slug, next))
      setDirty(false)
      setStatus(next)
    } catch (cause) {
      setStatus((cause as Error).message)
    }
  }

  return <aside className="write-split-pane">
    <header>
      <div><small>SPLIT EDITOR</small><strong>{path || 'Reference / second document'}</strong></div>
      <div><select value={path} onChange={(event) => void open(event.target.value)}><option value="">Choose document…</option>{choices.map((file) => <option key={file} value={file}>{file}</option>)}</select><button type="button" onClick={onClose}>×</button></div>
    </header>
    {path ? <RichTextEditor markdown={content} documentKey={`${slug}:${path}`} onChange={(next) => { setContent(next); setDirty(true) }} /> : <div className="write-split-empty">Open another chapter, scene, character file, or note beside the manuscript.</div>}
    <footer>{dirty ? 'Unsaved changes' : status}</footer>
  </aside>
}
