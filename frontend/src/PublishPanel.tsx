import { useEffect, useRef, useState } from 'react'
import './publish-navigation.css'

import CoverStudioPanel from './CoverStudioPanel'
import AudiobookPanel from './AudiobookPanel'
import ProductionPreflight from './ProductionPreflight'
import PublishingDesk from './PublishingDesk'
import InteriorAtelier from './InteriorAtelier'
import DistributionPanel from './DistributionPanel'
import PreviewStudioPanel from './PreviewStudioPanel'
import ProjectHistoryPanel from './ProjectHistoryPanel'
import SubmissionPanel from './SubmissionPanel'

type PublishStage = 'desk' | 'readiness' | 'interior' | 'cover' | 'audio' | 'distribution' | 'history'
const PUBLISH_STAGES: { id: PublishStage; label: string; detail: string }[] = [
  { id: 'desk', label: 'Publishing desk', detail: 'Your private guided path from manuscript to local release files' },
  { id: 'readiness', label: 'Readiness', detail: 'Check publication concerns before creating files' },
  { id: 'interior', label: 'Book files', detail: 'Preview and export EPUB, DOCX and PDF interiors' },
  { id: 'cover', label: 'Cover', detail: 'Create and review the cover assets' },
  { id: 'audio', label: 'Audiobook', detail: 'Offline narration and chapter audio packages' },
  { id: 'distribution', label: 'Release', detail: 'Submissions and distribution preparation' },
  { id: 'history', label: 'History', detail: 'Find saved project versions and backups' },
]

type Props = {
  apiBase: string
  slug: string
  projectName: string
  disabled: boolean
  onOpenSource?: (path: string, anchor?: string) => void
}

export default function PublishPanel({ apiBase, slug, projectName, disabled, onOpenSource }: Props) {
  const [stage, setStage] = useState<PublishStage>('desk')
  const navRef = useRef<HTMLElement | null>(null)
  useEffect(() => {
    navRef.current?.querySelector('button.active')?.scrollIntoView({ behavior: 'instant', block: 'nearest', inline: 'center' })
  }, [stage])
  useEffect(() => { setStage('desk') }, [slug])
  return (
    <section className="publish-workflow" aria-label="Publishing workspace">
      <nav ref={navRef} className="publish-workflow-nav" aria-label="Publishing steps">
        {PUBLISH_STAGES.map(item => <button key={item.id} type="button"
          className={stage === item.id ? 'active' : ''}
          aria-current={stage === item.id ? 'page' : undefined}
          onClick={() => setStage(item.id)}>{item.label}</button>)}
      </nav>
      <p className="publish-workflow-hint" aria-live="polite">{PUBLISH_STAGES.find(item => item.id === stage)?.detail}</p>
      <div className="publish-workflow-content" key={slug + ':' + stage}>
        {stage === 'desk' && <PublishingDesk apiBase={apiBase} slug={slug} disabled={disabled}
          onGo={next=>setStage(next)} onOpenSource={onOpenSource} />}
        {stage === 'readiness' && <ProductionPreflight apiBase={apiBase} slug={slug} disabled={disabled} />}
        {stage === 'history' && <ProjectHistoryPanel apiBase={apiBase} slug={slug} disabled={disabled} />}
        {stage === 'interior' && <InteriorAtelier apiBase={apiBase} slug={slug}
          title={projectName} author="" disabled={disabled}
          onBuilt={async()=>{}} />}
        {stage === 'interior' && <details className="authoring-panel">
          <summary>Advanced device preview <small>Existing full EPUB / print simulator</small></summary>
          <PreviewStudioPanel apiBase={apiBase} slug={slug} projectName={projectName} disabled={disabled} />
        </details>}
        {stage === 'cover' && <CoverStudioPanel apiBase={apiBase} slug={slug} projectName={projectName} disabled={disabled} />}
        {stage === 'audio' && <AudiobookPanel apiBase={apiBase} slug={slug} disabled={disabled} />}
        {stage === 'distribution' && <SubmissionPanel apiBase={apiBase} slug={slug} disabled={disabled} onOpenSource={onOpenSource} />}
        {stage === 'distribution' && <DistributionPanel apiBase={apiBase} slug={slug} projectName={projectName} disabled={disabled} />}
      </div>
    </section>
  )
}
