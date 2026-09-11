import { useState } from 'react'

import DevelopmentWorkspace from './DevelopmentWorkspace'
import PlanWorkspace from './PlanWorkspace'
import type { WorkspaceProject } from './workspace-types'

type Props = {
  apiBase: string
  project: WorkspaceProject
  onOpenSource: (path: string, anchor?: string) => void
}

type PlanHubTab = 'timeline' | 'story_map'

export default function PlanningHub({ apiBase, project, onOpenSource }: Props) {
  const [tab, setTab] = useState<PlanHubTab>('timeline')

  return (
    <section className="center-tool planning-hub">
      <header className="center-tool-header">
        <div>
          <small>PLAN · {project.name}</small>
          <h1>Story Development</h1>
          <p>Move between the manuscript-derived timeline and your author-owned structural map without losing context.</p>
        </div>
      </header>

      <nav className="center-subtabs planning-hub-tabs" aria-label="Story development tools">
        <button type="button" className={tab === 'timeline' ? 'active' : ''} onClick={() => setTab('timeline')}>Timeline · Beats · Scenes</button>
        <button type="button" className={tab === 'story_map' ? 'active' : ''} onClick={() => setTab('story_map')}>Story Map · Arcs · Relationships · Threads</button>
      </nav>

      {tab === 'timeline' ? (
        <PlanWorkspace apiBase={apiBase} project={project} onOpenSource={onOpenSource} />
      ) : (
        <DevelopmentWorkspace apiBase={apiBase} project={project} onOpenSource={onOpenSource} />
      )}
    </section>
  )
}
