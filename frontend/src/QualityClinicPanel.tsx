import { useEffect, useState } from 'react'
import './quality-clinic.css'

type Chapter = { path: string }
type Finding = { category: string; severity: string; line: number; excerpt: string; message: string }
type QualityReport = {
  path: string
  metrics: { words: number; sentences: number; average_sentence_words: number; unique_word_ratio: number; suspected_passives: number; em_dashes: number; findings: number }
  findings: Finding[]
  truncated: boolean
  method: string
}
type Props = { apiBase: string; projectSlug: string; onOpenSource: (path: string) => void }

export default function QualityClinicPanel({ apiBase, projectSlug, onOpenSource }: Props) {
  const endpoint = `${apiBase}/projects/${encodeURIComponent(projectSlug)}/quality-clinic`
  const [chapters, setChapters] = useState<Chapter[]>([])
  const [selected, setSelected] = useState('')
  const [report, setReport] = useState<QualityReport | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    setReport(null); setSelected(''); setChapters([]); setError('')
    fetch(endpoint + '/chapters')
      .then(async response => { if (!response.ok) throw new Error(`HTTP ${response.status}`); return response.json() as Promise<Chapter[]> })
      .then(items => { if (active) { setChapters(items); setSelected(items[0]?.path || '') } })
      .catch(e => { if (active) setError(String(e)) })
    return () => { active = false }
  }, [endpoint])

  async function inspect() {
    if (!selected) return
    setBusy(true); setError(''); setReport(null)
    try {
      const response = await fetch(endpoint + '/inspect?path=' + encodeURIComponent(selected))
      if (!response.ok) {
        const failure = await response.json().catch(() => ({}))
        throw new Error(failure.detail || `HTTP ${response.status}`)
      }
      setReport(await response.json() as QualityReport)
    } catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }

  return <section className="quality-clinic" aria-labelledby="quality-title">
    <div className="quality-clinic-heading">
      <div><small>THE PROSE LAB · OFFLINE DIAGNOSTICS</small><h3 id="quality-title">Quality Clinic</h3><p>Inspect words, rhythm, repetition, punctuation, possible typos, passive constructions and formulaic AI phrasing. Your work is never changed automatically.</p></div>
      <div className="quality-clinic-controls">
        <label htmlFor="quality-chapter">Manuscript chapter</label>
        <select id="quality-chapter" value={selected} onChange={e => { setSelected(e.target.value); setReport(null) }}>
          {chapters.length === 0 && <option value="">No manuscript chapters</option>}
          {chapters.map(ch => <option key={ch.path} value={ch.path}>{ch.path}</option>)}
        </select>
        <button disabled={!selected || busy} onClick={() => void inspect()}>{busy ? 'Examining…' : 'Inspect prose'}</button>
      </div>
    </div>
    {error && <p role="alert" className="quality-clinic-error">{error}</p>}
    {report && <>
      <div className="quality-clinic-metrics">
        <div><strong>{report.metrics.words.toLocaleString()}</strong><span>words</span></div>
        <div><strong>{report.metrics.average_sentence_words}</strong><span>avg words/sentence</span></div>
        <div><strong>{report.metrics.unique_word_ratio}</strong><span>unique word ratio</span></div>
        <div><strong>{report.metrics.suspected_passives}</strong><span>possible passive uses</span></div>
        <div><strong>{report.metrics.findings}</strong><span>review flags</span></div>
      </div>
      <div className="quality-clinic-report">
        <div className="quality-clinic-reporttop"><strong>Craft observations</strong><button onClick={() => onOpenSource(report.path)}>Open chapter in editor</button></div>
        {!report.findings.length && <p>Nothing flagged by the mechanical rules in this chapter. This does not mean the prose has been professionally proofread.</p>}
        {report.findings.map((finding, index) => <article key={index} className="quality-clinic-finding">
          <div><span>{finding.category}</span><small>{finding.line ? `Line ${finding.line}` : 'Chapter-wide'}</small><small>{finding.severity.replaceAll('_', ' ')}</small></div>
          <p>{finding.message}</p>
          {finding.excerpt && <blockquote>{finding.excerpt}</blockquote>}
        </article>)}
        {report.truncated && <p className="quality-clinic-warning">Result limit reached. Additional observations may exist.</p>}
      </div>
    </>}
    <p className="quality-clinic-caveat">Mechanical signals are not a comprehensive grammar checker or a score of literary merit. Creative choices, dialect, poetry, dialogue and character voice can intentionally break these patterns.</p>
  </section>
}
