import { useState } from 'react'
import './manuscript-intelligence.css'

type Reference = { path: string; evidence: { line: number; excerpt: string }[] }
type PromiseRow = { id: string; title: string; intention: string; tracking_phrase: string; status: string; resolution_note: string; reference_count: number; references: Reference[] }
type Chapter = { index: number; path: string; title: string; status: string; words: number; average_sentence_words: number; dialogue_passages: number; mechanical_flags: number; tracked_subjects: { name: string; evidence: { line: number; excerpt: string }[] }[] }
type Insight = { chapters: Chapter[]; total_words: number; chapter_count: number; average_chapter_words: number; long_chapters: string[]; short_chapters: string[]; cross_chapter_echoes: { phrase: string; chapters: number; references: string[] }[]; promises: PromiseRow[]; limitations: string }
type Props = { apiBase: string; projectSlug: string; onOpenSource: (path: string) => void }

export default function ManuscriptIntelligence({ apiBase, projectSlug, onOpenSource }: Props) {
  const endpoint = `${apiBase}/projects/${encodeURIComponent(projectSlug)}/manuscript-intelligence`
  const [report, setReport] = useState<Insight | null>(null)
  const [names, setNames] = useState('')
  const [title, setTitle] = useState('')
  const [phrase, setPhrase] = useState('')
  const [intention, setIntention] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  async function request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
    const response = await fetch(endpoint + path, {
      method, headers: { 'Content-Type': 'application/json' },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    })
    if (!response.ok) {
      const details = await response.json().catch(() => ({}))
      throw new Error(details.detail || `HTTP ${response.status}`)
    }
    return response.json() as Promise<T>
  }
  async function scan() {
    setBusy(true); setError('')
    try {
      const subjects = names.split(',').map(s => s.trim()).filter(Boolean)
      const params = new URLSearchParams()
      subjects.forEach(subject => params.append('subjects', subject))
      setReport(await request<Insight>('/analyze?' + params.toString()))
      setNotice('Scanned the current manuscript locally. No prose was changed.')
    } catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }
  async function create(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault(); setBusy(true); setError('')
    try {
      await request('/promises', 'POST', { title, tracking_phrase: phrase, intention })
      setTitle(''); setPhrase(''); setIntention('')
      setNotice('Story promise added. The author controls whether it is fulfilled.')
      const params = new URLSearchParams()
      names.split(',').map(s => s.trim()).filter(Boolean).forEach(subject => params.append('subjects', subject))
      setReport(await request<Insight>('/analyze?' + params.toString()))
    } catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }
  async function status(promise: PromiseRow, next: string) {
    setBusy(true); setError('')
    try {
      const note = next === 'resolved' ? window.prompt('What scene or event resolves this promise? (Required for your own records)') : ''
      if (next === 'resolved' && (!note || !note.trim())) return
      await request('/promises/' + encodeURIComponent(promise.id), 'PATCH', { status: next, resolution_note: note || '' })
      setReport(prev => prev ? { ...prev, promises: prev.promises.map(p => p.id === promise.id ? { ...p, status: next, resolution_note: note || '' } : p) } : prev)
    } catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }

  return <section className="manuscript-intelligence" aria-labelledby="manuscript-intelligence-title">
    <header className="manuscript-intelligence-hero">
      <small>THE WHOLE BOOK · STORY SIGNALS</small>
      <h2 id="manuscript-intelligence-title">Manuscript Intelligence</h2>
      <p>Look beyond individual chapters. Follow character mentions, chapter length, repeated four-word sequences, and promises you choose to track. Every observation points back to the source.</p>
    </header>
    <div className="manuscript-intelligence-controls">
      <label>Names and phrases to follow across chapters (comma-separated, maximum 30)
        <input value={names} onChange={e => setNames(e.target.value)} placeholder="Mira, Captain Orr, the glass compass" />
      </label>
      <button disabled={busy} onClick={() => void scan()}>{busy ? 'Scanning locally…' : 'Analyze full manuscript'}</button>
    </div>
    {error && <p role="alert" className="manuscript-intelligence-error">{error}</p>}
    {notice && <p role="status" className="manuscript-intelligence-notice">{notice}</p>}
    {report && <>
      <div className="manuscript-intelligence-stats">
        <div><strong>{report.total_words.toLocaleString()}</strong><span>manuscript words</span></div>
        <div><strong>{report.chapter_count}</strong><span>chapter documents</span></div>
        <div><strong>{report.average_chapter_words.toLocaleString()}</strong><span>average chapter words</span></div>
        <div><strong>{report.promises.filter(p => p.status === 'open').length}</strong><span>open story promises</span></div>
      </div>
      <div className="manuscript-intelligence-section">
        <h3>Chapter pulse <small>DESCRIPTIVE, NOT A QUALITY SCORE</small></h3>
        <div className="manuscript-intelligence-chart">
          {report.chapters.map(ch => <button key={ch.path} title={`${ch.title}: ${ch.words} words`} onClick={() => { if (!ch.path.startsWith('book-studio:candidate:')) onOpenSource(ch.path) }}>
            <span className="manuscript-intelligence-bar" style={{ height: `${Math.max(6, Math.round(100 * ch.words / Math.max(1, ...report.chapters.map(c => c.words))))}%` }} />
            <span>{ch.index}</span>
          </button>)}
        </div>
        <div className="manuscript-intelligence-chapters">
          {report.chapters.map(ch => <article key={ch.path}>
            <div><strong>{ch.index}. {ch.title}</strong><small>{ch.status} · {ch.path}</small></div>
            <span>{ch.words.toLocaleString()} words · avg sentence {ch.average_sentence_words} · {ch.mechanical_flags} mechanical flags</span>
            {!!ch.tracked_subjects.length && <details className="manuscript-intelligence-mentions"><summary>Tracked mentions: {ch.tracked_subjects.map(s => s.name).join(', ')}</summary>{ch.tracked_subjects.map(subject => <div key={subject.name}><strong>{subject.name}</strong>{subject.evidence.map((item, i) => <blockquote key={i}>Line {item.line}: {item.excerpt}</blockquote>)}</div>)}</details>}
            {!ch.path.startsWith('book-studio:candidate:') && <button onClick={() => onOpenSource(ch.path)}>Open chapter</button>}
          </article>)}
        </div>
        {!!(report.long_chapters.length || report.short_chapters.length) && <p className="manuscript-intelligence-caveat">
          Relative chapter-length outliers: {report.long_chapters.length} longer, {report.short_chapters.length} shorter. A short chapter is not inherently a pacing defect.
        </p>}
      </div>
      <div className="manuscript-intelligence-section">
        <h3>Cross-chapter echoes</h3>
        {!report.cross_chapter_echoes.length ? <p>No repeated four-word sequences found across chapters under the current heuristic.</p> : report.cross_chapter_echoes.map(item =>
          <div className="manuscript-intelligence-echo" key={item.phrase}>
            <strong>“{item.phrase}”</strong><span>{item.chapters} chapters</span>
            <small>{item.references.join(' · ')}</small>
          </div>)}
      </div>
      <div className="manuscript-intelligence-section">
        <h3>Story Promise Ledger <small>AUTHOR-OWNED</small></h3>
        <p>Log a foreshadowing promise, mystery, unanswered question, or plot thread. Mention detection is literal; only you decide whether the narrative delivers on that promise.</p>
        <form className="manuscript-intelligence-form" onSubmit={e => void create(e)}>
          <label>Promise or question<input required maxLength={180} value={title} onChange={e => setTitle(e.target.value)} placeholder="Who built the lantern tower?" /></label>
          <label>Evidence phrase<input required minLength={3} maxLength={150} value={phrase} onChange={e => setPhrase(e.target.value)} placeholder="lantern tower" /></label>
          <label>Author intention<textarea maxLength={1000} value={intention} onChange={e => setIntention(e.target.value)} placeholder="Pay off the mystery in the final act." /></label>
          <button disabled={busy}>Track this story promise</button>
        </form>
        {report.promises.map(p => <article className="manuscript-intelligence-promise" key={p.id}>
          <div className="manuscript-intelligence-promise-head"><strong>{p.title}</strong><span>{p.status}</span></div>
          <p>Tracking “{p.tracking_phrase}” · {p.reference_count} chapter(s) with mentions</p>
          {p.intention && <p>Author intention: {p.intention}</p>}
          {p.resolution_note && <p>Resolution: {p.resolution_note}</p>}
          {p.references.map(ref => <div key={ref.path} className="manuscript-intelligence-reference">
            {ref.path.startsWith('book-studio:candidate:') ? <strong>{ref.path}</strong> : <button onClick={() => onOpenSource(ref.path)}>{ref.path}</button>}
            {ref.evidence.map((ev, index) => <blockquote key={index}>Line {ev.line}: {ev.excerpt}</blockquote>)}
          </div>)}
          <div className="manuscript-intelligence-decisions">
            {p.status !== 'resolved' && <button disabled={busy} onClick={() => void status(p, 'resolved')}>Mark fulfilled</button>}
            {p.status !== 'open' && <button disabled={busy} onClick={() => void status(p, 'open')}>Reopen</button>}
            {p.status !== 'abandoned' && <button disabled={busy} onClick={() => void status(p, 'abandoned')}>Abandon thread</button>}
          </div>
        </article>)}
      </div>
      <p className="manuscript-intelligence-caveat">{report.limitations}</p>
    </>}
  </section>
}
