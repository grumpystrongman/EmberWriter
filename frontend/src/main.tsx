import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import WorkspaceShell from './WorkspaceShell'
import AuthorCaptureOverlay from './AuthorCaptureOverlay'
import ProjectRecoveryStatus from './ProjectRecoveryStatus'
import StableDiffusionStatus from './StableDiffusionStatus'
import VoiceFingerprintOverlay from './VoiceFingerprintOverlay'
import WriteWorkspacePro from './WriteWorkspacePro'
import './styles.css'
import './story.css'
import './editorial.css'
import './editorial-fix.css'
import './write-workspace-header.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <WorkspaceShell />
    <WriteWorkspacePro />
    <AuthorCaptureOverlay />
    <VoiceFingerprintOverlay />
    <ProjectRecoveryStatus />
    <StableDiffusionStatus />
  </StrictMode>,
)
