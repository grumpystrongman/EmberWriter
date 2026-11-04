import { useEffect, useState } from 'react'
import './editorial-board.css'

type Finding = {
  id: string; origin: string; category: string; title: string; excerpt: string
  line: number; decision: string; suggestion: string | null; mechanical: boolean
}
type Chapter = {
  path: string; title: string; status: string; words: number; fingerprint: string
  outstanding: number; dismissed: number; fixable: number; findings: Finding[]
  reader_reviews: number; reader_findings_pending: number; story_arc_reviewed: boolean
}
type Report = {
  chapters: Chapter[]; chapter_count: number; total_words: number; outstanding: number
  dismissed: number; fixable: number; scan_id?: string; scanned_at?: string
  reader_coverage: number; story_arc_coverage: number
  style_truncated: boolean; limitations: string
}
type Preview = {
  path: string; source_hash: string; proposed_hash: string; original: string
  proposed: string; count: number
  changes: { line: number; rule: string; before: string; after: string }[]
}
type Scan = { id: string; at: string; outstanding: number; fixable: number }
type Props = { apiBase: string; projectSlug: string; onOpenSource: (path: string) => void; onNavigate: (tool: 'prose_editor' | 'style_bible' | 'story_arcs', path: string) => void }

export default function EditorialBoard({ apiBase, projectSlug, onOpenSource, onNavigate }: Props) {
  const endpoint = `${apiBase}/projects/${encodeURIComponent(projectSlug)}/editorial-board`
  const [report, setReport] = useState<Report | null>(null)
  const [history, setHistory] = useState<Scan[]>([])
  const [perspective, setPerspective] = useState('unspecified')
  const [tense, setTense] = useState('unspecified')
  const [expanded, setExpanded] = useState<string | null>(null)
  const [chapterQuery, setChapterQuery] = useState('')
  const [chapterFilter, setChapterFilter] = useState<'open' | 'all'>('open')
  const [chapterSort, setChapterSort] = useState<'order' | 'work'>('order')
  const [visibleCount, setVisibleCount] = useState(12)
  const [findingLimit, setFindingLimit] = useState<Record<string, number>>({})
  const [selected, setSelected] = useState<Record<string, boolean>>({})
  const [preview, setPreview] = useState<Preview | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  async function request<T>(suffix: string, method = 'GET', body?: unknown): Promise<T> {
    const response = await fetch(endpoint + suffix, {
      method, headers: { 'Content-Type': 'application/json' },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    })
    if (!response.ok) {
      const detail = await response.json().catch(() => ({}))
      throw new Error(detail.detail || `HTTP ${response.status}`)
    }
    return response.json() as Promise<T>
  }
  const matchingChapters = (report?.chapters || [])
    .filter(ch => chapterFilter === 'all' || ch.outstanding > 0)
    .filter(ch => !chapterQuery.trim() || (ch.title + ' ' + ch.path).toLowerCase().includes(chapterQuery.trim().toLowerCase()))
    .sort((a, b) => chapterSort === 'work' ? b.outstanding - a.outstanding :
      (report?.chapters.indexOf(a) || 0) - (report?.chapters.indexOf(b) || 0))
  async function refreshHistory() { setHistory(await request<Scan[]>('/history')) }
  useEffect(() => {
    let active = true
    setReport(null); setHistory([]); setSelected({}); setPreview(null); setError(''); setMessage(''); setVisibleCount(12); setChapterQuery('')
    void request<Scan[]>('/history').then(value => { if (active) setHistory(value) })
      .catch(e => { if (active) setError(String(e)) })
    return () => { active = false }
  }, [endpoint])
  async function scanBook() {
    setBusy(true); setError(''); setMessage(''); setPreview(null); setSelected({}); setVisibleCount(12); setExpanded(null); setFindingLimit({})
    try {
      setReport(await request<Report>('/scan', 'POST', { perspective, tense }))
      await refreshHistory()
      setMessage('Whole-book analysis completed and the scan baseline was saved locally.')
    } catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }
  function checked(chapter: Chapter) {
    return chapter.findings.filter(item => item.mechanical && item.decision === 'pending' && selected[item.id]).map(x => x.id)
  }
  async function makePreview(chapter: Chapter) {
    setBusy(true); setError(''); setMessage('')
    try {
      setPreview(await request<Preview>('/preview', 'POST', {
        path: chapter.path, ids: checked(chapter), source_hash: chapter.fingerprint,
        perspective, tense,
      }))
      setExpanded(chapter.path)
    } catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }
  async function approve(chapter: Chapter) {
    if (!preview || preview.path !== chapter.path) return
    setBusy(true); setError(''); setMessage('')
    try {
      await request('/apply', 'POST', {
        path: chapter.path, ids: checked(chapter), source_hash: preview.source_hash,
        proposed_hash: preview.proposed_hash, perspective, tense,
      })
      setPreview(null); setSelected({})
      setReport(await request<Report>('/scan', 'POST', { perspective, tense }))
      await refreshHistory()
      setMessage('Author-approved corrections applied to this chapter. The original version was archived.')
    } catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }
  return <section className="editorial-board" aria-labelledby="editorial-board-heading">
    <header className="editorial-board-hero">
      <small>FULL MANUSCRIPT · AUTHOR-CONTROLLED EDITORIAL TRIAGE</small>
      <h2 id="editorial-board-heading">Whole-Book Editorial Board</h2>
      <p>Find issues across the entire book, inspect evidence, and preview individual corrections before accepting changes.</p>
    </header>
    <div className="editorial-board-controls">
      <label>Expected point of view<select value={perspective} onChange={e => { setPerspective(e.target.value); setReport(null); setPreview(null) }}>
        <option value="unspecified">Don't check POV</option><option value="first">First-person</option><option value="third">Third-person</option>
      </select></label>
      <label>Expected tense<select value={tense} onChange={e => { setTense(e.target.value); setReport(null); setPreview(null) }}>
        <option value="unspecified">Don't check tense</option><option value="past">Past</option><option value="present">Present</option>
      </select></label>
      <button disabled={busy} onClick={() => void scanBook()}>{busy ? 'Reviewing…' : 'Scan entire book'}</button>
      {report && <a href={endpoint + '/report.md?perspective=' + encodeURIComponent(perspective) + '&tense=' + encodeURIComponent(tense)} download="emberwriter-editorial-report.md">Export report</a>}
    </div>
    {error && <p className="editorial-board-error" role="alert">{error}</p>}
    {message && <p className="editorial-board-success" role="status">{message}</p>}
    {!!history.length && <details className="editorial-board-history"><summary>Earlier editorial scans ({history.length})</summary>{history.slice(0, 5).map(item =>
      <span key={item.id}>{new Date(item.at).toLocaleString()}: {item.outstanding} pending · {item.fixable} mechanical fixes</span>)}</details>}
    {report && <>
      <div className="editorial-board-stats">
        <div><strong>{report.chapter_count}</strong><span>chapters reviewed</span></div>
        <div><strong>{report.total_words.toLocaleString()}</strong><span>manuscript words</span></div>
        <div><strong>{report.outstanding}</strong><span>open observations</span></div>
        <div><strong>{report.fixable}</strong><span>possible individual fixes</span></div>
      </div>
      <details className="editorial-board-coverage"><summary>Additional editorial metrics and reader coverage</summary>
        <p>{report.dismissed} author-approved exceptions · {report.reader_coverage}/{report.chapter_count} chapters with current reader evaluations · {report.story_arc_coverage}/{report.chapter_count} chapters with current story-arc analysis.</p>
      </details>
      {report.style_truncated && <p className="editorial-board-error">The Style Bible reached its scan limit. Narrow broad rules and scan again.</p>}
      <div className="editorial-board-filterbar">
        <label>Find chapter<input type="search" value={chapterQuery}
          placeholder="Chapter title or source path"
          onChange={e => { setChapterQuery(e.target.value); setVisibleCount(12); setExpanded(null) }} /></label>
        <label>Show<select value={chapterFilter} onChange={e => { setChapterFilter(e.target.value as 'open' | 'all'); setVisibleCount(12); setExpanded(null) }}>
          <option value="open">Needs review</option><option value="all">All chapters</option>
        </select></label>
        <label>Order<select value={chapterSort} onChange={e => { setChapterSort(e.target.value as 'order' | 'work'); setVisibleCount(12); setExpanded(null) }}>
          <option value="order">Manuscript order</option><option value="work">Most findings first</option>
        </select></label>
        <span role="status">Showing {Math.min(visibleCount, matchingChapters.length)} of {matchingChapters.length} chapters</span>
      </div>
      {!matchingChapters.length && <p className="editorial-board-empty">No chapters match these filters. Choose “All chapters” to review completed or clean sections.</p>}
      <div className="editorial-board-chapters">
        {matchingChapters.slice(0, visibleCount).map(ch => <article key={ch.path}>
          <header><div><h3>{ch.title}</h3><small>{ch.status} · {ch.words.toLocaleString()} words · {ch.path}</small></div>
            <span>{ch.outstanding} open · {ch.fixable} fixable · {ch.reader_reviews} reader verdict(s) · {ch.story_arc_reviewed ? 'arc assessed' : 'arc not assessed'}{ch.reader_findings_pending ? ` · ${ch.reader_findings_pending} reader findings pending` : ''}</span></header>
          <div className="editorial-board-actions">
            <button onClick={() => { setExpanded(expanded === ch.path ? null : ch.path); setPreview(null) }}>{expanded === ch.path ? 'Hide observations' : 'Review chapter findings'}</button>
            {!ch.path.startsWith('book-studio:candidate:') && <button onClick={() => onOpenSource(ch.path)}>Open in editor</button>}
            <button onClick={() => onNavigate('prose_editor', ch.path)}>Prose Editor</button>
            <button onClick={() => onNavigate('style_bible', ch.path)}>Style Bible</button>
            <button onClick={() => onNavigate('story_arcs', ch.path)}>Story Arc Investigator</button>
          </div>
          {expanded === ch.path && <div className="editorial-board-findings">
            {!ch.outstanding && <p>No pending observations. Author exceptions are available in the individual editors.</p>}
            {ch.findings.filter(item => item.decision === 'pending').slice(0, findingLimit[ch.path] || 12).map(item => <div key={item.id} className={item.decision === 'dismissed' ? 'editorial-board-dismissed' : ''}>
              <div><strong>{item.title}</strong><span>{item.origin} · line {item.line} · {item.decision}</span></div>
              <blockquote>{item.excerpt}</blockquote>
              {item.mechanical && item.decision === 'pending' && <label className="editorial-board-select">
                <input type="checkbox" checked={!!selected[item.id]}
                  onChange={e => { setSelected(prev => ({ ...prev, [item.id]: e.target.checked })); setPreview(null) }} />
                Include proposed correction: <strong>{item.suggestion || '(remove extra spacing)'}</strong>
              </label>}
              {!item.mechanical && <p>Review the observation in {item.origin === 'style' ? 'Style Bible' : 'Prose Editor'}; only exact mechanical corrections can be batch-applied.</p>}
            </div>)}
            {ch.outstanding > (findingLimit[ch.path] || 12) && <button disabled={busy}
              onClick={() => setFindingLimit(prev => ({ ...prev, [ch.path]: (prev[ch.path] || 12) + 12 }))}>
              Show more observations ({ch.outstanding - (findingLimit[ch.path] || 12)} remaining)
            </button>}
            {checked(ch).length > 0 && <button disabled={busy || checked(ch).length > 100} onClick={() => void makePreview(ch)}>
              Preview {checked(ch).length} corrections
            </button>}
            {checked(ch).length > 100 && <p>Choose no more than 100 corrections in one batch.</p>}
            {preview && preview.path === ch.path && <section className="editorial-board-preview">
              <h4>Compare before approval</h4>
              <p>{preview.count} corrections. Nothing has been changed yet.</p>
              <div className="editorial-board-comparison">
                <div><h5>Original text</h5><pre>{preview.original}</pre></div>
                <div><h5>Proposed text</h5><pre>{preview.proposed}</pre></div>
              </div>
              <button disabled={busy} onClick={() => void approve(ch)}>Approve all {preview.count} corrections to this chapter</button>
              <button disabled={busy} onClick={() => setPreview(null)}>Discard preview</button>
            </section>}
          </div>}
        </article>)}
      </div>
      {matchingChapters.length > visibleCount && <button className="editorial-board-load" disabled={busy}
        onClick={() => setVisibleCount(value => value + 12)}>Show 12 more chapters</button>}
      <p className="editorial-board-caveat">{report.limitations} For style-rule or POV/tense decisions, use the dedicated Style Bible or Prose Editor; the dashboard never guesses those decisions.</p>
    </>}
  </section>
}
