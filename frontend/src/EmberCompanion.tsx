import { useEffect, useRef, useState } from 'react'
import type { Workspace, WorkspaceProject } from './workspace-types'
import './ember-companion.css'

type Props = {
  workspace: Workspace
  project: WorkspaceProject | null
  onNavigate: (workspace: Workspace) => void
}

type Message = { role: 'author' | 'ember'; text: string }
const API = 'http://127.0.0.1:8000/api'
const suggestions: { label: string; workspace: Workspace; answer: string; triggers: string[] }[] = [
  { label: 'Continue my story', workspace: 'write', answer: 'Open Write, choose your chapter in the Binder, and continue your prose. Your approved manuscript stays yours.', triggers: ['write', 'continue', 'chapter', 'manuscript'] },
  { label: 'Plan a complete book', workspace: 'plan', answer: 'In Plan, open Write the book and the Production guide. Start with a premise, review the chapter blueprint, then direct draft candidates. Only you approve chapters.', triggers: ['book', 'novel', 'outline', 'plan', 'draft'] },
  { label: 'Add visual inspiration', workspace: 'world', answer: 'Open World and Visual Studio. Paste an image (Ctrl+V), drop it, or choose a file. Then describe what you want to borrow in Notes and link the reference to a character, setting, or scene. References are not canon until you approve them.', triggers: ['image', 'picture', 'photo', 'reference', 'visual', 'paste'] },
  { label: 'Review a draft', workspace: 'analyze', answer: 'Use Analyze for editorial checks, or Plan for Book Studio chapter approval and revisions. AI suggestions never replace approved prose without your decision.', triggers: ['review', 'edit', 'critique', 'quality', 'grammar'] },
  { label: 'Create an audiobook', workspace: 'publish', answer: 'In Publish, choose Audiobook. Pick an available local narrator, render a chapter, listen to the take, record corrections, and only then prepare book audio. Neural voices and full multi-actor production depend on the models installed.', triggers: ['audio', 'voice', 'narrate', 'speech', 'listen'] },
]
function offlineHelp(question: string, workspace: Workspace): { text: string; destination?: Workspace } {
  const q = question.toLowerCase()
  const match = suggestions.find(item => item.triggers.some(trigger => q.includes(trigger)))
  if (match) return { text: match.answer, destination: match.workspace }
  return {
    text: `I can help you find your way. You're in ${workspace}. Try asking about writing a chapter, planning a book, saving a picture, reviewing a draft, or making an audiobook. For a more conversational answer, choose an installed local Ollama model below.`,
  }
}

export default function EmberCompanion({ workspace, project, onNavigate }: Props) {
  const [open, setOpen] = useState(false)
  const [question, setQuestion] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const [model, setModel] = useState('')
  const [models, setModels] = useState<string[]>([])
  const [busy, setBusy] = useState(false)
  const [destination, setDestination] = useState<Workspace | null>(null)
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setMessages([])
    setDestination(null)
  }, [project?.slug])
  useEffect(() => { endRef.current?.scrollIntoView({ block: 'nearest' }) }, [messages])
  useEffect(() => {
    if (!open || !project) return
    let cancelled = false
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
    setQuestion('')
    setDestination(null)
    setMessages(prev => [...prev, { role: 'author', text: current }])
    const fallback = offlineHelp(current, workspace)
    if (!model || !project) {
      setMessages(prev => [...prev, { role: 'ember', text: fallback.text }])
      setDestination(fallback.destination || null)
      return
    }
    setBusy(true)
    try {
      const response = await fetch(`${API}/projects/${encodeURIComponent(project.slug)}/companion/ask`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: current, workspace, active_path: project.activePath || '', model }),
      })
      if (!response.ok) throw new Error('local model unavailable')
      const result = await response.json() as { answer: string }
      setMessages(prev => [...prev, { role: 'ember', text: result.answer || fallback.text }])
      setDestination(fallback.destination || null)
    } catch {
      setMessages(prev => [...prev, { role: 'ember', text: `The local AI isn't responding, so here's the offline guide: ${fallback.text}` }])
      setDestination(fallback.destination || null)
    } finally { setBusy(false) }
  }

  return (
    <aside className="ember-companion" aria-label="Ember writing assistant">
      {open && (
        <div className="ember-companion-panel" role="region" aria-label="Talk with Ember">
          <header>
            <div><strong>✦ Ember</strong><small>Your writing companion · suggestions only</small></div>
            <button type="button" aria-label="Close Ember assistant" onClick={() => setOpen(false)}>✕</button>
          </header>
          <div className="ember-companion-body">
            {!messages.length && (
              <>
                <p>{project ? `Working on ${project.name}? I can explain what to do next, find a tool, or answer questions about EmberWriter.` : 'Open a story to get project-aware help. You can still explore the writing tools here.'}</p>
                <div className="ember-companion-suggestions">
                  {suggestions.map(item => <button type="button" key={item.label} onClick={() => void ask(item.label)}>{item.label}</button>)}
                </div>
              </>
            )}
            {messages.map((item, index) => <p key={index} className={`ember-companion-message ${item.role}`}><b>{item.role === 'author' ? 'You' : 'Ember'}</b>{item.text}</p>)}
            {busy && <p role="status">Ember is checking the local model…</p>}
            {destination && <button type="button" className="ember-companion-go" onClick={() => {
              onNavigate(destination)
              setOpen(false)
            }}>Open {destination.charAt(0).toUpperCase() + destination.slice(1)} →</button>}
            <div ref={endRef} />
          </div>
          <form onSubmit={event => { event.preventDefault(); void ask(question) }}>
            <label htmlFor="ember-companion-question">Ask about writing or using EmberWriter</label>
            <div className="ember-companion-compose">
              <input id="ember-companion-question" value={question} onChange={event => setQuestion(event.target.value)}
                placeholder="How do I add a picture?" maxLength={2000} disabled={busy} />
              <button type="submit" disabled={!question.trim() || busy}>Ask</button>
            </div>
            <label className="ember-companion-model">Help mode
              <select value={model} onChange={event => setModel(event.target.value)} disabled={busy}>
                <option value="">Offline guide (no AI needed)</option>
                {models.map(name => <option key={name} value={name}>Local AI · {name}</option>)}
              </select>
            </label>
            <small>No changes are made through this helper. Local AI questions do not include your manuscript or images.</small>
          </form>
        </div>
      )}
      <button type="button" className="ember-companion-launcher" aria-expanded={open} aria-label={open ? 'Hide Ember companion' : 'Ask Ember companion'}
        onClick={() => setOpen(prev => !prev)}>✦ <span>{open ? 'Hide Ember' : 'Ask Ember'}</span></button>
    </aside>
  )
}
