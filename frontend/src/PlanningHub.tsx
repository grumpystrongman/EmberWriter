import { useState } from 'react'

import AutopilotWorkspace from './AutopilotWorkspace'
import DevelopmentWorkspace from './DevelopmentWorkspace'
import PlanWorkspace from './PlanWorkspace'
import type { WorkspaceProject } from './workspace-types'

type Props = {
  apiBase: string
  project: WorkspaceProject
  onOpenSource: (path: string, anchor?: string) => void
}

type PlanHubTab = 'autopilot' | 'timeline' | 'story_map'

export default function PlanningHub({ apiBase, project, onOpenSource }: Props) {
  const [tab, setTab] = useState<PlanHubTab>('autopilot')

  return (
    <section className="center-tool planning-hub">
      <header className="center-tool-header">
        <div>
          <small>PLAN · {project.name}</small>
          <h1>Story Development</h1>
          <p>Run a local production-readiness assessment, then move between your timeline and author-owned story map without losing context.</p>
        </div>
      </header>

      <nav className="center-subtabs planning-hub-tabs" aria-label="Story development tools">
        <button type="button" className={tab === 'autopilot' ? 'active' : ''} onClick={() => setTab('autopilot')}>✦ Autopilot · Flight Deck</button>
        <button type="button" className={tab === 'timeline' ? 'active' : ''} onClick={() => setTab('timeline')}>Timeline · Beats · Scenes</button>
        <button type="button" className={tab === 'story_map' ? 'active' : ''} onClick={() => setTab('story_map')}>Story Map · Arcs · Relationships · Threads</button>
      </nav>

      {tab === 'autopilot' ? (
        <AutopilotWorkspace apiBase={apiBase} project={project} onOpenSource={onOpenSource} />
      ) : tab === 'timeline' ? (
        <PlanWorkspace apiBase={apiBase} project={project} onOpenSource={onOpenSource} />
      ) : (
        <DevelopmentWorkspace apiBase={apiBase} project={project} onOpenSource={onOpenSource} />
      )}
    </section>
  )
}
