import { lazy, Suspense } from 'react'

import EditorialPanel, { type EditorialFinding } from './EditorialPanel'
import PublishPanel from './PublishPanel'
import SubmissionPanel from './SubmissionPanel'
import type { Workspace, WorkspaceProject } from './workspace-types'
import './center-workspaces.css'
import './scene-center.css'

const AIStudioWorkspace = lazy(() => import('./AIStudioWorkspace'))
const CharacterVoiceStudio = lazy(() => import('./CharacterVoiceStudio'))
const CharactersWorkspace = lazy(() => import('./CharactersWorkspace'))
const NotesWorkspace = lazy(() => import('./NotesWorkspace'))
const PlanningHub = lazy(() => import('./PlanningHub'))
const ProvenanceVoicePanel = lazy(() => import('./ProvenanceVoicePanel'))
const ToolsWorkspace = lazy(() => import('./ToolsWorkspace'))
const WorldWorkspace = lazy(() => import('./WorldWorkspace'))
const SeriesDesk = lazy(() => import('./SeriesDesk'))

type Props = {
  workspace: Workspace
  project: WorkspaceProject | null
  onOpenSource: (path: string, anchor?: string) => void
  onNavigateWorkspace: (workspace:Workspace) => void
}

const API = 'http://127.0.0.1:8000/api'

function LoadingWorkspace() {
  return (
    <div className="center-workspace-empty" role="status" aria-live="polite">
      <span>◆</span>
      <h1>Opening workspace…</h1>
      <p>Loading the tools for this studio.</p>
    </div>
  )
}

export default function CenterWorkspace({ workspace, project, onOpenSource, onNavigateWorkspace }: Props) {
  if (workspace === 'write') return null
  if (workspace === 'series') return (
    <div className="center-workspace-overlay center-workspace-series">
      <Suspense fallback={<LoadingWorkspace />}><SeriesDesk project={project} /></Suspense>
    </div>
  )

  if (!project) {
    return (
      <div className="center-workspace-overlay">
        <div className="center-workspace-empty">
          <span>◆</span>
          <h1>Open a story project</h1>
          <p>This workspace belongs to a story. Choose a project in the Library, then {workspace} becomes available here.</p>
        </div>
      </div>
    )
  }

  async function openFinding(finding: EditorialFinding) {
    onOpenSource(finding.path, finding.anchor_text)
  }

  return (
    <div className={`center-workspace-overlay center-workspace-${workspace}`}>
      <Suspense fallback={<LoadingWorkspace />}>
        {workspace === 'studio' && <AIStudioWorkspace apiBase={API} project={project} />}
        {workspace === 'notes' && <NotesWorkspace project={project} onOpenSource={onOpenSource} />}
        {workspace === 'plan' && <PlanningHub apiBase={API} project={project} onOpenSource={onOpenSource} onNavigateWorkspace={onNavigateWorkspace} />}
        {workspace === 'characters' && (
          <>
            <CharactersWorkspace apiBase={API} project={project} onOpenSource={onOpenSource} />
            <CharacterVoiceStudio apiBase={API} slug={project.slug} />
          </>
        )}
        {workspace === 'world' && <WorldWorkspace apiBase={API} project={project} onOpenSource={onOpenSource} />}
        {workspace === 'analyze' && (
          <section className="center-tool analyze-workspace">
            <header className="center-tool-header">
              <div><small>DEEP CRITIQUE · {project.name}</small><h1>Reader Perspectives & Critique</h1>
     <p>Run deeper chapter and manuscript perspectives here. For source-linked manuscript health, selective rewriting and recoverable edits, use the unified Edit & Review workbench.</p>
     <button type="button" className="analyze-bridge" onClick={()=>{
       try{
         sessionStorage.setItem('emberwriter:planning-tab-request:'+project.slug,'developmental_studio')
         sessionStorage.setItem('emberwriter:editorial-mode:'+project.slug,'revisions')
       }catch{/* Navigation still works without storage */}
       onNavigateWorkspace('plan')
     }}>Open Edit & Review / Revision Workbench ↗</button>
   </div>
            </header>
            <EditorialPanel
              apiBase={API}
              slug={project.slug}
              activePath={project.activePath}
              disabled={false}
              refreshToken={0}
              onOpenFinding={openFinding}
            />
            <ProvenanceVoicePanel apiBase={API} slug={project.slug} activePath={project.activePath} />
          </section>
        )}
        {workspace === 'tools' && <ToolsWorkspace apiBase={API} project={project} onOpenSource={onOpenSource} />}
        {workspace === 'publish' && (
          <section className="center-tool publish-workspace">
            <header className="center-tool-header">
              <div><small>PUBLISH · {project.name}</small><h1>Publishing Studio</h1><p>Compile interiors, design the cover, validate release metadata, and build retailer-ready handoff packages without leaving the center workspace.</p></div>
            </header>
            <div className="center-existing-tools publish-existing-tools">
              <PublishPanel apiBase={API} slug={project.slug} projectName={project.name} disabled={false} onOpenSource={onOpenSource} />
            </div>
          </section>
        )}
        {workspace === 'submit' && (
          <section className="center-tool submit-workspace">
            <header className="center-tool-header">
              <div><small>SUBMIT · {project.name}</small><h1>Traditional Submission Studio</h1><p>Build and edit your query package, destination-specific requirements, samples, synopsis, pitch, bio, and submission tracker.</p></div>
            </header>
            <div className="center-existing-tools">
              <SubmissionPanel apiBase={API} slug={project.slug} disabled={false} onOpenSource={onOpenSource} />
            </div>
          </section>
        )}
      </Suspense>
    </div>
  )
}
