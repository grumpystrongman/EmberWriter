import { useState } from 'react'

import AutopilotWorkspace from './AutopilotWorkspace'
import BookStudio from './BookStudio'
import ManuscriptIntelligence from './ManuscriptIntelligence'
import StoryArcInvestigator from './StoryArcInvestigator'
import VoiceprintLab from './VoiceprintLab'
import DevelopmentWorkspace from './DevelopmentWorkspace'
import PlanWorkspace from './PlanWorkspace'
import type { WorkspaceProject } from './workspace-types'

type Props = {
  apiBase: string
  project: WorkspaceProject
  onOpenSource: (path: string, anchor?: string) => void
}

type PlanHubTab = 'autopilot' | 'book_studio' | 'manuscript_intelligence' | 'story_arcs' | 'voiceprint' | 'timeline' | 'story_map'

export default function PlanningHub({ apiBase, project, onOpenSource }: Props) {
  const [tab, setTab] = useState<PlanHubTab>('book_studio')

  return (
    <section className="center-tool planning-hub">
      <header className="center-tool-header">
        <div>
          <small>PLAN · {project.name}</small>
          <h1>Story Development</h1>
          <p>Lead the story. Give EmberWriter a premise, characters, world and direction; draft a complete book with your edits, approvals and creative control at every step.</p>
        </div>
      </header>

      <nav className="center-subtabs planning-hub-tabs" aria-label="Story development tools">
        <button type="button" className={tab === 'book_studio' ? 'active' : ''} onClick={() => setTab('book_studio')}>Book Studio · Write the whole book</button>
        <button type="button" className={tab === 'manuscript_intelligence' ? 'active' : ''} onClick={() => setTab('manuscript_intelligence')}>Manuscript Intelligence</button>
        <button type="button" className={tab === 'story_arcs' ? 'active' : ''} onClick={() => setTab('story_arcs')}>Story Arc Investigator</button>
        <button type="button" className={tab === 'voiceprint' ? 'active' : ''} onClick={() => setTab('voiceprint')}>Voiceprint Lab</button>
        <button type="button" className={tab === 'autopilot' ? 'active' : ''} onClick={() => setTab('autopilot')}>✦ Autopilot · Flight Deck</button>
        <button type="button" className={tab === 'timeline' ? 'active' : ''} onClick={() => setTab('timeline')}>Timeline · Beats · Scenes</button>
        <button type="button" className={tab === 'story_map' ? 'active' : ''} onClick={() => setTab('story_map')}>Story Map · Arcs · Relationships · Threads</button>
      </nav>

      {tab === 'book_studio' ? (
        <BookStudio apiBase={apiBase} projectSlug={project.slug} onOpenSource={onOpenSource} />
      ) : tab === 'manuscript_intelligence' ? (
        <ManuscriptIntelligence apiBase={apiBase} projectSlug={project.slug} onOpenSource={onOpenSource} />
      ) : tab === 'story_arcs' ? (
        <StoryArcInvestigator apiBase={apiBase} projectSlug={project.slug} onOpenSource={onOpenSource} />
      ) : tab === 'voiceprint' ? (
        <VoiceprintLab apiBase={apiBase} projectSlug={project.slug} onOpenSource={onOpenSource} />
      ) : tab === 'autopilot' ? (
        <AutopilotWorkspace apiBase={apiBase} project={project} onOpenSource={onOpenSource} />
      ) : tab === 'timeline' ? (
        <PlanWorkspace apiBase={apiBase} project={project} onOpenSource={onOpenSource} />
      ) : (
        <DevelopmentWorkspace apiBase={apiBase} project={project} onOpenSource={onOpenSource} />
      )}
    </section>
  )
}
