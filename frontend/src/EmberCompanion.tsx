import { useEffect, useRef, useState } from 'react'
import type { Workspace, WorkspaceProject } from './workspace-types'
import './ember-companion.css'

type Props = {
  workspace: Workspace
  project: WorkspaceProject | null
  onNavigate: (workspace: Workspace) => void
  onOpenSource: (path: string) => void
  onNewWriting: () => void
}
type Source = { path: string; excerpt: string; kind: string; status: string }
type Snapshot = {
  name: string; description: string; manuscript_files: number
  chapter_names: string[]; character_names: string[]; writing_formats: string[]
}
type Response = { answer?: string; project?: Snapshot; sources?: Source[]; writing_used?: boolean; read_only?: boolean }
type Message = { role: 'author' | 'ember'; text: string; sources?: Source[] }
const API = 'http://127.0.0.1:8000/api'

const guides: { label: string; workspace: Workspace; answer: string; triggers: string[] }[] = [
  { label: 'Continue my manuscript', workspace: 'write', answer: 'In Write, select your chapter from the Binder and keep writing. Focus mode hides distractions. Your draft is the source of truth.', triggers: ['continue', 'manuscript', 'write chapter', 'open chapter'] },
  { label: 'Outline a book', workspace: 'plan', answer: 'Open Plan → Book Studio. Start with a spark, review the chapter blueprint, and approve each draft in your own time.', triggers: ['outline', 'plot a book', 'plan a book', 'novel planning'] },
  { label: 'Choose a format', workspace: 'write', answer: 'Choose New writing in the top toolbar. Pick horror, science fiction, short story, essay, screenplay, stage play or another format. Preview it, then create a new page without touching existing writing.', triggers: ['template', 'horror', 'sci-fi', 'science fiction', 'screenplay', 'script', 'essay', 'genre', 'format', 'short story'] },
  { label: 'Use visual references', workspace: 'world', answer: 'Use Reference in the toolbar to paste a picture and describe what you want to borrow. In World → Visual Studio, an optional local vision model can study it. Images do not change story canon automatically.', triggers: ['photo', 'image', 'picture', 'visual', 'reference'] },
  { label: 'Get editing help', workspace: 'analyze', answer: 'In Analyze, review continuity and editorial findings. You decide whether to incorporate suggestions; Ember never overwrites approved prose.', triggers: ['analyze', 'critique', 'editing', 'edit my', 'proofread', 'continuity'] },
  { label: 'Create an audiobook', workspace: 'publish', answer: 'In Publish → Audiobook, cast narrator and character voices, set delivery emotion, generate local proof takes, and listen before approving a chapter.', triggers: ['audiobook', 'narrate', 'speech', 'voice', 'audio'] },
]
function helpfulAnswer(question: string, workspace: Workspace) {
  const q = question.toLowerCase()
  const match = guides.find(item => item.triggers.some(trigger => q.includes(trigger)))
  if (match) return { text: match.answer, destination: match.workspace }
  return { text: `I'm here to help with ${workspace} and your book. Ask how to use a tool, or allow me to search passages from this project for one question. Without a local model I can show relevant excerpts, but I won't invent answers.` }
}
function isAvailablePath(path: string) {
  return /^(manuscript|characters|world|summaries|scenes|style)\/[\w./-]+\.(md|txt)$/i.test(path) && !path.includes('..')
}

export default function EmberCompanion({ workspace, project, onNavigate, onOpenSource, onNewWriting }: Props) {
  const [open, setOpen] = useState(false)
  const [question, setQuestion] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const [model, setModel] = useState('')
  const [models, setModels] = useState<string[]>([])
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null)
  const [allowStory, setAllowStory] = useState(false)
  const [busy, setBusy] = useState(false)
  const [destination, setDestination] = useState<Workspace | null>(null)
  const endRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    setMessages([])
    setDestination(null)
    setSnapshot(null)
    setAllowStory(false)
  }, [project?.slug])
  useEffect(() => { endRef.current?.scrollIntoView({ block: 'nearest' }) }, [messages])
  useEffect(() => {
    if (!open || !project) return
    let cancelled = false
    const slug = encodeURIComponent(project.slug)
    void fetch(`${API}/projects/${slug}/companion/context`)
      .then(response => response.ok ? response.json() as Promise<Response> : null)
      .then(result => { if (!cancelled) setSnapshot(result?.project || null) })
      .catch(() => { if (!cancelled) setSnapshot(null) })
    void fetch(`${API}/models`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ provider: 'ollama', base_url: 'http://127.0.0.1:11434', model: '' }),
    }).then(response => response.ok ? response.json() : { models: [] })
      .then((value: { models?: string[] }) => {
        if (cancelled) return
        const installed = (value.models || []).filter(name => !/(?:-cloud|:cloud)(?:$|[-:])/i.test(name))
        setModels(installed)
        setModel(previous => installed.includes(previous) ? previous : '')
      }).catch(() => { if (!cancelled) setModels([]) })
    return () => { cancelled = true }
  }, [open, project?.slug])

  async function ask(text: string) {
    const current = text.trim()
    if (!current || busy) return
    const permitted = allowStory
    setQuestion(''); setAllowStory(false); setDestination(null)
    setMessages(previous => [...previous, { role: 'author', text: current }])
    const guide = helpfulAnswer(current, workspace)
    if (!project) {
      setMessages(previous => [...previous, { role: 'ember', text: guide.text }])
      setDestination(guide.destination || null)
      return
    }
    setBusy(true)
    try {
      const slug = encodeURIComponent(project.slug)
      let result: Response
      if (model) {
        const response = await fetch(`${API}/projects/${slug}/companion/ask`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question: current, workspace, model, include_writing: permitted }),
        })
        if (!response.ok) throw new Error('Local AI is unavailable')
        result = await response.json() as Response
      } else {
        const params = new URLSearchParams({ question: current, include_writing: String(permitted) })
        const response = await fetch(`${API}/projects/${slug}/companion/context?${params}`)
        if (!response.ok) throw new Error('Project context is unavailable')
        result = await response.json() as Response
      }
      const found = result.sources || []
      let answer = result.answer?.trim() || guide.text
      if (!model && permitted) {
        answer = found.length
          ? `I found ${found.length} potentially relevant passage${found.length === 1 ? '' : 's'} below. These are source excerpts rather than a synthesized answer. Choose a local AI model for a more conversational reading of them.`
          : 'I couldn’t find matching passages in the project files or extracted story notes. Try a character name or specific event. No writing was changed.'
      }
      setMessages(previous => [...previous, { role: 'ember', text: answer, sources: found }])
      setSnapshot(result.project || null)
      setDestination(guide.destination || null)
    } catch {
      setMessages(previous => [...previous, { role: 'ember', text: `I couldn't reach the local assistant. Here's the built-in guide: ${guide.text}` }])
      setDestination(guide.destination || null)
    } finally { setBusy(false) }
  }

  function navigate(next: Workspace) {
    onNavigate(next); setOpen(false)
  }

  return (
    <aside className="ember-companion" aria-label="Ember writing assistant">
      {open && <div className="ember-companion-panel" role="region" aria-label="Talk with Ember">
        <header>
          <div className="ember-companion-header">
            <span className="ember-mascot" aria-hidden="true"><span className="ember-mascot-eyes">••</span></span>
            <div><strong>Ember</strong><small>Your story sidekick · suggestions, not edits</small></div>
          </div>
          <button type="button" aria-label="Close Ember assistant" onClick={() => setOpen(false)}>✕</button>
        </header>
        <div className="ember-companion-body">
          {!messages.length && <>
            <p className="ember-companion-welcome">{project
              ? `Hi! I'm beside you in ${workspace}. I can help you find tools, explore writing ideas, or look up details in ${project.name} when you allow it.`
              : 'Hi! Open a writing project and I can learn its characters and plot with your permission. I can explain the tools right now.'}</p>
            {snapshot && <div className="ember-companion-project" aria-label="Project overview">
              <strong>On your desk: {snapshot.name}</strong>
              <span>{snapshot.manuscript_files} manuscript file{snapshot.manuscript_files === 1 ? '' : 's'}
                {snapshot.character_names.length > 0 && ` · ${snapshot.character_names.length} character files`}</span>
              {snapshot.writing_formats.length > 0 && <small>Writing formats: {snapshot.writing_formats.join(', ')}</small>}
              <small>Only file names are loaded until you choose to share passages.</small>
            </div>}
            <div className="ember-companion-suggestions">
              <button type="button" onClick={() => { onNewWriting(); setOpen(false) }}>＋ Start something new</button>
              {(workspace === 'publish' ? [guides[5], guides[2], guides[4]] :
                workspace === 'plan' ? [guides[1], guides[2], guides[4]] :
                [guides[0], guides[2], guides[4]]).map(item =>
                <button type="button" key={item.label} onClick={() => void ask(item.label)}>{item.label} →</button>)}
            </div>
          </>}
          {messages.map((item, index) => <div key={index} className={`ember-companion-message ${item.role}`}>
            <b>{item.role === 'author' ? 'You' : 'Ember'}</b>
            <p>{item.text}</p>
            {!!item.sources?.length && <div className="ember-companion-sources">
              <strong>From your project (not necessarily approved canon)</strong>
              {item.sources.map((source, ix) => <div key={ix} className="ember-companion-source">
                <span>[SOURCE {ix + 1}] {source.path || 'Story memory'}</span>
                <p>{source.excerpt}</p>
                {isAvailablePath(source.path) && <button type="button" onClick={() => {
                  onOpenSource(source.path); setOpen(false)
                }}>Open source →</button>}
              </div>)}
            </div>}
          </div>)}
          {busy && <p role="status">Ember is reading the local context…</p>}
          {destination && <button type="button" className="ember-companion-go" onClick={() => navigate(destination)}>
            Open {destination.charAt(0).toUpperCase() + destination.slice(1)} →
          </button>}
          <div ref={endRef} />
        </div>
        <form onSubmit={event => { event.preventDefault(); void ask(question) }}>
          <label htmlFor="ember-companion-question">What can I help you with?</label>
          <div className="ember-companion-compose">
            <input ref={inputRef} id="ember-companion-question" value={question}
              onChange={event => setQuestion(event.target.value)}
              placeholder="What does Mara know about the key?" maxLength={2000} disabled={busy} />
            <button type="submit" disabled={!question.trim() || busy}>Ask</button>
          </div>
          <label className="ember-companion-permission">
            <input type="checkbox" checked={allowStory} disabled={!project || busy}
              onChange={event => setAllowStory(event.target.checked)} />
            <span>Let Ember read matching passages from this book <em>(this question only)</em></span>
          </label>
          <label className="ember-companion-model">Answer mode
            <select value={model} onChange={event => setModel(event.target.value)} disabled={busy}>
              <option value="">Offline guide + source search</option>
              {models.map(name => <option key={name} value={name}>Local AI · {name}</option>)}
            </select>
          </label>
          <small>Read-only. Source excerpts go only to the local model you select. No changes to your story or canon.</small>
        </form>
      </div>}
      <button type="button" className="ember-companion-launcher" aria-expanded={open}
        aria-label={open ? 'Hide Ember companion' : 'Ask Ember about your book or the app'}
        onClick={() => { setOpen(previous => !previous); window.setTimeout(() => inputRef.current?.focus(), 80) }}>
        <span className="ember-mascot small" aria-hidden="true"><span className="ember-mascot-eyes">••</span></span>
        <span>{open ? 'Hide Ember' : 'Ask Ember'}</span>
      </button>
    </aside>
  )
}
