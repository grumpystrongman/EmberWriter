import { useEffect, useMemo, useState } from 'react'

import './submission.css'

type SubmissionMethod = 'email' | 'query_manager' | 'web_form' | 'postal' | 'other'
type TargetKind = 'agent' | 'publisher' | 'editor' | 'contest' | 'other'
type SampleKind = 'none' | 'pages' | 'chapters' | 'words' | 'full'
type AttachmentMode = 'body' | 'attachments' | 'mixed'
type ManuscriptPreset = 'standard_novel' | 'shunn_classic'
type SubmissionStatus = 'draft' | 'ready' | 'sent' | 'partial_requested' | 'full_requested' | 'revision_requested' | 'offer' | 'pass' | 'withdrawn'
type DraftKind = 'query' | 'synopsis' | 'pitch' | 'bio'

type Destination = {
  id: string
  name: string
  kind: TargetKind
  contact_name: string
  email: string
  submission_url: string
  guidelines_url: string
  method: SubmissionMethod
  query_required: boolean
  synopsis_required: boolean
  bio_required: boolean
  sample_kind: SampleKind
  sample_count: number
  attachment_mode: AttachmentMode
  accepted_formats: string[]
  simultaneous_submissions_allowed: boolean | null
  expected_response_days: number | null
  notes: string
}

type SubmissionRecord = {
  id: string
  destination_id: string
  status: SubmissionStatus
  package_id: string
  submitted_at: string
  follow_up_on: string
  response_at: string
  notes: string
  created_at: string
  updated_at: string
}

type SubmissionProfile = {
  schema_version: number
  author_name: string
  email: string
  phone: string
  address: string
  website: string
  title: string
  genre: string
  word_count: number
  logline: string
  pitch: string
  query_letter: string
  synopsis: string
  bio: string
  comp_titles: string[]
  manuscript_preset: ManuscriptPreset
  destinations: Destination[]
  records: SubmissionRecord[]
}

type ValidationIssue = {
  level: 'error' | 'warning' | 'info'
  code: string
  message: string
  destination_id: string | null
}

type Validation = {
  valid: boolean
  issues: ValidationIssue[]
  destination_id: string
  sample_description: string
}

type PackageArtifact = {
  format: 'zip' | 'json' | 'docx' | 'pdf' | 'txt'
  filename: string
  relative_path: string
  bytes: number
}

type BuildResult = {
  package_id: string
  validation: Validation
  artifacts: PackageArtifact[]
  included_files: string[]
  profile: SubmissionProfile | null
}

type Provider = {
  provider: 'ollama' | 'openai_compatible'
  base_url: string
  model: string
  api_key?: string
}

type Props = {
  apiBase: string
  slug: string
  disabled: boolean
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || `${response.status} ${response.statusText}`)
  }
  return response.json() as Promise<T>
}

function splitLines(value: string) {
  return value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean)
}

function humanBytes(value: number) {
  if (value < 1024 * 1024) return `${Math.max(1, Math.round(value / 1024)).toLocaleString()} KB`
  return `${(value / (1024 * 1024)).toFixed(1)} MB`
}

function newDestination(): Destination {
  return {
    id: crypto.randomUUID(),
    name: 'New submission target',
    kind: 'agent',
    contact_name: '',
    email: '',
    submission_url: '',
    guidelines_url: '',
    method: 'email',
    query_required: true,
    synopsis_required: false,
    bio_required: false,
    sample_kind: 'pages',
    sample_count: 10,
    attachment_mode: 'body',
    accepted_formats: ['docx'],
    simultaneous_submissions_allowed: null,
    expected_response_days: null,
    notes: '',
  }
}

function providerFromStorage(): Provider | null {
  try {
    const raw = localStorage.getItem('emberwriter.provider')
    if (!raw) return null
    const parsed = JSON.parse(raw) as Provider
    return parsed.model?.trim() ? parsed : null
  } catch {
    return null
  }
}

export default function SubmissionPanel({ apiBase, slug, disabled }: Props) {
  const [profile, setProfile] = useState<SubmissionProfile | null>(null)
  const [selectedDestinationId, setSelectedDestinationId] = useState('')
  const [validation, setValidation] = useState<Validation | null>(null)
  const [result, setResult] = useState<BuildResult | null>(null)
  const [busy, setBusy] = useState(false)
  const [drafting, setDrafting] = useState<DraftKind | ''>('')
  const [draftEvidence, setDraftEvidence] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    setError('')
    setResult(null)
    void request<SubmissionProfile>(`${apiBase}/projects/${slug}/submissions/profile`)
      .then((next) => {
        setProfile(next)
        setSelectedDestinationId(next.destinations[0]?.id || '')
      })
      .catch((cause) => setError((cause as Error).message))
  }, [apiBase, slug])

  const selectedDestination = useMemo(
    () => profile?.destinations.find((item) => item.id === selectedDestinationId) || null,
    [profile, selectedDestinationId],
  )

  const destinationRecords = useMemo(
    () => profile?.records.filter((item) => item.destination_id === selectedDestinationId) || [],
    [profile, selectedDestinationId],
  )

  useEffect(() => {
    if (!profile || !selectedDestinationId) {
      setValidation(null)
      return
    }
    const timer = window.setTimeout(() => {
      void request<Validation>(`${apiBase}/projects/${slug}/submissions/validate`, {
        method: 'POST',
        body: JSON.stringify({ destination_id: selectedDestinationId, profile }),
      })
        .then(setValidation)
        .catch((cause) => setError((cause as Error).message))
    }, 350)
    return () => window.clearTimeout(timer)
  }, [apiBase, slug, profile, selectedDestinationId])

  function updateDestination(patch: Partial<Destination>) {
    if (!profile || !selectedDestination) return
    setProfile({
      ...profile,
      destinations: profile.destinations.map((item) =>
        item.id === selectedDestination.id ? { ...item, ...patch } : item,
      ),
    })
    setResult(null)
  }

  function addDestination() {
    if (!profile) return
    const next = newDestination()
    setProfile({ ...profile, destinations: [...profile.destinations, next] })
    setSelectedDestinationId(next.id)
    setResult(null)
  }

  function removeDestination() {
    if (!profile || !selectedDestination) return
    const next = profile.destinations.filter((item) => item.id !== selectedDestination.id)
    setProfile({ ...profile, destinations: next })
    setSelectedDestinationId(next[0]?.id || '')
    setValidation(null)
    setResult(null)
  }

  async function save() {
    if (!profile || busy) return
    setBusy(true)
    setError('')
    try {
      setProfile(await request<SubmissionProfile>(`${apiBase}/projects/${slug}/submissions/profile`, {
        method: 'PUT',
        body: JSON.stringify(profile),
      }))
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function draft(kind: DraftKind) {
    if (!profile || drafting || busy) return
    const provider = providerFromStorage()
    if (!provider) {
      setError('Choose a model in Ember model settings before drafting submission material.')
      return
    }
    setDrafting(kind)
    setDraftEvidence('')
    setError('')
    try {
      const response = await request<{
        text: string
        context_documents: number
        used_story_summaries: boolean
      }>(`${apiBase}/projects/${slug}/submissions/draft`, {
        method: 'POST',
        body: JSON.stringify({
          kind,
          provider,
          destination_id: selectedDestinationId || null,
          profile,
        }),
      })
      const patch = kind === 'query'
        ? { query_letter: response.text }
        : kind === 'synopsis'
          ? { synopsis: response.text }
          : kind === 'pitch'
            ? { pitch: response.text }
            : { bio: response.text }
      setProfile({ ...profile, ...patch })
      setDraftEvidence(
        `Draft grounded in ${response.context_documents} Binder document${response.context_documents === 1 ? '' : 's'}${response.used_story_summaries ? ' with current Story Memory summaries' : ' using manuscript excerpts'}.`,
      )
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setDrafting('')
    }
  }

  async function build() {
    if (!profile || !selectedDestinationId || busy || drafting) return
    setBusy(true)
    setError('')
    try {
      const built = await request<BuildResult>(`${apiBase}/projects/${slug}/submissions/build`, {
        method: 'POST',
        body: JSON.stringify({ destination_id: selectedDestinationId, profile }),
      })
      setResult(built)
      setValidation(built.validation)
      if (built.profile) setProfile(built.profile)
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function updateRecord(record: SubmissionRecord, patch: Partial<SubmissionRecord>) {
    if (busy) return
    setBusy(true)
    setError('')
    try {
      setProfile(await request<SubmissionProfile>(`${apiBase}/projects/${slug}/submissions/records/${record.id}`, {
        method: 'PATCH',
        body: JSON.stringify(patch),
      }))
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  if (!profile) {
    return (
      <details className="authoring-panel submission-panel">
        <summary>Traditional Submission Studio <small>Loading…</small></summary>
        <div className="authoring-panel-body">{error && <small className="panel-error">{error}</small>}</div>
      </details>
    )
  }

  return (
    <details className="authoring-panel submission-panel">
      <summary>Traditional Submission Studio <small>query · synopsis · samples · tracker</small></summary>
      <div className="authoring-panel-body submission-body">
        <div className="submission-grid">
          <label>Author / pen name<input value={profile.author_name} onChange={(event) => setProfile({ ...profile, author_name: event.target.value })} disabled={disabled || busy} /></label>
          <label>Manuscript title<input value={profile.title} onChange={(event) => setProfile({ ...profile, title: event.target.value })} disabled={disabled || busy} /></label>
          <label>Genre / category<input value={profile.genre} onChange={(event) => setProfile({ ...profile, genre: event.target.value })} placeholder="Adult dark fantasy" disabled={disabled || busy} /></label>
          <label>Word count<input type="number" min="0" value={profile.word_count} onChange={(event) => setProfile({ ...profile, word_count: Number(event.target.value) })} disabled={disabled || busy} /></label>
          <label>Submission manuscript preset<select value={profile.manuscript_preset} onChange={(event) => setProfile({ ...profile, manuscript_preset: event.target.value as ManuscriptPreset })} disabled={disabled || busy}><option value="standard_novel">Modern standard novel</option><option value="shunn_classic">Shunn-style classic / Courier</option></select></label>
          <label>Comparable titles<input value={profile.comp_titles.join(', ')} onChange={(event) => setProfile({ ...profile, comp_titles: event.target.value.split(',').map((item) => item.trim()).filter(Boolean) })} disabled={disabled || busy} /></label>
          <label>Email<input value={profile.email} onChange={(event) => setProfile({ ...profile, email: event.target.value })} disabled={disabled || busy} /></label>
          <label>Phone<input value={profile.phone} onChange={(event) => setProfile({ ...profile, phone: event.target.value })} disabled={disabled || busy} /></label>
          <label className="submission-wide">Mailing address<textarea rows={2} value={profile.address} onChange={(event) => setProfile({ ...profile, address: event.target.value })} disabled={disabled || busy} /></label>
          <label className="submission-wide">Website<input value={profile.website} onChange={(event) => setProfile({ ...profile, website: event.target.value })} disabled={disabled || busy} /></label>
        </div>

        <div className="submission-materials">
          <label>Logline<textarea rows={2} value={profile.logline} onChange={(event) => setProfile({ ...profile, logline: event.target.value })} disabled={disabled || busy} /></label>
          <label>Pitch <button type="button" onClick={() => void draft('pitch')} disabled={disabled || busy || Boolean(drafting)}>{drafting === 'pitch' ? 'Drafting…' : 'AI draft'}</button><textarea rows={4} value={profile.pitch} onChange={(event) => setProfile({ ...profile, pitch: event.target.value })} disabled={disabled || busy} /></label>
          <label>Query letter <button type="button" onClick={() => void draft('query')} disabled={disabled || busy || Boolean(drafting)}>{drafting === 'query' ? 'Drafting…' : 'AI draft'}</button><textarea rows={10} value={profile.query_letter} onChange={(event) => setProfile({ ...profile, query_letter: event.target.value })} disabled={disabled || busy} /></label>
          <label>Synopsis <button type="button" onClick={() => void draft('synopsis')} disabled={disabled || busy || Boolean(drafting)}>{drafting === 'synopsis' ? 'Drafting…' : 'AI draft'}</button><textarea rows={12} value={profile.synopsis} onChange={(event) => setProfile({ ...profile, synopsis: event.target.value })} disabled={disabled || busy} /></label>
          <label>Author bio <button type="button" onClick={() => void draft('bio')} disabled={disabled || busy || Boolean(drafting)}>{drafting === 'bio' ? 'Drafting…' : 'AI draft'}</button><textarea rows={4} value={profile.bio} onChange={(event) => setProfile({ ...profile, bio: event.target.value })} disabled={disabled || busy} /></label>
          {draftEvidence && <small className="panel-help">{draftEvidence}</small>}
        </div>

        <div className="submission-target-toolbar">
          <select value={selectedDestinationId} onChange={(event) => setSelectedDestinationId(event.target.value)} disabled={disabled || busy}>
            <option value="">Choose an agent / publisher…</option>
            {profile.destinations.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
          <button type="button" onClick={addDestination} disabled={disabled || busy}>+ Target</button>
          {selectedDestination && <button type="button" onClick={removeDestination} disabled={disabled || busy}>Remove</button>}
        </div>

        {selectedDestination && (
          <section className="submission-target-card">
            <div className="submission-grid">
              <label>Name<input value={selectedDestination.name} onChange={(event) => updateDestination({ name: event.target.value })} disabled={disabled || busy} /></label>
              <label>Type<select value={selectedDestination.kind} onChange={(event) => updateDestination({ kind: event.target.value as TargetKind })} disabled={disabled || busy}><option value="agent">Agent</option><option value="publisher">Publisher</option><option value="editor">Editor</option><option value="contest">Contest</option><option value="other">Other</option></select></label>
              <label>Contact<input value={selectedDestination.contact_name} onChange={(event) => updateDestination({ contact_name: event.target.value })} disabled={disabled || busy} /></label>
              <label>Method<select value={selectedDestination.method} onChange={(event) => updateDestination({ method: event.target.value as SubmissionMethod })} disabled={disabled || busy}><option value="email">Email</option><option value="query_manager">QueryManager</option><option value="web_form">Web form</option><option value="postal">Postal</option><option value="other">Other</option></select></label>
              <label>Email<input value={selectedDestination.email} onChange={(event) => updateDestination({ email: event.target.value })} disabled={disabled || busy} /></label>
              <label>Submission portal<input value={selectedDestination.submission_url} onChange={(event) => updateDestination({ submission_url: event.target.value })} disabled={disabled || busy} /></label>
              <label className="submission-wide">Guidelines URL<input value={selectedDestination.guidelines_url} onChange={(event) => updateDestination({ guidelines_url: event.target.value })} placeholder="Current authoritative submission page" disabled={disabled || busy} /></label>
              <label>Sample<select value={selectedDestination.sample_kind} onChange={(event) => updateDestination({ sample_kind: event.target.value as SampleKind })} disabled={disabled || busy}><option value="none">None</option><option value="pages">First pages</option><option value="chapters">First chapters</option><option value="words">First words</option><option value="full">Full manuscript</option></select></label>
              {selectedDestination.sample_kind !== 'none' && selectedDestination.sample_kind !== 'full' && <label>Amount<input type="number" min="1" value={selectedDestination.sample_count} onChange={(event) => updateDestination({ sample_count: Number(event.target.value) })} disabled={disabled || busy} /></label>}
              <label>Delivery<select value={selectedDestination.attachment_mode} onChange={(event) => updateDestination({ attachment_mode: event.target.value as AttachmentMode })} disabled={disabled || busy}><option value="body">Paste in body/form</option><option value="attachments">Attachments</option><option value="mixed">Mixed</option></select></label>
              <label>Accepted attachment formats<input value={selectedDestination.accepted_formats.join(', ')} onChange={(event) => updateDestination({ accepted_formats: event.target.value.split(',').map((item) => item.trim().replace(/^\./, '')).filter(Boolean) })} disabled={disabled || busy} /></label>
              <label>Expected response days<input type="number" min="1" max="730" value={selectedDestination.expected_response_days ?? ''} onChange={(event) => updateDestination({ expected_response_days: event.target.value ? Number(event.target.value) : null })} disabled={disabled || busy} /></label>
              <label>Simultaneous submissions<select value={selectedDestination.simultaneous_submissions_allowed === null ? 'unknown' : String(selectedDestination.simultaneous_submissions_allowed)} onChange={(event) => updateDestination({ simultaneous_submissions_allowed: event.target.value === 'unknown' ? null : event.target.value === 'true' })} disabled={disabled || busy}><option value="unknown">Unknown</option><option value="true">Allowed</option><option value="false">Not allowed</option></select></label>
            </div>
            <div className="submission-requirements">
              <label><input type="checkbox" checked={selectedDestination.query_required} onChange={(event) => updateDestination({ query_required: event.target.checked })} disabled={disabled || busy} /> Query required</label>
              <label><input type="checkbox" checked={selectedDestination.synopsis_required} onChange={(event) => updateDestination({ synopsis_required: event.target.checked })} disabled={disabled || busy} /> Synopsis required</label>
              <label><input type="checkbox" checked={selectedDestination.bio_required} onChange={(event) => updateDestination({ bio_required: event.target.checked })} disabled={disabled || busy} /> Bio required</label>
            </div>
            <label className="submission-notes">Guideline notes<textarea rows={5} value={selectedDestination.notes} onChange={(event) => updateDestination({ notes: event.target.value })} placeholder="Exact subject line, pasted pages, no attachments, one agent at a time, response window…" disabled={disabled || busy} /></label>
          </section>
        )}

        {validation && (
          <div className={`submission-validation ${validation.valid ? 'valid' : 'invalid'}`}>
            <strong>{validation.valid ? 'Handoff passes Ember blocking checks' : 'Submission has blocking issues'}</strong>
            <small>{validation.sample_description}</small>
            {validation.issues.map((issue, index) => <small className={`submission-issue issue-${issue.level}`} key={`${issue.code}-${index}`}><b>{issue.level.toUpperCase()}</b> {issue.message}</small>)}
          </div>
        )}

        <div className="submission-actions">
          <button type="button" onClick={() => void save()} disabled={disabled || busy}>{busy ? 'Working…' : 'Save submission workspace'}</button>
          <button type="button" className="primary" onClick={() => void build()} disabled={disabled || busy || Boolean(drafting) || !selectedDestinationId || validation?.valid === false}>Build submission handoff package</button>
        </div>

        {result && (
          <div className="publish-result submission-result">
            <strong>Package {result.package_id} ready</strong>
            {result.artifacts.map((artifact) => {
              const url = `${apiBase}/projects/${slug}/exports/download?path=${encodeURIComponent(artifact.relative_path)}`
              return <a key={artifact.relative_path} href={url} download={artifact.filename}>Download {artifact.filename} <small>{humanBytes(artifact.bytes)}</small></a>
            })}
          </div>
        )}

        {destinationRecords.length > 0 && (
          <details className="submission-history" open>
            <summary>Submission history ({destinationRecords.length})</summary>
            {destinationRecords.slice().reverse().map((record) => (
              <article key={record.id}>
                <div><strong>{record.status.replaceAll('_', ' ')}</strong><small>{record.package_id}</small></div>
                <select value={record.status} onChange={(event) => void updateRecord(record, { status: event.target.value as SubmissionStatus })} disabled={disabled || busy}>
                  {(['ready', 'sent', 'partial_requested', 'full_requested', 'revision_requested', 'offer', 'pass', 'withdrawn'] as SubmissionStatus[]).map((status) => <option key={status} value={status}>{status.replaceAll('_', ' ')}</option>)}
                </select>
                <label>Sent<input type="date" value={record.submitted_at.slice(0, 10)} onChange={(event) => void updateRecord(record, { submitted_at: event.target.value })} disabled={disabled || busy} /></label>
                <label>Follow up<input type="date" value={record.follow_up_on.slice(0, 10)} onChange={(event) => void updateRecord(record, { follow_up_on: event.target.value })} disabled={disabled || busy} /></label>
                <label>Response<input type="date" value={record.response_at.slice(0, 10)} onChange={(event) => void updateRecord(record, { response_at: event.target.value })} disabled={disabled || busy} /></label>
              </article>
            ))}
          </details>
        )}

        <small className="panel-help">Agent and publisher rules are destination-specific. Ember's preset creates a clean manuscript handoff, but the saved current guideline page always overrides the preset. Ember prepares and tracks submissions; it does not send them automatically.</small>
        {error && <small className="panel-error">{error}</small>}
      </div>
    </details>
  )
}
