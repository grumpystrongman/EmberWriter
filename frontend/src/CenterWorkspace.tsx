import CharactersWorkspace from './CharactersWorkspace'
import EditorialPanel, { type EditorialFinding } from './EditorialPanel'
import PlanningHub from './PlanningHub'
import PublishPanel from './PublishPanel'
import SubmissionPanel from './SubmissionPanel'
import WorldWorkspace from './WorldWorkspace'
import type { Workspace, WorkspaceProject } from './workspace-types'
import './center-workspaces.css'
import './scene-center.css'

type Props = {
  workspace: Workspace
  project: WorkspaceProject | null
  onOpenSource: (path: string, anchor?: string) => void
}

const API = 'http://127.0.0.1:8000/api'

export default function CenterWorkspace({ workspace, project, onOpenSource }: Props) {
  if (workspace === 'write') return null

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
      {workspace === 'plan' && <PlanningHub apiBase={API} project={project} onOpenSource={onOpenSource} />}
      {workspace === 'characters' && <CharactersWorkspace apiBase={API} project={project} onOpenSource={onOpenSource} />}
      {workspace === 'world' && <WorldWorkspace apiBase={API} project={project} onOpenSource={onOpenSource} />}
      {workspace === 'analyze' && (
        <section className="center-tool analyze-workspace">
          <header className="center-tool-header">
            <div><small>ANALYZE · {project.name}</small><h1>Editorial & Reader Studio</h1><p>Manuscript-wide diagnostics, smart triage, AI side-by-side revision review, genre readers, grammar knowledge, and continuity work in one full-width surface.</p></div>
          </header>
          <EditorialPanel
            apiBase={API}
            slug={project.slug}
            activePath={project.activePath}
            disabled={false}
            refreshToken={0}
            onOpenFinding={openFinding}
          />
        </section>
      )}
      {workspace === 'publish' && (
        <section className="center-tool publish-workspace">
          <header className="center-tool-header">
            <div><small>PUBLISH · {project.name}</small><h1>Publishing Studio</h1><p>Compile interiors, design the cover, validate release metadata, and build retailer-ready handoff packages without leaving the center workspace.</p></div>
          </header>
          <div className="center-existing-tools publish-existing-tools">
            <PublishPanel apiBase={API} slug={project.slug} projectName={project.name} disabled={false} />
          </div>
        </section>
      )}
      {workspace === 'submit' && (
        <section className="center-tool submit-workspace">
          <header className="center-tool-header">
            <div><small>SUBMIT · {project.name}</small><h1>Traditional Submission Studio</h1><p>Build and edit your query package, destination-specific requirements, samples, synopsis, pitch, bio, and submission tracker.</p></div>
          </header>
          <div className="center-existing-tools">
            <SubmissionPanel apiBase={API} slug={project.slug} disabled={false} />
          </div>
        </section>
      )}
    </div>
  )
}
