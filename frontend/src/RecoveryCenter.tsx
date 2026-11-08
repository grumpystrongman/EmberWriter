import { useCallback, useEffect, useRef, useState } from 'react'
import './recovery-center.css'

const API = 'http://127.0.0.1:8000/api/recovery'
type Status = {
  directory: string; automatic: boolean; snapshot_count: number
  last_snapshot: { id: string; created_at: string; files: number; bytes: number } | null
  last_automatic_error: string | null; last_automatic_attempt: string | null
  mirror_directory: string | null; mirror_latest_present: boolean
  last_mirror_error: string | null; warning: string; latest_manifest_invalid: boolean
  free_bytes: number; mirror_free_bytes: number | null
}
type Generation = { id: string; created_at?: string; files?: number; bytes?: number; reason?: string; invalid_manifest?: boolean }
type Preview = { id: string; created_at: string; total_files: number; bytes: number; projects: string[];
  has_series: boolean; includes_media: boolean; warning: string; files: {path: string; bytes: number}[] }
type Verification = { healthy: boolean; checked_files: number; total_files: number; bad: {path:string;problem:string}[] }
type Props = { open: boolean; onClose: () => void }

async function call<T>(endpoint: string, init?: RequestInit): Promise<T> {
  const response = await fetch(API + endpoint, init)
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Recovery operation failed')
  return data as T
}
const json = (payload: object): RequestInit => ({
  method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload),
})
function size(bytes: number) {
  if (bytes >= 1024 ** 3) return (bytes / 1024 ** 3).toFixed(2) + ' GB'
  if (bytes >= 1024 ** 2) return (bytes / 1024 ** 2).toFixed(1) + ' MB'
  return Math.ceil(bytes / 1024) + ' KB'
}
function prettyDate(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

export default function RecoveryCenter({ open, onClose }: Props) {
  const [status, setStatus] = useState<Status | null>(null)
  const [generations, setGenerations] = useState<Generation[]>([])
  const [directory, setDirectory] = useState('')
  const [mirror, setMirror] = useState('')
  const [automatic, setAutomatic] = useState(true)
  const [selected, setSelected] = useState('')
  const [preview, setPreview] = useState<Preview | null>(null)
  const [verification, setVerification] = useState<Verification | null>(null)
  const [confirmation, setConfirmation] = useState(false)
  const [restoreDirectory, setRestoreDirectory] = useState('')
  const [restoreResult, setRestoreResult] = useState<{directory:string;files:number}|null>(null)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [busy, setBusy] = useState(false)
  const dialog = useRef<HTMLElement>(null)

  const refresh = useCallback(async () => {
    const [latest, history] = await Promise.all([
      call<Status>('/status'), call<Generation[]>('/generations'),
    ])
    setStatus(latest)
    setGenerations(history)
    window.dispatchEvent(new CustomEvent('emberwriter:recovery-changed'))
    setDirectory(latest.directory)
    setMirror(latest.mirror_directory || '')
    setAutomatic(latest.automatic)
    setSelected(previous => history.some(row => row.id === previous) ? previous : history[0]?.id || '')
  }, [])

  useEffect(() => {
    if (!open) return
    let alive = true
    void refresh().catch(cause => { if (alive) setError((cause as Error).message) })
    return () => { alive = false }
  }, [open, refresh])
  useEffect(() => {
    if (!open || !selected) { setPreview(null); return }
    let active = true
    setVerification(null)
    void call<Preview>('/generations/' + encodeURIComponent(selected))
      .then(value => { if (active) setPreview(value) })
      .catch(cause => { if (active) setError((cause as Error).message) })
    return () => { active = false }
  }, [open, selected])
  useEffect(() => {
    if (!open) return
    function keyboard(event: KeyboardEvent) {
      if (event.key === 'Escape' && !busy) { event.preventDefault(); onClose() }
      if (event.key !== 'Tab' || !dialog.current) return
      const controls = Array.from(dialog.current.querySelectorAll<HTMLElement>(
        'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href]'))
      if (!controls.length) return
      if (event.shiftKey && document.activeElement === controls[0]) {
        event.preventDefault(); controls[controls.length - 1].focus()
      } else if (!event.shiftKey && document.activeElement === controls[controls.length - 1]) {
        event.preventDefault(); controls[0].focus()
      }
    }
    window.addEventListener('keydown', keyboard)
    return () => window.removeEventListener('keydown', keyboard)
  }, [open, busy, onClose])

  async function execute(task: () => Promise<void>, message: string) {
    setError(''); setSuccess(''); setBusy(true)
    try { await task(); setSuccess(message) }
    catch (cause) { setError((cause as Error).message) }
    finally { setBusy(false) }
  }
  async function backup() {
    await execute(async () => {
      const result = await call<{id:string;mirror_healthy:boolean|null}>('/backup',
        json({reason:'author requested safety copy'}))
      await refresh()
      setSelected(result.id)
      if (result.mirror_healthy === false) {
        throw new Error('Local recovery copy was saved, but your external mirror failed. Inspect the mirror drive.')
      }
    }, 'Backup completed. Every file was copied into a versioned, verified recovery generation.')
  }
  async function saveSettings() {
    await execute(async () => {
      await call<Status>('/settings', json({
        directory: directory.trim(), mirror_directory: mirror.trim() || null,
        automatic,
      }))
      await refresh()
    }, 'Recovery settings saved. New automatic backups use these locations.')
  }
  async function verify() {
    if (!selected) return
    await execute(async () => {
      const report = await call<Verification>(
        '/generations/' + encodeURIComponent(selected) + '/verify', {method:'POST'})
      setVerification(report)
      if (!report.healthy) throw new Error(
        `Backup is damaged: ${report.bad.length} missing or incorrect file(s). Do not depend on this generation.`)
    }, 'All files in the selected backup passed SHA-256 integrity verification.')
  }
  async function restore() {
    if (!selected || !confirmation) return
    await execute(async () => {
      const output = await call<{directory:string;files:number}>(
        '/generations/' + encodeURIComponent(selected) + '/restore',
        json({confirmed:true, destination:restoreDirectory.trim() || null}))
      setRestoreResult(output)
      setConfirmation(false)
    }, 'Recovery verified and created as a separate library. Your live writing remains unchanged.')
  }
  async function syncMirror() {
    await execute(async () => {
      const result = await call<{remaining:number;error:string|null}>(
        '/mirror/synchronize', {method:'POST'})
      await refresh()
      if (result.remaining || result.error) {
        throw new Error(result.error || 'Some backup generations still need copying to the mirror.')
      }
    }, 'Independent recovery mirror is synchronized.')
  }

  if (!open) return null
  return <div className="recovery-backdrop">
    <section ref={dialog} className="recovery-center" role="dialog" aria-modal="true"
      aria-labelledby="recovery-heading">
      <header className="recovery-header">
        <div><small>AUTHOR DATA PROTECTION</small><h2 id="recovery-heading">Recovery Center</h2>
          <p>Automatic safety copies for your manuscripts, worlds, references, databases, images, and audio.</p>
        </div>
        <button type="button" aria-label="Close Recovery Center" disabled={busy}
          onClick={onClose}>✕</button>
      </header>
      {error && <p className="recovery-error" role="alert">{error}</p>}
      {success && <p className="recovery-success" role="status">{success}</p>}
      <div className="recovery-layout">
        <div className="recovery-primary">
          <section className="recovery-card">
            <h3>Protect my work</h3>
            <p>{status?.snapshot_count
              ? `${status.snapshot_count} complete backup generation(s). Latest: ${prettyDate(status.last_snapshot?.created_at || '')}`
              : 'No completed backup has been found yet. Create the first safety copy.'}</p>
            {status?.last_automatic_error && <p className="recovery-error">Last scheduled backup failed: {status.last_automatic_error}</p>}
            {status?.latest_manifest_invalid && <p className="recovery-error">A recovery manifest cannot be read. Verify another generation before relying on it.</p>}
            <button type="button" className="recovery-primary-button" disabled={busy}
              onClick={() => void backup()}>{busy ? 'Working with your recovery data…' : 'Create verified backup now'}</button>
            {status && <p className="recovery-note">
              Backup storage free: {size(status.free_bytes)}
              {status.mirror_free_bytes != null && ` · Independent mirror free: ${size(status.mirror_free_bytes)}`}
            </p>}
            {status && status.free_bytes < 4 * 1024 ** 3 &&
              <p className="recovery-error">Recovery storage is low. Older generations are never discarded automatically; arrange additional capacity before writing data grows.</p>}
            <p className="recovery-note">Automatic recovery is {automatic ? 'enabled (approximately every 15 minutes while EmberWriter is running)' : 'disabled'}. Earlier generations are retained; they are never overwritten by a later backup.</p>
          </section>
          <section className="recovery-card">
            <h3>Where safety copies live</h3>
            <label>Primary recovery folder
              <input value={directory} onChange={event => setDirectory(event.target.value)}
                placeholder="Absolute path to a dedicated recovery folder" /></label>
            <label className="recovery-check"><input type="checkbox" checked={automatic}
              onChange={event => setAutomatic(event.target.checked)} />
              <span>Back up automatically while EmberWriter is open</span></label>
            <label>Independent second copy (recommended)
              <input value={mirror} onChange={event => setMirror(event.target.value)}
                placeholder="Optional external encrypted drive folder, e.g. E:\\EmberWriterBackups" /></label>
            <p className="recovery-note">Use a physically separate, encrypted drive or trusted replicated location for the second copy. A folder on the same disk cannot protect you against disk failure, theft, or fire. Backup contents aren't encrypted by EmberWriter itself.</p>
            <div className="recovery-actions">
              <button type="button" disabled={busy || !directory.trim()}
                onClick={() => void saveSettings()}>Save backup locations</button>
              {status?.mirror_directory && <button type="button" disabled={busy}
                onClick={() => void syncMirror()}>Check & synchronize second copy</button>}
            </div>
            {status?.mirror_directory && <p className={status.mirror_latest_present ? 'recovery-success' : 'recovery-error'}>
              {status.mirror_latest_present
                ? 'The latest backup also exists in your configured mirror.'
                : 'The latest backup is not yet confirmed in your second location.'}
              {status.last_mirror_error ? ` Last error: ${status.last_mirror_error}` : ''}
            </p>}
          </section>
        </div>
        <section className="recovery-card recovery-history">
          <h3>Recover an earlier version</h3>
          <p>Choose a dated safety copy, inspect what it contains, verify it, then recover it into a separate folder. Nothing here overwrites the active library.</p>
          <label>Backup generation
            <select value={selected} onChange={event => {
              setSelected(event.target.value); setConfirmation(false); setRestoreResult(null)
            }}>
              {!generations.length && <option value="">No backups available</option>}
              {generations.map(item => <option key={item.id} value={item.id}>
                {item.invalid_manifest ? 'Damaged manifest · ' : ''}
                {item.created_at ? prettyDate(item.created_at) : item.id}
                {item.reason ? ' · ' + item.reason : ''}
              </option>)}
            </select></label>
          {preview && <div className="recovery-preview">
            <strong>{preview.total_files} files · {size(preview.bytes)}</strong>
            <p>Projects: {preview.projects.length ? preview.projects.join(', ') : 'No manuscript projects'}
              {preview.has_series ? ' · Series Vault included' : ''}
              {preview.includes_media ? ' · Media included' : ''}</p>
            <details><summary>Preview protected paths</summary>
              <ul>{preview.files.map(item => <li key={item.path}>{item.path} · {size(item.bytes)}</li>)}</ul>
            </details>
          </div>}
          <button type="button" disabled={busy || !selected || !!generations.find(g => g.id === selected)?.invalid_manifest}
            onClick={() => void verify()}>Verify this backup's files</button>
          {verification && <p className={verification.healthy ? 'recovery-success' : 'recovery-error'}>
            {verification.healthy
              ? `Verified ${verification.checked_files} / ${verification.total_files} files successfully.`
              : `Damaged: ${verification.bad.map(item => item.path).slice(0,3).join(', ')}`}</p>}
          <div className="recovery-restore">
            <h4>Recover without risking your current books</h4>
            <label>New recovered-library folder (leave blank for a safe automatic location)
              <input value={restoreDirectory} onChange={event => setRestoreDirectory(event.target.value)}
                placeholder="Create a separate recovered library" /></label>
            <label className="recovery-check"><input type="checkbox" checked={confirmation}
              onChange={event => setConfirmation(event.target.checked)} />
              <span>I understand this creates a separate recovered copy; the current library stays untouched.</span></label>
            <button type="button" className="recovery-primary-button"
              disabled={busy || !confirmation || !selected}
              onClick={() => void restore()}>Restore into a new library</button>
            {restoreResult && <div className="recovery-success">
              <strong>Recovery completed: {restoreResult.files} files</strong>
              <p>Recovered folder: <code>{restoreResult.directory}</code></p>
              <p>Inspect the files first. To open this recovered library in EmberWriter, launch the app with its <code>-DataDir</code> argument pointing to that folder. Your current work remains available.</p>
              <button type="button" onClick={() => void navigator.clipboard.writeText(restoreResult.directory)}>
                Copy recovery folder path
              </button>
            </div>}
          </div>
        </section>
      </div>
      <footer className="recovery-footer">
        <p>Trust means knowing recovery actually works: periodically verify a backup and restore a test copy. For disaster protection, maintain a second copy on independent encrypted storage.</p>
        <button type="button" disabled={busy} onClick={onClose}>Return to writing</button>
      </footer>
    </section>
  </div>
}
