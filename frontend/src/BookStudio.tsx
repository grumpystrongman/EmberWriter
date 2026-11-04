import { useEffect, useState } from 'react'
import './book-studio.css'

type Chapter = { number: number; title: string; brief: string; status: string; candidate_words: number; attempts: number; error?: string }
type BookPlan = { configured: boolean; premise?: string; voice?: string; target_words?: number; chapters: Chapter[]; running?: boolean }
type BookJob = { exists: boolean; status: string; active: boolean; current_chapter?: number | null; drafted?: number; approved?: number; total_chapters?: number; message?: string; model?: string }
type Props = { apiBase: string; projectSlug: string; onOpenSource: (path: string) => void }

export default function BookStudio({ apiBase, projectSlug, onOpenSource }: Props) {
  const endpoint = `${apiBase}/projects/${encodeURIComponent(projectSlug)}/book-studio`
  const jobEndpoint = `${apiBase}/projects/${encodeURIComponent(projectSlug)}/book-jobs`
  const [plan, setPlan] = useState<BookPlan | null>(null)
  const [premise, setPremise] = useState('')
  const [voice, setVoice] = useState('')
  const [chapterLines, setChapterLines] = useState('1. The Arrival | The crew encounters the impossible lantern signal.\n2. The Archive | A hidden star map reframes the mystery.\n3. The Crossing | The crew travels to the observatory and faces a choice.')
  const [wordTarget, setWordTarget] = useState(1500)
  const [chapterCount, setChapterCount] = useState(12)
  const [model, setModel] = useState('')
  const [installedModels, setInstalledModels] = useState<string[]>([])
  const [busy, setBusy] = useState(false)
  const [job, setJob] = useState<BookJob | null>(null)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [preview, setPreview] = useState<{ number: number; content: string } | null>(null)
  const [editing, setEditing] = useState<number | null>(null)
  const [editingDraft, setEditingDraft] = useState(false)
  const [draftText, setDraftText] = useState('')
  const [editTitle, setEditTitle] = useState('')
  const [editBrief, setEditBrief] = useState('')

  async function request<T>(suffix = '', method = 'GET', body?: unknown): Promise<T> {
    const response = await fetch(endpoint + suffix, {
      method, headers: { 'Content-Type': 'application/json' },
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
    })
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}))
      throw new Error(payload.detail || `HTTP ${response.status}`)
    }
    return response.json() as Promise<T>
  }
  async function refresh() {
    const next = await request<BookPlan>()
    setPlan(next)
    return next
  }
  async function jobRequest<T>(suffix = '', method = 'GET', body?: unknown): Promise<T> {
    const response = await fetch(jobEndpoint + suffix, {
      method, headers: { 'Content-Type': 'application/json' },
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
    })
    if (!response.ok) {
      const detail = await response.json().catch(() => ({}))
      throw new Error(detail.detail || `Job request failed: ${response.status}`)
    }
    return response.json() as Promise<T>
  }
  async function refreshJob() {
    const next = await jobRequest<BookJob>()
    setJob(next)
    return next
  }
  useEffect(() => {
    setPreview(null); setError(''); setMessage(''); setPlan(null); setJob(null)
    void refresh().catch(e => setError(String(e)))
    void refreshJob().catch(e => setError(String(e)))
    void discoverModels().catch(() => {})
    const timer = window.setInterval(() => {
      void Promise.all([refresh(), refreshJob()]).catch(() => {})
    }, 2200)
    return () => window.clearInterval(timer)
  }, [endpoint])

  async function discoverModels() {
    const result = await fetch(`${apiBase}/models`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ provider: 'ollama', base_url: 'http://127.0.0.1:11434', model: '' }),
    })
    if (!result.ok) throw new Error('Could not connect to local Ollama')
    const catalog = await result.json() as { models: string[] }
    const locallyHosted = catalog.models.filter(name => !/(?:-cloud|:cloud)(?:$|[-:])/i.test(name))
    setInstalledModels(locallyHosted)
    if (!model && locallyHosted.length) setModel(locallyHosted[0])
  }

  async function suggestChapters() {
    setBusy(true); setError(''); setMessage('')
    try {
      if (!model.trim()) throw new Error('Choose an installed Ollama model to propose an outline.')
      const result = await request<{ chapters: { title: string; brief: string }[] }>('/suggest-outline', 'POST', {
        premise, voice, chapter_count: chapterCount,
        provider: { provider: 'ollama', base_url: 'http://127.0.0.1:11434', model: model.trim() },
      })
      setChapterLines(result.chapters.map((c, i) => `${i + 1}. ${c.title} | ${c.brief}`).join('\n'))
      setMessage(`Local AI proposed ${result.chapters.length} chapters. Revise the outline to your taste before saving it.`)
    } catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }

  async function createPlan(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setBusy(true); setError(''); setMessage('')
    try {
      const chapters = chapterLines.split('\n').map(line => line.trim()).filter(Boolean).map(line => {
        const [rawTitle, ...details] = line.split('|')
        return { title: rawTitle.replace(/^\d+[.)]\s*/, '').trim(), brief: details.join('|').trim() }
      })
      if (chapters.some(c => !c.title || !c.brief)) throw new Error('Each chapter must have a title | brief.')
      await request('', 'PUT', { premise, voice, target_words: wordTarget, chapters })
      await refresh()
      setMessage('Book blueprint saved locally. Choose your local model and start drafting.')
    } catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }

  async function draftOne() {
    setError(''); setMessage(''); setBusy(true)
    try {
      if (!model.trim()) throw new Error('Enter the tag of an installed Ollama model first.')
      const result = await request<{ chapter: Chapter; preview: string }>('/draft-next', 'POST', {
        provider: { provider: 'ollama', base_url: 'http://127.0.0.1:11434', model: model.trim() },
      })
      setPreview({ number: result.chapter.number, content: result.preview })
      setDraftText(result.preview)
      setEditingDraft(false)
      setMessage(`Chapter ${result.chapter.number} is ready as a candidate. Your manuscript has not been replaced.`)
      await refresh()
    } catch (e) { setError(String(e)); throw e }
    finally { setBusy(false) }
  }

  async function changeJob(action: 'start' | 'pause' | 'resume') {
    setBusy(true); setError(''); setMessage('')
    try {
      if (action === 'start' && !model.trim()) throw new Error('Choose an installed local Ollama model.')
      const data = action === 'start' ? {
        provider: { provider: 'ollama', base_url: 'http://127.0.0.1:11434', model: model.trim() },
      } : undefined
      const next = await jobRequest<BookJob>(`/${action}`, 'POST', data)
      setJob(next)
      setMessage(next.message || 'Drafting job updated.')
      await refresh()
    } catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }

  async function openPreview(number: number) {
    setError('')
    try {
      const result = await request<{ content: string }>(`/candidates/${number}`)
      setPreview({ number, content: result.content })
      setDraftText(result.content)
      setEditingDraft(false)
    } catch (e) { setError(String(e)) }
  }

  async function saveDraftEdits(number: number) {
    setBusy(true); setError('')
    try {
      const updated = await request<{ content: string }>(`/candidates/${number}`, 'PUT', { content: draftText })
      setPreview({ number, content: updated.content })
      setDraftText(updated.content)
      setEditingDraft(false)
      setMessage('Your editorial changes are saved locally; the original candidate was archived. You can now approve or keep editing.')
      await refresh()
    } catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }

  async function decide(number: number, action: 'approve' | 'decline') {
    setBusy(true); setError('')
    try {
      await request(`/candidates/${number}/${action}`, 'POST')
      if (action === 'approve') {
        setMessage(`Chapter ${number} accepted into manuscript/book-studio/. You can open it in the editor.`)
      } else setMessage(`Chapter ${number} declined. It can be redrafted or rebriefed.`)
      await refresh()
      setPreview(null)
    } catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }

  async function saveBrief(e: React.FormEvent) {
    e.preventDefault()
    if (editing === null) return
    setBusy(true); setError('')
    try {
      await request(`/chapters/${editing}`, 'PUT', { title: editTitle, brief: editBrief })
      setEditing(null)
      await refresh()
      setMessage('Creative direction updated. The next draft will use the revised brief.')
    } catch (e) { setError(String(e)) }
    finally { setBusy(false) }
  }

  const total = plan?.chapters.length ?? 0
  const candidates = plan?.chapters.filter(c => c.status === 'candidate').length ?? 0
  const approved = plan?.chapters.filter(c => c.status === 'approved').length ?? 0
  const pending = plan?.chapters.filter(c => c.status === 'planned' || (c.status === 'failed' && c.attempts < 3)).length ?? 0
  return <section className="book-studio">
    <div className="book-studio-hero">
      <span>THE AUTHOR'S ENGINE ROOM Â· PRIVATE LOCAL DRAFTING</span>
      <h2>Book Studio</h2>
      <p>Give EmberWriter your world, characters, premise and chapter direction. It can draft a full novel, one chapter at a time, while you review, edit, reject or redirect the work. You're the author. EmberWriter handles the first-pass miles.</p>
      <div className="book-studio-stats"><strong>{total} chapters planned</strong><strong>{candidates} awaiting review</strong><strong>{approved} approved</strong><strong>{pending} remaining</strong></div>
    </div>
    {error && <p role="alert" className="book-studio-error">{error}</p>}
    {message && <p role="status" className="book-studio-message">{message}</p>}
    {!plan && !error && <p>Loading project book planâ€¦</p>}
    {plan && !plan.configured && <form className="book-studio-form" onSubmit={e => void createPlan(e)}>
      <h3>1. Direct your book</h3>
      <p>Book Studio also reads existing character, worldbuilding, timeline, relationship and style files from this project. Add them in the other writing workspaces whenever you like.</p>
      <label>Premise, stakes and ending direction <textarea required maxLength={8000} value={premise} onChange={e => setPremise(e.target.value)} placeholder="Describe the story's central conflict, themes, characters and destination." /></label>
      <label>Voice and craft direction <textarea maxLength={3000} value={voice} onChange={e => setVoice(e.target.value)} placeholder="POV, tense, rhythm, humor, dialogue style, audience, toneâ€¦" /></label>
      <div className="book-studio-outline-generator"><label>Suggested chapter count<input type="number" min={1} max={80} value={chapterCount} onChange={e => setChapterCount(Number(e.target.value))} /></label><label>Local model for outlining<input list="book-studio-local-models" value={model} onChange={e => setModel(e.target.value)} placeholder="Choose an installed Ollama model" /><datalist id="book-studio-local-models">{installedModels.map(name => <option key={name} value={name} />)}</datalist></label><button type="button" disabled={busy || !premise.trim() || !model.trim()} onClick={() => void suggestChapters()}>{busy ? 'Building possible outlineâ€¦' : 'Suggest an outline with local AI'}</button></div>
      <label>Chapter blueprint â€” one chapter per line as Title | required beats <textarea required className="book-studio-outline" value={chapterLines} onChange={e => setChapterLines(e.target.value)} /></label>
      <label>Target words per chapter <input type="number" min={300} max={5000} value={wordTarget} onChange={e => setWordTarget(Number(e.target.value))} /></label>
      <button type="submit" disabled={busy}>Save author blueprint</button>
    </form>}
    {plan?.configured && <>
      <div className="book-studio-controls">
        <div><h3>2. Draft your story</h3><p>Choose an installed Ollama model. No remote provider fallback. Candidates are held separately until approved.</p></div>
        <label>Local Ollama model tag <input list="book-studio-local-models" value={model} onChange={e => setModel(e.target.value)} placeholder="Choose an installed Ollama model" /><datalist id="book-studio-local-models">{installedModels.map(name => <option key={name} value={name} />)}</datalist></label>
        <div className="book-studio-run-controls">
          <button disabled={busy || !!job?.active || !pending} onClick={() => void draftOne().catch(() => {})}>Draft one chapter</button>
          <button disabled={busy || !!job?.active || !pending || job?.status === 'queued' || job?.status === 'running'} onClick={() => void changeJob('start')}>Run whole-book drafting locally</button>
          {(job?.status === 'queued' || job?.status === 'running') && <button disabled={busy} onClick={() => void changeJob('pause')}>Pause after chapter</button>}
          {(job?.status === 'paused' || job?.status === 'needs_attention' || job?.status === 'interrupted') && <button disabled={busy || !!job.active || !pending} onClick={() => void changeJob('resume')}>Resume saved job</button>}
        </div>
        {job?.exists && <div className="book-studio-job" role="status" aria-live="polite">
          <div className="book-studio-job-head"><strong>Local drafting: {job.status}</strong><span>{job.drafted ?? 0} of {job.total_chapters ?? 0} drafted</span></div>
          <progress value={job.drafted ?? 0} max={Math.max(1, job.total_chapters ?? 1)} aria-label="Book drafting progress" />
          <p>{job.message || 'Job is saved locally.'} {job.current_chapter ? `(Chapter ${job.current_chapter} in progress)` : ''}</p>
        </div>}
      </div>
      <div className="book-studio-chapters">
        <h3>3. Review, intervene, and approve</h3>
        {plan.chapters.map(ch => <article key={ch.number} className="book-studio-chapter">
          <div className="book-studio-chapter-head"><span className="book-studio-index">{String(ch.number).padStart(2, '0')}</span><div><h4>{ch.title}</h4><p>{ch.brief}</p></div><span className="book-studio-badge">{ch.status}</span></div>
          {ch.error && <small className="book-studio-error">{ch.error}</small>}
          <div className="book-studio-chapter-actions">
            {(ch.status === 'planned' || ch.status === 'failed') && <button disabled={busy || !!job?.active} onClick={() => { setEditing(ch.number); setEditTitle(ch.title); setEditBrief(ch.brief) }}>Change direction</button>}
            {(ch.status === 'candidate' || ch.status === 'approved') && <button onClick={() => void openPreview(ch.number)}>Read draft ({ch.candidate_words} words)</button>}
            {ch.status === 'approved' && <button onClick={() => onOpenSource(`manuscript/book-studio/chapter-${String(ch.number).padStart(3, '0')}.md`)}>Open in manuscript editor</button>}
          </div>
          {editing === ch.number && <form className="book-studio-edit" onSubmit={e => void saveBrief(e)}>
            <label>Chapter title<input required maxLength={200} value={editTitle} onChange={e => setEditTitle(e.target.value)} /></label>
            <label>New creative brief<textarea required maxLength={3000} value={editBrief} onChange={e => setEditBrief(e.target.value)} /></label>
            <div><button disabled={busy}>Save direction</button><button type="button" onClick={() => setEditing(null)}>Cancel</button></div>
          </form>}
          {preview?.number === ch.number && <div className="book-studio-preview">
            <header><strong>Chapter candidate â€” not yet in your manuscript</strong><button onClick={() => setPreview(null)}>Close preview</button></header>
            {editingDraft ? <textarea className="book-studio-draft-editor" value={draftText} onChange={e => setDraftText(e.target.value)} aria-label="Edit chapter candidate text" /> : <pre>{preview.content}</pre>}
            {ch.status === 'candidate' && <div className="book-studio-edit-actions">{editingDraft
              ? <><button disabled={busy} onClick={() => void saveDraftEdits(ch.number)}>Save my edits</button><button onClick={() => setEditingDraft(false)}>Cancel edits</button></>
              : <button disabled={busy || !!job?.active} onClick={() => setEditingDraft(true)}>Edit the draft before approval</button>}</div>}
            {ch.status === 'candidate' && <footer><button disabled={busy || !!job?.active || editingDraft} onClick={() => void decide(ch.number, 'approve')}>Approve and add to manuscript</button><button disabled={busy || !!job?.active} onClick={() => void decide(ch.number, 'decline')}>Decline and redraft</button></footer>}
          </div>}
        </article>)}
      </div>
    </>}
    <p className="book-studio-footnote">Whole-book drafting now runs in the local server, with one chapter checkpointed at a time. You can close the tab and return to review progress. Queued and running jobs resume after a service restart; a paused job stays paused. Nothing is approved automatically.</p>
  </section>
}
