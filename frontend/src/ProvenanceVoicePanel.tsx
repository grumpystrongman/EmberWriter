import { useEffect, useMemo, useState } from 'react'
import './provenance-voice.css'

type Props = {
  apiBase: string
  slug: string
  activePath?: string | null
}

type AssistanceEvent = {
  id: string
  created_at: string
  mode: string
  active_file: string | null
  output_words: number
  refined: boolean
  provider: string
  model: string
}

type AssistanceDecision = {
  assistance_event_id: string
  created_at: string
  decision: 'accepted_append' | 'accepted_replace' | 'rejected' | 'partial' | 'copied'
  active_file: string | null
  note: string
}

type ProvenanceSummary = {
  draft: { documents: number; words: number; project_hash: string }
  provenance: {
    total_revisions: number
    assistance_events: number
    assistance_decisions: number
    assistance_decision_counts: Record<string, number>
    unreviewed_assistance_events: number
    assistance_events_with_later_revisions: number
    artifacts: Record<string, number | boolean>
  }
  evidence_strength: { score: number; label: string; reasons: string[] }
  recent_assistance_events: AssistanceEvent[]
  recent_assistance_decisions: AssistanceDecision[]
  cautions: string[]
}

type VoiceFinding = {
  id: string
  label: string
  count: number
  examples: Array<{ excerpt?: string; metric?: string; baseline?: number; current?: number }>
  suggestion: string
}

type VoiceAudit = {
  scope: string
  words: number
  voice_alignment: { score: number; label: string } | null
  findings: VoiceFinding[]
  disclaimer: string
}

type ExportResult = {
  json_path: string
  markdown_path: string
  manifest_sha256: string
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
  })
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}))
    throw new Error(payload.detail || `Request failed (${response.status})`)
  }
  return response.json() as Promise<T>
}

function decisionLabel(decision: AssistanceDecision['decision']) {
  if (decision === 'accepted_append') return 'Accepted · appended'
  if (decision === 'accepted_replace') return 'Accepted · replaced selection'
  if (decision === 'partial') return 'Partially used'
  if (decision === 'copied') return 'Copied elsewhere'
  return 'Rejected'
}

export default function ProvenanceVoicePanel({ apiBase, slug, activePath }: Props) {
  const [summary, setSummary] = useState<ProvenanceSummary | null>(null)
  const [audit, setAudit] = useState<VoiceAudit | null>(null)
  const [scope, setScope] = useState<'document' | 'draft'>(activePath ? 'document' : 'draft')
  const [error, setError] = useState('')
  const [exportResult, setExportResult] = useState<ExportResult | null>(null)
  const [busy, setBusy] = useState(false)
  const [reviewBusy, setReviewBusy] = useState('')

  const decisionsByEvent = useMemo(() => {
    const map = new Map<string, AssistanceDecision>()
    for (const decision of summary?.recent_assistance_decisions || []) map.set(decision.assistance_event_id, decision)
    return map
  }, [summary])

  const acceptedCount = useMemo(() => {
    const counts = summary?.provenance.assistance_decision_counts || {}
    return (counts.accepted_append || 0) + (counts.accepted_replace || 0)
  }, [summary])

  async function load(nextScope = scope) {
    setBusy(true)
    setError('')
    try {
      const auditUrl = nextScope === 'document' && activePath
        ? `${apiBase}/projects/${slug}/voice-audit?path=${encodeURIComponent(activePath)}`
        : `${apiBase}/projects/${slug}/voice-audit`
      const [nextSummary, nextAudit] = await Promise.all([
        request<ProvenanceSummary>(`${apiBase}/projects/${slug}/provenance`),
        request<VoiceAudit>(auditUrl),
      ])
      setSummary(nextSummary)
      setAudit(nextAudit)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load provenance and voice audit')
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    const nextScope = activePath ? 'document' : 'draft'
    setScope(nextScope)
    void load(nextScope)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug, activePath])

  async function changeScope(nextScope: 'document' | 'draft') {
    setScope(nextScope)
    await load(nextScope)
  }

  async function exportEvidence() {
    setBusy(true)
    setError('')
    try {
      const result = await request<ExportResult>(`${apiBase}/projects/${slug}/provenance/export`, { method: 'POST' })
      setExportResult(result)
      const nextSummary = await request<ProvenanceSummary>(`${apiBase}/projects/${slug}/provenance`)
      setSummary(nextSummary)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not export provenance report')
    } finally {
      setBusy(false)
    }
  }

  async function reviewSuggestion(event: AssistanceEvent, decision: AssistanceDecision['decision']) {
    setReviewBusy(event.id)
    setError('')
    try {
      await request(`${apiBase}/projects/${slug}/provenance/assistance/${event.id}/decision`, {
        method: 'POST',
        body: JSON.stringify({
          decision,
          active_file: event.active_file || activePath || null,
          note: '',
        }),
      })
      setSummary(await request<ProvenanceSummary>(`${apiBase}/projects/${slug}/provenance`))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not record the review decision')
    } finally {
      setReviewBusy('')
    }
  }

  return (
    <section className="provenance-voice-panel">
      <div className="provenance-voice-header">
        <div>
          <small>PROVENANCE · VOICE FIDELITY</small>
          <h2>Creative Process Evidence</h2>
          <p>Document how the book evolved, then compare current prose with the voice EmberWriter learned from your manuscript.</p>
        </div>
        <div className="provenance-voice-actions">
          <button className="provenance-button" disabled={busy} onClick={() => void load()}>Refresh</button>
          <button className="provenance-button" disabled={busy || !summary} onClick={() => void exportEvidence()}>Export report</button>
        </div>
      </div>

      {summary && (
        <>
          <div className="provenance-stat-grid">
            <div className="provenance-stat"><small>Internal evidence</small><strong>{summary.evidence_strength.label} · {summary.evidence_strength.score}/100</strong></div>
            <div className="provenance-stat"><small>Recoverable revisions</small><strong>{summary.provenance.total_revisions}</strong></div>
            <div className="provenance-stat"><small>Assistance events</small><strong>{summary.provenance.assistance_events}</strong></div>
            <div className="provenance-stat"><small>Suggestions reviewed</small><strong>{summary.provenance.assistance_decisions}</strong></div>
            <div className="provenance-stat"><small>Later author revisions</small><strong>{summary.provenance.assistance_events_with_later_revisions}</strong></div>
          </div>
          <p className="provenance-note">
            Draft fingerprint: {summary.draft.project_hash.slice(0, 20)}… · {summary.draft.documents} documents · {summary.draft.words.toLocaleString()} words
            {' · '}{acceptedCount} accepted · {summary.provenance.assistance_decision_counts.rejected || 0} rejected · {summary.provenance.assistance_decision_counts.partial || 0} partial · {summary.provenance.unreviewed_assistance_events} unreviewed
          </p>
        </>
      )}

      {summary && summary.recent_assistance_events.length > 0 && (
        <div className="assistance-review-section">
          <div className="voice-audit-toolbar">
            <div>
              <h3>Suggestion Review Ledger</h3>
              <p>Record what you actually did with recent Ember suggestions. Generation alone is never treated as acceptance.</p>
            </div>
          </div>
          <div className="assistance-review-list">
            {summary.recent_assistance_events.slice(0, 10).map((event) => {
              const decision = decisionsByEvent.get(event.id)
              return (
                <article className="assistance-review-row" key={event.id}>
                  <div className="assistance-review-copy">
                    <small>{event.mode} · {event.output_words.toLocaleString()} words · {event.model || event.provider}</small>
                    <strong>{event.active_file || 'No manuscript file attached'}</strong>
                    <span>{new Date(event.created_at).toLocaleString()}</span>
                    {decision && <em>Recorded: {decisionLabel(decision.decision)}</em>}
                  </div>
                  <div className="assistance-review-actions">
                    <button className="provenance-button" disabled={reviewBusy === event.id} onClick={() => void reviewSuggestion(event, 'accepted_append')}>Accepted · append</button>
                    <button className="provenance-button" disabled={reviewBusy === event.id} onClick={() => void reviewSuggestion(event, 'accepted_replace')}>Accepted · replace</button>
                    <button className="provenance-button" disabled={reviewBusy === event.id} onClick={() => void reviewSuggestion(event, 'partial')}>Partial</button>
                    <button className="provenance-button" disabled={reviewBusy === event.id} onClick={() => void reviewSuggestion(event, 'copied')}>Copied</button>
                    <button className="provenance-button" disabled={reviewBusy === event.id} onClick={() => void reviewSuggestion(event, 'rejected')}>Rejected</button>
                  </div>
                </article>
              )
            })}
          </div>
          <p className="provenance-note">A later choice replaces the earlier classification for the same suggestion, so the ledger reflects your final review outcome.</p>
        </div>
      )}

      <div className="voice-audit-section">
        <div className="voice-audit-toolbar">
          <div><h3>Voice Fidelity Audit</h3><p>Flags overly uniform cadence, repeated scaffolding, symmetrical phrasing, and drift from your learned voice.</p></div>
          <div className="provenance-voice-actions">
            <button className="provenance-button" disabled={busy || !activePath} onClick={() => void changeScope('document')}>Current document</button>
            <button className="provenance-button" disabled={busy} onClick={() => void changeScope('draft')}>Whole Draft</button>
          </div>
        </div>

        {audit && (
          <>
            <p className="provenance-note">
              Scope: {audit.scope} · {audit.words.toLocaleString()} words
              {audit.voice_alignment ? ` · Voice alignment ${audit.voice_alignment.score}/100 (${audit.voice_alignment.label})` : ' · Learn a Voice Profile to enable alignment scoring'}
            </p>
            {audit.findings.length === 0 ? (
              <p className="provenance-note">No material voice-fidelity findings in this scope.</p>
            ) : (
              <div className="voice-findings">
                {audit.findings.map((finding) => (
                  <article className="voice-finding" key={finding.id}>
                    <small>{finding.count} finding{finding.count === 1 ? '' : 's'}</small>
                    <h4>{finding.label}</h4>
                    <p>{finding.suggestion}</p>
                    {finding.examples[0]?.excerpt && <blockquote>{finding.examples[0].excerpt}</blockquote>}
                  </article>
                ))}
              </div>
            )}
            <p className="provenance-note" style={{ marginTop: '0.8rem' }}>{audit.disclaimer}</p>
          </>
        )}
      </div>

      {exportResult && (
        <div className="provenance-export-result">
          Exported {exportResult.markdown_path} · manifest {exportResult.manifest_sha256.slice(0, 20)}…
        </div>
      )}
      {error && <div className="provenance-error">{error}</div>}
    </section>
  )
}