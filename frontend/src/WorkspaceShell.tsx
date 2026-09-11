import { useEffect, useMemo, useState } from 'react'

import AppV2 from './AppV2'
import './workspace-shell.css'

type Workspace = 'write' | 'plan' | 'characters' | 'world' | 'analyze' | 'publish' | 'submit'

const workspaces: { id: Workspace; label: string; icon: string; targets: string[] }[] = [
  { id: 'write', label: 'Write', icon: '✎', targets: [] },
  { id: 'plan', label: 'Plan', icon: '▦', targets: ['Corkboard', 'Outliner', 'Binder'] },
  { id: 'characters', label: 'Characters', icon: '♟', targets: ['Story Intelligence', 'Relationship Chemistry'] },
  { id: 'world', label: 'World', icon: '◎', targets: ['Story Memory', 'Trusted Knowledge'] },
  { id: 'analyze', label: 'Analyze', icon: '◫', targets: ['Editorial Studio', 'AI Readers', 'Review Comments'] },
  { id: 'publish', label: 'Publish', icon: '▤', targets: ['Cover Studio', 'Interior Compile', 'Release & Distribution'] },
  { id: 'submit', label: 'Submit', icon: '⇧', targets: ['Traditional Submission Studio'] },
]

function visibleText(element: Element): string {
  return (element.textContent || '').replace(/\s+/g, ' ').trim().toLowerCase()
}

function findPanel(labels: string[]): HTMLElement | null {
  const wanted = labels.map((label) => label.toLowerCase())
  const summaries = Array.from(document.querySelectorAll('summary'))
  for (const summary of summaries) {
    const text = visibleText(summary)
    if (!wanted.some((label) => text.includes(label))) continue
    const details = summary.closest('details') as HTMLDetailsElement | null
    if (details) {
      details.open = true
      return details
    }
    return summary as HTMLElement
  }
  return null
}

function clickBinderWorkspace(label: string): boolean {
  const buttons = Array.from(document.querySelectorAll<HTMLButtonElement>('.library button'))
  const button = buttons.find((candidate) => visibleText(candidate).includes(label.toLowerCase()))
  if (!button) return false
  button.click()
  button.scrollIntoView({ block: 'nearest' })
  return true
}

export default function WorkspaceShell() {
  const [workspace, setWorkspace] = useState<Workspace>(() => {
    const stored = localStorage.getItem('emberwriter.workspace') as Workspace | null
    return workspaces.some((item) => item.id === stored) ? stored! : 'write'
  })
  const [focusMode, setFocusMode] = useState(() => localStorage.getItem('emberwriter.focusMode') === 'true')
  const [binderCollapsed, setBinderCollapsed] = useState(false)
  const [assistantCollapsed, setAssistantCollapsed] = useState(false)

  const active = useMemo(() => workspaces.find((item) => item.id === workspace) || workspaces[0], [workspace])

  useEffect(() => {
    localStorage.setItem('emberwriter.workspace', workspace)
  }, [workspace])

  useEffect(() => {
    localStorage.setItem('emberwriter.focusMode', String(focusMode))
  }, [focusMode])

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.shiftKey && event.key.toLowerCase() === 'f') {
        event.preventDefault()
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
    window.requestAnimationFrame(() => {
      if (next === 'write') {
        document.querySelector<HTMLElement>('.editor-panel')?.scrollIntoView({ block: 'nearest' })
        return
      }
      if (next === 'plan') {
        if (clickBinderWorkspace('Corkboard')) return
        document.querySelector<HTMLElement>('.library')?.scrollIntoView({ block: 'nearest' })
        return
      }
      const definition = workspaces.find((item) => item.id === next)
      const panel = definition ? findPanel(definition.targets) : null
      panel?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    })
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
            onClick={() => setFocusMode((value) => !value)}
            title="Focus mode · Ctrl/Cmd+Shift+F"
          >
            ◉ Focus
          </button>
        </div>
      </header>

      <div className="workspace-contextbar">
        <span className="workspace-context-label">{active.icon} {active.label}</span>
        <span>{workspace === 'write' ? 'Manuscript-first writing workspace' : `Working in ${active.label}`}</span>
        <span className="workspace-shortcut">Ctrl/Cmd+1–7 changes workspace · Ctrl/Cmd+Shift+F toggles Focus</span>
      </div>

      <div className="workspace-app">
        <AppV2 />
      </div>
    </div>
  )
}
