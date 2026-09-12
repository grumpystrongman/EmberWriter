import { useEffect, useState } from 'react'

import type { ProjectSummary } from './capture-store'
import { activePath, activeProject } from './write-workspace-store'

export function useWriteContext() {
  const [project, setProject] = useState<ProjectSummary | null>(null)
  const [path, setPath] = useState('')
  const [panel, setPanel] = useState<HTMLElement | null>(null)
  const [header, setHeader] = useState<HTMLElement | null>(null)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    let timer = 0
    let disposed = false
    async function sync() {
      const shell = document.querySelector<HTMLElement>('.workspace-shell')
      setVisible(shell?.dataset.workspace === 'write')
      setPanel(document.querySelector<HTMLElement>('.rich-editor-panel'))
      setHeader(document.querySelector<HTMLElement>('.editor-header'))
      setPath(activePath())
      const nextProject = await activeProject()
      if (!disposed) setProject(nextProject)
    }
    function schedule() {
      window.clearTimeout(timer)
      timer = window.setTimeout(() => void sync(), 70)
    }
    const observer = new MutationObserver(schedule)
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      characterData: true,
      attributes: true,
      attributeFilter: ['class', 'data-workspace'],
    })
    document.addEventListener('click', schedule, true)
    schedule()
    return () => {
      disposed = true
      window.clearTimeout(timer)
      observer.disconnect()
      document.removeEventListener('click', schedule, true)
    }
  }, [])

  return { project, path, panel, header, visible }
}
