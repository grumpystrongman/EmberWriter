import { useEffect, useState } from 'react'
import './planning-hub.css'
import AutopilotWorkspace from './AutopilotWorkspace'
import BookStudio from './BookStudio'
import ManuscriptIntelligence from './ManuscriptIntelligence'
import StoryArcInvestigator from './StoryArcInvestigator'
import VoiceprintLab from './VoiceprintLab'
import StyleBible from './StyleBible'
import ProseEditor from './ProseEditor'
import EditorialBoard from './EditorialBoard'
import DevelopmentalStudio from './DevelopmentalStudio'
import ProductionConductor from './ProductionConductor'
import DevelopmentWorkspace from './DevelopmentWorkspace'
import PlanWorkspace from './PlanWorkspace'
import type { WorkspaceProject } from './workspace-types'

type Props = {
  apiBase: string
  project: WorkspaceProject
  onOpenSource: (path: string, anchor?: string) => void
  onNavigateWorkspace: (workspace:'analyze') => void
}
type PlanHubTab =
  | 'production_conductor' | 'book_studio'
  | 'timeline' | 'story_map' | 'manuscript_intelligence' | 'story_arcs'
  | 'editorial_board' | 'developmental_studio' | 'prose_editor' | 'style_bible' | 'voiceprint'
  | 'autopilot'
type Group = 'produce' | 'develop' | 'edit' | 'advanced'
type Tool = { id: PlanHubTab; name: string; detail: string }
type GroupSpec = { id: Group; label: string; description: string; tools: Tool[] }

export const PLANNING_GROUPS: GroupSpec[] = [
  {
    id: 'produce', label: 'Write the book',
    description: 'From a chapter plan to draft candidates, reader critiques and your final approval.',
    tools: [
      { id: 'production_conductor', name: 'Production guide', detail: 'Draft, review, approve and prepare the complete book' },
      { id: 'book_studio', name: 'Book Studio', detail: 'Outline, write and edit individual chapter candidates' },
    ],
  },
  {
    id: 'develop', label: 'Develop the story',
    description: 'Shape plot, characters, timelines and the evidence behind your story.',
    tools: [
      { id: 'timeline', name: 'Timeline & scenes', detail: 'Plan beats and scene order' },
      { id: 'story_map', name: 'Story map', detail: 'See arcs, relationships and narrative threads' },
      { id: 'manuscript_intelligence', name: 'Manuscript intelligence', detail: 'Track changes, narrative patterns and promises' },
      { id: 'story_arcs', name: 'Story arc investigation', detail: 'Assess narrative choices with cited passages' },
    ],
  },
  {
    id: 'edit', label: 'Edit & review',
    description: 'Prioritize issues across the manuscript and retain every deliberate writing decision.',
    tools: [
      { id: 'developmental_studio', name: 'Developmental studio', detail: 'Visual manuscript health, arc atlas, and selective revision workbench' },
      { id: 'editorial_board', name: 'Editorial overview', detail: 'Find outstanding work across all chapters' },
      { id: 'prose_editor', name: 'Prose editor', detail: 'Review specific grammar and style suggestions' },
      { id: 'style_bible', name: 'Style Bible', detail: 'Preferred spellings and invented terminology' },
      { id: 'voiceprint', name: 'Voiceprint', detail: 'Compare rhythm against your own writing sample' },
    ],
  },
  {
    id: 'advanced', label: 'Advanced',
    description: 'Specialized automation and model capabilities for experienced authors.',
    tools: [
      { id: 'autopilot', name: 'AI Flight Deck', detail: 'Experimental agents and capabilities' },
    ],
  },
]
const TOOLS = PLANNING_GROUPS.flatMap(group => group.tools)
function groupFor(tab: PlanHubTab): Group {
  return PLANNING_GROUPS.find(group => group.tools.some(tool => tool.id === tab))?.id || 'produce'
}
function initialTab(slug: string): PlanHubTab {
  try {
    const requested = window.sessionStorage.getItem('emberwriter:planning-tab-request:'+slug)
    if(requested && TOOLS.some(tool=>tool.id===requested)){
      window.sessionStorage.removeItem('emberwriter:planning-tab-request:'+slug)
      return requested as PlanHubTab
    }
    const stored = window.localStorage.getItem(`emberwriter:planning-tab:${slug}`)
    if (TOOLS.some(tool => tool.id === stored)) return stored as PlanHubTab
  } catch { /* Private browsing may disable local storage. */ }
  return 'production_conductor'
}

export default function PlanningHub({ apiBase, project, onOpenSource, onNavigateWorkspace }: Props) {
  const [tab, setTab] = useState<PlanHubTab>(() => initialTab(project.slug))
  const [editorialTarget, setEditorialTarget] = useState('')
  const groupId = groupFor(tab)
  const group = PLANNING_GROUPS.find(item => item.id === groupId)!
  const activeTool = TOOLS.find(item => item.id === tab)!

  useEffect(() => { setTab(initialTab(project.slug)); setEditorialTarget('') }, [project.slug])
  function selectTool(next: PlanHubTab) {
    setTab(next)
    try { window.localStorage.setItem(`emberwriter:planning-tab:${project.slug}`, next) }
    catch { /* Local selection still works without storage. */ }
  }
  function selectGroup(next: Group) {
    selectTool(PLANNING_GROUPS.find(item => item.id === next)!.tools[0].id)
  }
  function navigateEditorial(destination: 'prose_editor' | 'style_bible' | 'story_arcs', chapterPath: string) {
    setEditorialTarget(chapterPath)
    selectTool(destination)
  }
  function content() {
    switch (tab) {
      case 'production_conductor':
        return <ProductionConductor apiBase={apiBase} projectSlug={project.slug} onNavigate={selectTool} />
      case 'book_studio':
        return <BookStudio apiBase={apiBase} projectSlug={project.slug} onOpenSource={onOpenSource} />
      case 'manuscript_intelligence':
        return <ManuscriptIntelligence apiBase={apiBase} projectSlug={project.slug} onOpenSource={onOpenSource} />
      case 'story_arcs':
        return <StoryArcInvestigator apiBase={apiBase} projectSlug={project.slug} initialPath={editorialTarget} onOpenSource={onOpenSource} />
      case 'voiceprint':
        return <VoiceprintLab apiBase={apiBase} projectSlug={project.slug} onOpenSource={onOpenSource} />
      case 'style_bible':
        return <StyleBible apiBase={apiBase} projectSlug={project.slug} initialPath={editorialTarget} onOpenSource={onOpenSource} />
      case 'prose_editor':
        return <ProseEditor apiBase={apiBase} projectSlug={project.slug} initialPath={editorialTarget} onOpenSource={onOpenSource} />
      case 'developmental_studio':
        return <DevelopmentalStudio apiBase={apiBase} projectSlug={project.slug} onOpenSource={onOpenSource}
          onOpenEditorTool={(tool,path)=>{setEditorialTarget(path);selectTool(tool)}} />
      case 'editorial_board':
        return <EditorialBoard apiBase={apiBase} projectSlug={project.slug} onOpenSource={onOpenSource} onNavigate={navigateEditorial} />
      case 'autopilot':
        return <AutopilotWorkspace apiBase={apiBase} project={project} onOpenSource={onOpenSource} />
      case 'timeline':
        return <PlanWorkspace apiBase={apiBase} project={project} onOpenSource={onOpenSource} />
      case 'story_map':
        return <DevelopmentWorkspace apiBase={apiBase} project={project} onOpenSource={onOpenSource} />
    }
  }

  return (
    <section className="center-tool planning-hub">
      <header className="center-tool-header">
        <div>
          <small>STORY DEVELOPMENT · {project.name}</small>
          <h1>Your writing workspace</h1>
          <p>Choose the work you're doing. Your chapters, settings and author decisions remain in the project.</p>
        </div>
      </header>
      <div className="planning-author-shortcut">
        <span>Source-linked editing and safe revisions live here.</span>
        <button type="button" onClick={()=>onNavigateWorkspace('analyze')}>Run deep reader critique ↗</button>
      </div>
      <nav className="planning-groups" aria-label="Writing workflow">
        {PLANNING_GROUPS.map(item =>
          <button key={item.id} type="button" aria-pressed={groupId === item.id}
            className={groupId === item.id ? 'active' : ''} onClick={() => selectGroup(item.id)}>
            {item.label}
          </button>)}
      </nav>
      <div className="planning-tool-selector">
        <div className="planning-tool-heading">
          <strong>{group.label}</strong>
          <span>{group.description}</span>
        </div>
        <nav className="planning-tool-tabs" aria-label={group.label + ' tools'}>
          {group.tools.map(item =>
            <button key={item.id} type="button" className={tab === item.id ? 'active' : ''}
              aria-current={tab === item.id ? 'page' : undefined}
              title={item.detail} onClick={() => selectTool(item.id)}>
              {item.name}
            </button>)}
        </nav>
        <p className="planning-tool-description" aria-live="polite">{activeTool.detail}</p>
      </div>
      <div className="planning-tool-content" key={project.slug + ':' + tab}>
        {content()}
      </div>
    </section>
  )
}
