import { useEffect, useState } from 'react'
import { Dialect, WorkerLinter } from 'harper.js'
import { binary } from 'harper.js/binary'
import './quality-clinic.css'

type Chapter = { path: string }
type GrammarFinding = {path:string; start:number; end:number; line:number; excerpt:string; message:string; suggestions:string[]}
type GrammarReport = {chapters:number; findings:GrammarFinding[]; total:number; incomplete:boolean; message:string}
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
  const [grammar, setGrammar] = useState<GrammarReport | null>(null)
  const [grammarBusy, setGrammarBusy] = useState(false)
  const [grammarProgress, setGrammarProgress] = useState('')

  useEffect(() => {
    let active = true
    setReport(null); setSelected(''); setChapters([]); setError(''); setGrammar(null)
    fetch(endpoint + '/chapters')
      .then(async response => { if (!response.ok) throw new Error(`HTTP ${response.status}`); return response.json() as Promise<Chapter[]> })
      .then(items => { if (active) { setChapters(items); setSelected(items[0]?.path || '') } })
      .catch(e => { if (active) setError(String(e)) })
    return () => { active = false }
  }, [endpoint])

  async function inspectGrammar(wholeBook: boolean) {
    if (!selected) return
    setGrammarBusy(true); setError(''); setGrammar(null)
    const linter = new WorkerLinter({binary, dialect: Dialect.American})
    const scope = wholeBook ? chapters : [{path:selected}]
    let total = 0
    const matches: GrammarFinding[] = []
    let scanned = 0
    let incomplete = false
    try {
      await linter.setup()
      for (const chapter of scope) {
        setGrammarProgress(`Proofreading chapter ${scanned + 1} of ${scope.length} locally…`)
        const response = await fetch(endpoint + '/source?path=' + encodeURIComponent(chapter.path))
        if (!response.ok) {
          const detail = await response.json().catch(() => ({}))
          throw new Error(detail.detail || 'Could not access a local manuscript chapter')
        }
        const {text} = await response.json() as {text:string}
        // Chunk at paragraph boundaries near 12k characters so WASM remains
        // responsive for a book-length scan, while preserving source offsets.
        let start = 0
        while (start < text.length) {
          const limit = Math.min(start + 12000, text.length)
          let end = limit
          if (limit < text.length) {
            const boundary = text.lastIndexOf('\n\n', limit)
            if (boundary > start + 4000) end = boundary + 2
          }
          const chunk = text.slice(start, end)
          const findings = await linter.lint(chunk, {language:chapter.path.endsWith('.md') ? 'markdown' : 'plaintext'})
          total += findings.length
          for (const lint of findings) {
            if (matches.length >= 700) {incomplete = true;continue}
            const span = lint.span()
            const begin = Math.max(0, Math.min(text.length, start + span.start))
            const finish = Math.max(begin, Math.min(text.length, start + span.end))
            matches.push({
              path:chapter.path, start:begin, end:finish,
              line: text.slice(0, begin).split('\n').length,
              excerpt:text.slice(Math.max(0, begin-60), Math.min(text.length, finish+80)).replace(/\s+/g,' ').slice(0,180),
              message:lint.message(),
              suggestions:lint.suggestions().slice(0,3).map(suggestion=>suggestion.get_replacement_text()),
            })
          }
          start = end
        }
        scanned += 1
      }
      setGrammar({chapters:scanned, findings:matches, total, incomplete,
        message:'Harper English grammar, usage and spelling checks run in a local browser Web Worker; no manuscript is sent to an online proofreading service. Suggestions require author review.'})
    } catch (e) {setError(String(e))}
    finally {
      await linter.dispose()
      setGrammarBusy(false); setGrammarProgress('')
    }
  }

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
        <select id="quality-chapter" value={selected} onChange={e => { setSelected(e.target.value); setReport(null); setGrammar(null) }}>
          {chapters.length === 0 && <option value="">No manuscript chapters</option>}
          {chapters.map(ch => <option key={ch.path} value={ch.path}>{ch.path}</option>)}
        </select>
        <button disabled={!selected || busy} onClick={() => void inspect()}>{busy ? 'Examining…' : 'Inspect prose'}</button>
        <button disabled={!selected || grammarBusy} onClick={() => void inspectGrammar(false)}>
          {grammarBusy ? 'Proofreading…' : 'Run offline grammar on chapter'}</button>
        <button disabled={!selected || !chapters.length || grammarBusy} onClick={() => void inspectGrammar(true)}>
          Run offline grammar across book</button>
      </div>
    </div>
    {error && <p role="alert" className="quality-clinic-error">{error}</p>}
    {grammarBusy && <p role="status">{grammarProgress}</p>}
    {grammar && <section className="quality-clinic-report" aria-live="polite">
      <div className="quality-clinic-reporttop">
        <strong>Offline English grammar: {grammar.total} findings across {grammar.chapters} chapters</strong>
        <span>{grammar.incomplete ? 'Display capped at 700 issues; complete count shown.' : 'All detected findings displayed.'}</span>
      </div>
      <p>{grammar.message}</p>
      {!grammar.findings.length && <p>No issues flagged by Harper. A human copyedit is still recommended.</p>}
      {grammar.findings.map((finding, index)=><article className="quality-clinic-finding" key={finding.path+':'+finding.start+':'+index}>
        <div><strong>{finding.path}</strong><small>Line {finding.line} · {finding.start}–{finding.end}</small></div>
        <p>{finding.message}</p>
        <blockquote>{finding.excerpt}</blockquote>
        {!!finding.suggestions.length && <p>Suggestions: {finding.suggestions.join(' / ')}</p>}
        <button onClick={()=>onOpenSource(finding.path)}>Open manuscript chapter</button>
      </article>)}
    </section>}
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
    <p className="quality-clinic-caveat">Harper adds substantial offline English grammar and spellchecking beyond EmberWriter's deterministic craft rules. Neither algorithm replaces a human copyeditor; creative dialect, dialogue and character voice can be intentional.</p>
  </section>
}
