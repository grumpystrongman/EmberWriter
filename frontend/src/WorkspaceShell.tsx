import { useEffect, useMemo, useState } from 'react'

import AppV2 from './AppV2'
import CenterWorkspace from './CenterWorkspace'
import type { Workspace, WorkspaceProject } from './workspace-types'
import './workspace-shell.css'

const API = 'http://127.0.0.1:8000/api'

const workspaces: { id: Workspace; label: string; icon: string }[] = [
  { id: 'write', label: 'Write', icon: '✎' },
  { id: 'plan', label: 'Plan', icon: '▦' },
  { id: 'characters', label: 'Characters', icon: '♟' },
  { id: 'world', label: 'World', icon: '◎' },
  { id: 'analyze', label: 'Analyze', icon: '◫' },
  { id: 'publish', label: 'Publish', icon: '▤' },
  { id: 'submit', label: 'Submit', icon: '⇧' },
]

type ProjectSummary = {
  slug: string
  name: string
  description: string
}

type BinderNode = {
  id: string
  title: string
  parent_id: string | null
  path: string | null
}

type BinderState = {
  nodes: BinderNode[]
}

function cleanText(value: string | null | undefined) {
  return (value || '').replace(/\s+/g, ' ').trim()
}

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}

function binderButton(title: string): HTMLButtonElement | null {
  return Array.from(document.querySelectorAll<HTMLButtonElement>('.binder-node-button'))
    .find((button) => cleanText(button.querySelector('strong')?.textContent) === title) || null
}

function highlightEditorText(anchor: string) {
  const needle = anchor.trim()
  const root = document.querySelector<HTMLElement>('.prose-editor')
  if (!root || !needle || needle === '\u0000') return

  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT)
  const segments: { node: Text; start: number; end: number }[] = []
  let haystack = ''
  let current: Node | null
  while ((current = walker.nextNode())) {
    const text = current.textContent || ''
    const start = haystack.length
    haystack += text
    segments.push({ node: current as Text, start, end: haystack.length })
  }

  const start = haystack.toLocaleLowerCase().indexOf(needle.toLocaleLowerCase())
  if (start < 0) return
  const end = start + needle.length
  const first = segments.find((segment) => start >= segment.start && start <= segment.end)
  const last = [...segments].reverse().find((segment) => end >= segment.start && end <= segment.end)
  if (!first || !last) return

  const range = document.createRange()
  range.setStart(first.node, Math.max(0, start - first.start))
  range.setEnd(last.node, Math.min(last.node.length, end - last.start))
  const selection = window.getSelection()
  selection?.removeAllRanges()
  selection?.addRange(range)
  const parent = first.node.parentElement
  parent?.scrollIntoView({ block: 'center', behavior: 'smooth' })
}

export default function WorkspaceShell() {
  const [workspace, setWorkspace] = useState<Workspace>(() => {
    const stored = localStorage.getItem('emberwriter.workspace') as Workspace | null
    return workspaces.some((item) => item.id === stored) ? stored! : 'write'
  })
  const [focusMode, setFocusMode] = useState(() => localStorage.getItem('emberwriter.focusMode') === 'true')
  const [binderCollapsed, setBinderCollapsed] = useState(false)
  const [assistantCollapsed, setAssistantCollapsed] = useState(false)
  const [projectContext, setProjectContext] = useState<WorkspaceProject | null>(null)

  const active = useMemo(() => workspaces.find((item) => item.id === workspace) || workspaces[0], [workspace])

  useEffect(() => {
    localStorage.setItem('emberwriter.workspace', workspace)
  }, [workspace])

  useEffect(() => {
    localStorage.setItem('emberwriter.focusMode', String(focusMode))
  }, [focusMode])

  useEffect(() => {
    let timer = 0
    let disposed = false

    async function syncProjectContext() {
      const activeCard = document.querySelector<HTMLElement>('.project-card.active')
      const name = cleanText(activeCard?.querySelector('strong')?.textContent)
      if (!name) {
        setProjectContext(null)
        return
      }
      const description = cleanText(activeCard?.querySelector('small')?.textContent)
      const activePathText = cleanText(document.querySelector<HTMLElement>('.editor-header h1')?.textContent)
      const activePath = activePathText === 'Select a file' ? '' : activePathText
      try {
        const response = await fetch(`${API}/projects`)
        if (!response.ok) return
        const projects = await response.json() as ProjectSummary[]
        const exact = projects.find((item) => item.name === name && cleanText(item.description || 'Local story project') === description)
        const match = exact || projects.find((item) => item.name === name)
        if (!match || disposed) return
        const next: WorkspaceProject = { slug: match.slug, name: match.name, description: match.description, activePath }
        setProjectContext((current) => (
          current?.slug === next.slug && current.activePath === next.activePath && current.name === next.name
            ? current
            : next
        ))
      } catch {
        // AppV2 owns the visible API-offline state; avoid duplicating it here.
      }
    }

    function scheduleSync() {
      window.clearTimeout(timer)
      timer = window.setTimeout(() => void syncProjectContext(), 80)
    }

    const root = document.querySelector('.workspace-app') || document.body
    const observer = new MutationObserver(scheduleSync)
    observer.observe(root, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ['class'] })
    document.addEventListener('click', scheduleSync, true)
    scheduleSync()

    return () => {
      disposed = true
      window.clearTimeout(timer)
      observer.disconnect()
      document.removeEventListener('click', scheduleSync, true)
    }
  }, [])

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.shiftKey && event.key.toLowerCase() === 'f') {
        event.preventDefault()
        setWorkspace('write')
        setFocusMode((value) => !value)
      }
      if ((event.ctrlKey || event.metaKey) && event.key >= '1' && event.key <= '7') {
        event.preventDefault()
        const next = workspaces[Number(event.key) - 1]
        if (next) openWorkspace(next.id)
      }
    }
    function onFocusMode(event: Event) {
      const custom = event as CustomEvent<boolean>
      setWorkspace('write')
      setFocusMode(custom.detail ?? true)
    }
    window.addEventListener('keydown', onKeyDown)
    window.addEventListener('emberwriter:focus-mode', onFocusMode)
    return () => {
      window.removeEventListener('keydown', onKeyDown)
      window.removeEventListener('emberwriter:focus-mode', onFocusMode)
    }
  }, [])

  function openWorkspace(next: Workspace) {
    setWorkspace(next)
    setFocusMode(false)
  }

  async function openSource(path: string, anchor = '') {
    if (!projectContext) return
    setWorkspace('write')
    setFocusMode(false)
    try {
      const response = await fetch(`${API}/projects/${projectContext.slug}/binder`)
      const binder = response.ok ? await response.json() as BinderState : null
      const node = binder?.nodes.find((item) => item.path === path)
      if (!node) return
      const nodes = new Map(binder!.nodes.map((item) => [item.id, item]))
      const parents: BinderNode[] = []
      let parentId = node.parent_id
      while (parentId) {
        const parent = nodes.get(parentId)
        if (!parent) break
        parents.unshift(parent)
        parentId = parent.parent_id
      }

      await sleep(40)
      for (const parent of parents) {
        const button = binderButton(parent.title)
        const row = button?.closest('.binder-row')
        const disclosure = row?.querySelector<HTMLButtonElement>('.binder-disclosure')
        if (disclosure && cleanText(disclosure.textContent) === '›') {
          disclosure.click()
          await sleep(45)
        }
      }
      const target = binderButton(node.title)
      target?.click()
      await sleep(180)
      highlightEditorText(anchor)
    } catch {
      // Falling back to Write still gives the author direct access through the Binder.
    }
  }

  return (
    <div
      className={`workspace-shell workspace-${workspace}${focusMode ? ' focus-mode' : ''}${binderCollapsed ? ' binder-collapsed' : ''}${assistantCollapsed ? ' assistant-collapsed' : ''}`}
      data-workspace={workspace}
    >
      <header className="workspace-topbar">
        <div className="workspace-brand" onClick={() => openWorkspace('write')} role="button" tabIndex={0}>
          <span className="workspace-flame">◆</span>
          <span><strong>EmberWriter</strong><small>Stories. Sharper.</small></span>
        </div>
        <nav className="workspace-nav" aria-label="Primary workspaces">
          {workspaces.map((item, index) => (
            <button
              key={item.id}
              type="button"
              className={workspace === item.id ? 'active' : ''}
              onClick={() => openWorkspace(item.id)}
              title={`${item.label} · Ctrl/Cmd+${index + 1}`}
            >
              <span>{item.icon}</span>{item.label}
            </button>
          ))}
        </nav>
        <div className="workspace-actions">
          <button type="button" onClick={() => setBinderCollapsed((value) => !value)} title="Toggle Binder">☰</button>
          <button type="button" onClick={() => setAssistantCollapsed((value) => !value)} title="Toggle Ember">◆</button>
          <button
            type="button"
            className={focusMode ? 'active' : ''}
            onClick={() => { setWorkspace('write'); setFocusMode((value) => !value) }}
            title="Focus mode · Ctrl/Cmd+Shift+F"
          >
            ◉ Focus
          </button>
        </div>
      </header>

      <div className="workspace-contextbar">
        <span className="workspace-context-label">{active.icon} {active.label}</span>
        <span>{projectContext ? `${projectContext.name} · ${workspace === 'write' ? projectContext.activePath || 'Manuscript' : `${active.label} workspace`}` : workspace === 'write' ? 'Manuscript-first writing workspace' : `Working in ${active.label}`}</span>
        <span className="workspace-shortcut">Ctrl/Cmd+1–7 changes workspace · Ctrl/Cmd+Shift+F toggles Focus</span>
      </div>

      <div className="workspace-app">
        <AppV2 />
        <CenterWorkspace workspace={workspace} project={projectContext} onOpenSource={(path, anchor) => void openSource(path, anchor)} />
      </div>
    </div>
  )
}
