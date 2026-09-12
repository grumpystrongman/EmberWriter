import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'

import SplitEditorPane from './SplitEditorPane'
import WriteSearchDrawer from './WriteSearchDrawer'
import WriteTabsBar from './WriteTabsBar'
import { useWriteContext } from './useWriteContext'
import './write-workspace-pro.css'

export default function WriteWorkspacePro() {
  const { project, path, panel, header, visible } = useWriteContext()
  const [tabs, setTabs] = useState<string[]>([])
  const [split, setSplit] = useState(false)
  const [search, setSearch] = useState(false)

  useEffect(() => {
    if (!project) return
    const key = `emberwriter.writeTabs.${project.slug}`
    try {
      const stored = JSON.parse(localStorage.getItem(key) || '[]') as string[]
      setTabs(Array.isArray(stored) ? stored.slice(-12) : [])
    } catch {
      setTabs([])
    }
  }, [project?.slug])

  useEffect(() => {
    if (!project || !path) return
    setTabs((current) => {
      const next = current.includes(path) ? current : [...current, path].slice(-12)
      localStorage.setItem(`emberwriter.writeTabs.${project.slug}`, JSON.stringify(next))
      return next
    })
  }, [path, project?.slug])

  useEffect(() => {
    if (!panel) return
    panel.classList.toggle('write-pro-mounted', visible)
    panel.classList.toggle('write-split-open', visible && split)
    panel.classList.toggle('write-search-open', visible && search)
    return () => panel.classList.remove('write-pro-mounted', 'write-split-open', 'write-search-open')
  }, [panel, visible, split, search])

  function updateTabs(next: string[]) {
    setTabs(next)
    if (project) localStorage.setItem(`emberwriter.writeTabs.${project.slug}`, JSON.stringify(next))
  }

  if (!visible || !project || !panel || !header) return null

  return <>
    {createPortal(
      <WriteTabsBar
        project={project}
        activePath={path}
        tabs={tabs}
        onTabs={updateTabs}
        onSplit={() => setSplit((value) => !value)}
        onSearch={() => setSearch((value) => !value)}
      />,
      header,
    )}
    {split && createPortal(
      <SplitEditorPane slug={project.slug} primaryPath={path} onClose={() => setSplit(false)} />,
      panel,
    )}
    {search && createPortal(
      <WriteSearchDrawer slug={project.slug} currentPath={path} onClose={() => setSearch(false)} />,
      panel,
    )}
  </>
}
