import { useEffect, useState } from 'react'
import './style-bible.css'

type Rule = {
  id: string; category: 'preferred' | 'avoid' | 'watch'; phrase: string
  preferred: string; note: string; case_sensitive: boolean
}
type Finding = {
  id: string; rule_id: string; category: string; phrase: string; preferred: string
  note: string; path: string; title: string; line: number; excerpt: string
  matched: string; dismissed: boolean; dismissal_reason: string
}
type Audit = {
  rules: Rule[]; findings: Finding[]; truncated: boolean; chapters: number
  outstanding: number; dismissed: number; limits: string
}
type Props = { apiBase: string; projectSlug: string; onOpenSource: (path: string) => void }

export default function StyleBible({ apiBase, projectSlug, onOpenSource }: Props) {
  const endpoint = `${apiBase}/projects/${encodeURIComponent(projectSlug)}/style-bible`
  const [data, setData] = useState<Audit | null>(null)
  const [category, setCategory] = useState<Rule['category']>('preferred')
  const [phrase, setPhrase] = useState('')
  const [preferred, setPreferred] = useState('')
  const [note, setNote] = useState('')
  const [caseSensitive, setCaseSensitive] = useState(false)
  const [reasons, setReasons] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [showDismissed, setShowDismissed] = useState(false)

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
  async function refresh() { setData(await request<Audit>('/audit')) }
  useEffect(() => {
    let active = true
    setData(null); setError(''); setMessage('')
    void request<Audit>('/audit').then(next => { if (active) setData(next) })
      .catch(e => { if (active) setError(String(e)) })
    return () => { active = false }
  }, [endpoint])

  async function create(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault(); setBusy(true); setError(''); setMessage('')
    try {
      await request('/rules', 'POST', {
        category, phrase, preferred: category === 'preferred' ? preferred : '',
        note, case_sensitive: caseSensitive,
      })
      setPhrase(''); setPreferred(''); setNote('')
      await refresh()
      setMessage('Style rule added. The manuscript was not modified.')
    } catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }
  async function remove(rule: Rule) {
    if (!window.confirm(`Remove the rule for “${rule.phrase}”? Existing prose will remain unchanged.`)) return
    setBusy(true); setError('')
    try {
      await request(`/rules/${encodeURIComponent(rule.id)}`, 'DELETE')
      await refresh()
      setMessage('Style rule removed.')
    } catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }
  async function decision(finding: Finding, action: 'dismiss' | 'reopen') {
    setBusy(true); setError('')
    try {
      const reason = (reasons[finding.id] || '').trim()
      if (action === 'dismiss' && reason.length < 8) throw new Error('Describe why this usage is intentional (8 or more characters).')
      setData(await request<Audit>(`/findings/${encodeURIComponent(finding.id)}`, 'POST', {
        action, reason: action === 'dismiss' ? reason : '',
      }))
      setMessage(action === 'dismiss'
        ? 'Exception recorded for this precise occurrence in the current chapter.'
        : 'Finding reopened for review.')
    } catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }
  return <section className="style-bible" aria-labelledby="style-bible-title">
    <header className="style-bible-hero">
      <small>THE AUTHOR'S RULES · THE BOOK'S LANGUAGE</small>
      <h2 id="style-bible-title">Style Bible</h2>
      <p>Decide how names, invented words, important terms, and recurring phrases should appear. Audit every chapter against your choices without automatic changes to the manuscript.</p>
    </header>
    {error && <p className="style-bible-error" role="alert">{error}</p>}
    {message && <p className="style-bible-success" role="status">{message}</p>}
    <div className="style-bible-layout">
      <section className="style-bible-card">
        <h3>Add a writing rule</h3>
        <form onSubmit={e => void create(e)}>
          <label>Rule type<select value={category} onChange={e => setCategory(e.target.value as Rule['category'])}>
            <option value="preferred">Preferred spelling · flag alternate form</option>
            <option value="avoid">Avoid this word or phrase</option>
            <option value="watch">Watch for this expression</option>
          </select></label>
          <label>Text to find<input required minLength={2} maxLength={120} value={phrase} onChange={e => setPhrase(e.target.value)} placeholder="e.g. Aster Fall" /></label>
          {category === 'preferred' && <label>Preferred form<input required minLength={2} maxLength={120} value={preferred} onChange={e => setPreferred(e.target.value)} placeholder="e.g. Asterfall" /></label>}
          <label>Author note<textarea maxLength={500} value={note} onChange={e => setNote(e.target.value)} placeholder="The city uses the joined spelling in narration." /></label>
          <label className="style-bible-check"><input type="checkbox" checked={caseSensitive} onChange={e => setCaseSensitive(e.target.checked)} /> Match capital letters exactly</label>
          <button disabled={busy || !phrase.trim()}>Add to Style Bible</button>
        </form>
      </section>
      <section className="style-bible-card">
        <div className="style-bible-titlebar"><h3>Your rules</h3><span>{data?.rules.length ?? 0} / 250</span></div>
        {!data?.rules.length && <p>No style rules yet. Start with recurring character names or invented terms.</p>}
        {data?.rules.map(rule => <article key={rule.id} className="style-bible-rule">
          <div><strong>{rule.phrase}</strong><small>{rule.category.toUpperCase()}</small></div>
          {rule.preferred && <p>Preferred: <strong>{rule.preferred}</strong></p>}
          {rule.note && <p>{rule.note}</p>}
          <button disabled={busy} onClick={() => void remove(rule)}>Delete rule</button>
        </article>)}
      </section>
    </div>
    <section className="style-bible-card">
      <div className="style-bible-titlebar"><div><h3>Whole-book terminology audit</h3>
        <p>Every result includes the literal source text and line number.</p></div>
        <button disabled={busy} onClick={() => void refresh().catch(e => setError(String(e)))}>Rescan manuscript</button></div>
      {!!data && <div className="style-bible-stats">
        <span>{data.chapters} chapters scanned</span><span>{data.outstanding} pending findings</span>
        <span>{data.dismissed} acknowledged exceptions</span>
      </div>}
      {!!data?.truncated && <p className="style-bible-error">The safety limit of 2,000 findings was reached. Reduce broad rules and rescan.</p>}
      <label className="style-bible-check"><input type="checkbox" checked={showDismissed} onChange={e => setShowDismissed(e.target.checked)} /> Show dismissed occurrences</label>
      {!data?.findings.filter(f => showDismissed || !f.dismissed).length && <p>No flagged occurrences in the current manuscript.</p>}
      {data?.findings.filter(f => showDismissed || !f.dismissed).map(finding => <article className="style-bible-finding" key={finding.id}>
        <div className="style-bible-findinghead"><strong>{finding.category === 'preferred' ? `Use “${finding.preferred}” instead of “${finding.matched}”?` : `Review “${finding.matched}”`}</strong><span>{finding.dismissed ? 'AUTHOR-ACKNOWLEDGED' : finding.category.toUpperCase()}</span></div>
        <p>{finding.title} · line {finding.line}</p>
        <blockquote>{finding.excerpt}</blockquote>
        {finding.note && <p>Author's rule note: {finding.note}</p>}
        {!finding.path.startsWith('book-studio:candidate:') && <button onClick={() => onOpenSource(finding.path)}>Open chapter</button>}
        {finding.dismissed ? <div><p>Exception: {finding.dismissal_reason}</p><button disabled={busy} onClick={() => void decision(finding, 'reopen')}>Reopen finding</button></div>
          : <div className="style-bible-exception"><label>Intentionally allow this usage?
            <input maxLength={500} placeholder="Reason for this exception" value={reasons[finding.id] || ''} onChange={e => setReasons(prev => ({ ...prev, [finding.id]: e.target.value }))} />
          </label><button disabled={busy || (reasons[finding.id] || '').trim().length < 8} onClick={() => void decision(finding, 'dismiss')}>Keep this occurrence</button></div>}
      </article>)}
      {data && <p className="style-bible-caveat">{data.limits}</p>}
    </section>
  </section>
}
