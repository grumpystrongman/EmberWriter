import { useEffect, useState } from 'react'
import './revision-workbench.css'

type Proposal = {
  id: string; status: string; stale: boolean; created_at: string; model: string
  source_words: number; proposed_words: number; accepted_findings: number
  author_direction: string
}
type Preview = Proposal & {
  proposed_text: string; current_text: string
  metrics: { added_lines: number; removed_lines: number; unchanged_lines: number }
  quality_before: { findings: number }; quality_after: { findings: number }
}
type Props = { apiBase: string; projectSlug: string; chapter: number; model: string; onChanged: () => void }

export default function RevisionWorkbench({ apiBase, projectSlug, chapter, model, onChanged }: Props) {
  const endpoint = `${apiBase}/projects/${encodeURIComponent(projectSlug)}/book-revisions/${chapter}`
  const [proposals, setProposals] = useState<Proposal[]>([])
  const [selected, setSelected] = useState<Preview | null>(null)
  const [direction, setDirection] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  async function request<T>(suffix = '', method = 'GET', body?: unknown): Promise<T> {
    const result = await fetch(endpoint + suffix, {
      method, headers: { 'Content-Type': 'application/json' },
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
    })
    if (!result.ok) {
      const value = await result.json().catch(() => ({}))
      throw new Error(value.detail || `HTTP ${result.status}`)
    }
    return result.json() as Promise<T>
  }
  async function refresh() {
    const data = await request<{ proposals: Proposal[] }>()
    setProposals(data.proposals)
  }
  useEffect(() => {
    setSelected(null); setProposals([]); setError(''); setNotice('')
    void refresh().catch(e => setError(String(e)))
  }, [endpoint])
  async function generate() {
    setBusy(true); setError(''); setNotice('')
    try {
      if (!model.trim()) throw new Error('Select an installed local model first.')
      const result = await request<Preview>('/propose', 'POST', {
        provider: { provider: 'ollama', base_url: 'http://127.0.0.1:11434', model },
        author_direction: direction,
      })
      setSelected(result)
      await refresh()
      setNotice('Revision proposed. Compare the text before accepting any change.')
    } catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }
  async function inspect(id: string) {
    setError('')
    try { setSelected(await request<Preview>(`/${id}`)) }
    catch (e) { setError(String(e)) }
  }
  async function decide(action: 'accept' | 'reject') {
    if (!selected) return
    setBusy(true); setError('')
    try {
      await request(`/${selected.id}/decision`, 'POST', { action })
      await refresh()
      setSelected(null)
      setNotice(action === 'accept'
        ? 'Your approved revision replaced the draft candidate. The original was archived; previous reader reviews are now stale.'
        : 'Revision rejected. Your original chapter remains unchanged.')
      if (action === 'accept') onChanged()
    } catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }
  return <section className="revision-workbench" aria-label="Revision workbench">
    <div className="revision-workbench-hero">
      <div><small>REVISION INTELLIGENCE · LOCAL ONLY</small><h4>Revision Workbench</h4>
        <p>Combine accepted reader findings with your own direction. EmberWriter creates a complete alternative chapter, never an automatic replacement.</p></div>
    </div>
    <label>Additional author direction (optional)
      <textarea maxLength={2000} value={direction} onChange={e => setDirection(e.target.value)}
        placeholder="Keep the captain's anger understated. Make the revelation happen in dialogue, but preserve the ending." />
    </label>
    <button disabled={busy || !model.trim()} onClick={() => void generate()}>
      {busy ? 'Creating alternative draft…' : 'Propose a revised chapter'}
    </button>
    <p className="revision-workbench-note">A revision requires at least one accepted reader finding or your own direction. No local files are changed while generating the proposal.</p>
    {error && <p role="alert" className="revision-workbench-error">{error}</p>}
    {notice && <p role="status" className="revision-workbench-success">{notice}</p>}
    {proposals.length > 0 && <div className="revision-workbench-history">
      <strong>Revision history</strong>
      {proposals.map(p => <button key={p.id} onClick={() => void inspect(p.id)} className={selected?.id === p.id ? 'active' : ''}>
        {p.status.toUpperCase()} · {p.source_words} → {p.proposed_words} words · {p.stale ? 'OLDER DRAFT' : 'CURRENT DRAFT'} · {new Date(p.created_at).toLocaleString()}
      </button>)}
    </div>}
    {selected && <div className="revision-workbench-preview">
      <div className="revision-workbench-summary">
        <strong>Compare before you approve</strong>
        <span>{selected.metrics.added_lines} lines added or rewritten · {selected.metrics.removed_lines} removed or rewritten</span>
        <span>Mechanical flags: {selected.quality_before.findings} → {selected.quality_after.findings}</span>
        <small>These metrics are descriptive, not a quality verdict.</small>
      </div>
      <div className="revision-workbench-columns">
        <section><h5>Original candidate (preserved)</h5><pre>{selected.current_text}</pre></section>
        <section><h5>Proposed revision</h5><pre>{selected.proposed_text}</pre></section>
      </div>
      {selected.status === 'proposed' && !selected.stale
        ? <div className="revision-workbench-approval">
          <button disabled={busy} onClick={() => void decide('accept')}>Accept revision (archive original)</button>
          <button disabled={busy} onClick={() => void decide('reject')}>Reject revision</button>
        </div>
        : <p className="revision-workbench-note">This proposal has been decided or is based on an older draft; it cannot overwrite the current chapter.</p>}
    </div>}
  </section>
}
