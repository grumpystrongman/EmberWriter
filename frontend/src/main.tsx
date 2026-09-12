import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import WorkspaceShell from './WorkspaceShell'
import AuthorCaptureOverlay from './AuthorCaptureOverlay'
import VoiceFingerprintOverlay from './VoiceFingerprintOverlay'
import './styles.css'
import './story.css'
import './editorial.css'
import './editorial-fix.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <WorkspaceShell />
    <AuthorCaptureOverlay />
    <VoiceFingerprintOverlay />
  </StrictMode>,
)
