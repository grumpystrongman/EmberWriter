import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import WorkspaceShell from './WorkspaceShell'
import GenerationModePolicy from './GenerationModePolicy'
import GenerationWatchdog from './GenerationWatchdog'
import PerformancePanel from './PerformancePanel'
import ProjectRecoveryStatus from './ProjectRecoveryStatus'
import StableDiffusionStatus from './StableDiffusionStatus'
import StartupModelGuard from './StartupModelGuard'
import StickyNoteOverlay from './StickyNoteOverlay'
import VoiceFingerprintOverlay from './VoiceFingerprintOverlay'
import WriteWorkspacePro from './WriteWorkspacePro'
import './folder-picker-directory'
import './styles.css'
import './story.css'
import './editorial.css'
import './editorial-fix.css'
import './write-workspace-header.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <StartupModelGuard>
      <GenerationWatchdog />
      <GenerationModePolicy />
      <WorkspaceShell />
      <WriteWorkspacePro />
      <StickyNoteOverlay />
      <VoiceFingerprintOverlay />
      <ProjectRecoveryStatus />
      <StableDiffusionStatus />
      <PerformancePanel />
    </StartupModelGuard>
  </StrictMode>,
)
