import { useEffect, useState } from 'react'
import './voiceprint-lab.css'

type Fingerprint = {
  words: number; sentence_words: number; sentence_variation: number
  paragraph_words: number; dialogue_share: number; em_dashes_per_1000: number
  questions_per_1000: number; exclamations_per_1000: number
}
type Signal = { metric: string; label: string; reference: number; chapter: number; message: string }
type Chapter = { path: string; title: string; status: string; metrics: Fingerprint; signals: Signal[] }
type VoiceReport = {
  configured: boolean; baseline: { selected: boolean; path: string }
  reference?: Fingerprint; chapters: Chapter[]; limitations: string
}
type Props = { apiBase: string; projectSlug: string; onOpenSource: (path: string) => void }

export default function VoiceprintLab({ apiBase, projectSlug, onOpenSource }: Props) {
  const endpoint = `${apiBase}/projects/${encodeURIComponent(projectSlug)}/voiceprint`
  const [options, setOptions] = useState<string[]>([])
  const [selection, setSelection] = useState('')
  const [report, setReport] = useState<VoiceReport | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  async function request<T>(suffix: string, method = 'GET', body?: unknown): Promise<T> {
    const result = await fetch(endpoint + suffix, {
      method, headers: { 'Content-Type': 'application/json' },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    })
    if (!result.ok) {
      const value = await result.json().catch(() => ({}))
      throw new Error(value.detail || `HTTP ${result.status}`)
    }
    return result.json() as Promise<T>
  }
  async function load() {
    const [files, ref] = await Promise.all([
      request<{ path: string }[]>('/options'),
      request<{ selected: boolean; path: string }>('/reference'),
    ])
    setOptions(files.map(x => x.path))
    setSelection(ref.path || files[0]?.path || '')
    setReport(await request<VoiceReport>('/report'))
  }
  useEffect(() => {
    let active = true
    setReport(null); setError(''); setMessage('')
    void load().catch(e => { if (active) setError(String(e)) })
    return () => { active = false }
  }, [endpoint])

  async function choose() {
    setBusy(true); setError(''); setMessage('')
    try {
      await request('/reference', 'PUT', { path: selection })
      setReport(await request<VoiceReport>('/report'))
      setMessage('Author reference selected. Your existing writing was not modified.')
    } catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }
  async function rescan() {
    setBusy(true); setError('')
    try { setReport(await request<VoiceReport>('/report')) }
    catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }
  const metrics: { name: keyof Fingerprint; label: string; suffix?: string }[] = [
    { name: 'sentence_words', label: 'Average sentence length', suffix: ' words' },
    { name: 'sentence_variation', label: 'Sentence-length variation' },
    { name: 'paragraph_words', label: 'Average paragraph length', suffix: ' words' },
    { name: 'dialogue_share', label: 'Dialogue proportion' },
    { name: 'em_dashes_per_1000', label: 'Em dashes / 1,000 words' },
    { name: 'questions_per_1000', label: 'Questions / 1,000 words' },
    { name: 'exclamations_per_1000', label: 'Exclamations / 1,000 words' },
  ]
  return <section className="voiceprint-lab" aria-labelledby="voiceprint-title">
    <header className="voiceprint-hero">
      <small>AUTHOR VOICE · THE RHYTHM OF YOUR STORY</small>
      <h2 id="voiceprint-title">Voiceprint Lab</h2>
      <p>Choose a passage that sounds like you. Compare the book's sentence rhythm, paragraph density and dialogue proportion to that reference—without asking an AI to flatten your distinctive voice.</p>
    </header>
    <div className="voiceprint-config">
      <label>Reference written in your preferred voice
        <select value={selection} onChange={e => setSelection(e.target.value)}>
          {!options.length && <option value="">No manuscript or style documents</option>}
          {options.map(path => <option key={path} value={path}>{path}</option>)}
        </select>
      </label>
      <button disabled={busy || !selection} onClick={() => void choose()}>Use this author reference</button>
      <button disabled={busy} onClick={() => void rescan()}>Refresh comparisons</button>
    </div>
    {error && <p role="alert" className="voiceprint-error">{error}</p>}
    {message && <p role="status" className="voiceprint-success">{message}</p>}
    {!report?.configured && <p className="voiceprint-hint">Choose at least 120 words of real authored prose. A short author-profile placeholder isn't enough to establish a meaningful rhythm reference.</p>}
    {report?.configured && <>
      <div className="voiceprint-reference">
        <strong>Selected author reference: {report.baseline.path}</strong>
        <p>Reference sample: {report.reference?.words} words. These comparisons are measurements, not grades.</p>
        <div className="voiceprint-metrics">
          {metrics.map(metric => <div key={metric.name}><small>{metric.label}</small><strong>{report.reference?.[metric.name]}{metric.suffix || ''}</strong></div>)}
        </div>
      </div>
      <div className="voiceprint-chapters">
        <h3>Chapter voice trajectories</h3>
        {report.chapters.map(ch => <article key={ch.path}>
          <header><div><h4>{ch.title}</h4><small>{ch.path} · {ch.status} · {ch.metrics.words} words</small></div>
            <span>{ch.signals.length ? `${ch.signals.length} differences worth reviewing` : 'No major rhythm differences flagged'}</span>
          </header>
          <div className="voiceprint-metrics">
            {metrics.map(metric => <div key={metric.name}><small>{metric.label}</small><strong>{ch.metrics[metric.name]}{metric.suffix || ''}</strong></div>)}
          </div>
          {ch.signals.map(signal => <p className="voiceprint-signal" key={signal.metric}>{signal.message} <small>Reference {signal.reference}; chapter {signal.chapter}.</small></p>)}
          {!ch.path.startsWith('book-studio:candidate:') && <button onClick={() => onOpenSource(ch.path)}>Read this chapter</button>}
        </article>)}
      </div>
    </>}
    {report && <p className="voiceprint-disclaimer">{report.limitations}</p>}
  </section>
}
