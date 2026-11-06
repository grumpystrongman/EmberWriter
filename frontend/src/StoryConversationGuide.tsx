import { useEffect, useState } from 'react'
import './story-conversation-guide.css'

type Brief = { premise: string; voice: string; chapterCount: number; wordsPerChapter: number }
type Props = { projectSlug: string; onUseBrief: (brief: Brief) => void }

const questions = [
  { title: 'Who are we following?', prompt: "Tell me about the main character, what they long for, or what makes them interesting.", example: "A retired knight who wants to be left alone", key: 'hero' },
  { title: 'What makes this story matter?', prompt: 'What obstacle, danger, mystery, or relationship should drive the plot?', example: 'A missing child threatens the uneasy peace', key: 'conflict' },
  { title: 'What kind of ending?', prompt: 'Tell me the destination, emotional payoff, or one thing the ending must honor. You can leave the details open.', example: 'A hopeful, costly victory', key: 'ending' },
  { title: 'How should it sound?', prompt: 'Describe the mood, prose style, audience, or point of view. You can decide later.', example: 'Close third person, atmospheric and witty', key: 'voice' },
] as const
type AnswerKey = typeof questions[number]['key']
type State = { idea: string; answers: Record<AnswerKey, string>; step: number; length: 'short' | 'novel' | 'long' }
const blank: State = { idea: '', answers: { hero: '', conflict: '', ending: '', voice: '' }, step: 0, length: 'novel' }

export default function StoryConversationGuide({ projectSlug, onUseBrief }: Props) {
  const storageKey = `emberwriter.story-intake.${projectSlug}`
  const [state, setState] = useState<State>(() => {
    try { return { ...blank, ...(JSON.parse(localStorage.getItem(storageKey) || 'null') || {}) } }
    catch { return blank }
  })
  const [answer, setAnswer] = useState('')

  useEffect(() => {
    try { setState({ ...blank, ...(JSON.parse(localStorage.getItem(storageKey) || 'null') || {}) }) }
    catch { setState(blank) }
  }, [storageKey])
  useEffect(() => { localStorage.setItem(storageKey, JSON.stringify(state)) }, [state, storageKey])
  useEffect(() => { setAnswer(state.step > 0 && state.step <= questions.length ? state.answers[questions[state.step - 1].key] : '') }, [state.step])

  function next() {
    if (state.step === 0 && !state.idea.trim()) return
    if (state.step >= 1 && state.step <= questions.length) {
      const key = questions[state.step - 1].key
      setState(current => ({ ...current, answers: { ...current.answers, [key]: answer.trim() }, step: current.step + 1 }))
      setAnswer('')
      return
    }
    setState(current => ({ ...current, step: Math.min(current.step + 1, questions.length + 1) }))
  }

  function useBrief() {
    const { idea, answers, length } = state
    const premise = [
      idea.trim(),
      answers.hero && answers.hero !== 'Let Ember propose ideas' ? `Protagonist and motivation: ${answers.hero}` : '',
      answers.conflict && answers.conflict !== 'Let Ember propose ideas' ? `Central conflict and stakes: ${answers.conflict}` : '',
      answers.ending && answers.ending !== 'Let Ember propose ideas' ? `Ending direction: ${answers.ending}` : '',
    ].filter(Boolean).join('\n\n')
    const count = length === 'short' ? 12 : length === 'long' ? 36 : 24
    onUseBrief({ premise, voice: answers.voice === 'Let Ember propose ideas' ? '' : answers.voice, chapterCount: count, wordsPerChapter: 2500 })
  }
  const finished = state.step > questions.length
  const currentQuestion = !finished && state.step > 0 ? questions[state.step - 1] : null
  return <section className="story-conversation-guide" aria-label="Start your story from one idea">
    <div className="story-conversation-title">
      <div><strong>✦ Start with a spark</strong><p>You don't need a finished outline. Tell EmberWriter your idea, then answer only what matters to you. Nothing is saved as story canon until you approve the blueprint.</p></div>
      {state.step > 0 && <button type="button" onClick={() => { setState(blank); setAnswer('') }}>Start over</button>}
    </div>
    {state.step === 0 && <div className="story-conversation-turn">
      <label htmlFor="story-spark">What's the story you want to tell?</label>
      <textarea id="story-spark" value={state.idea} onChange={event => setState(current => ({ ...current, idea: event.target.value }))}
        maxLength={8000} placeholder="A lonely lighthouse keeper receives a letter from a ship that sank a century ago…" />
      <button type="button" disabled={!state.idea.trim()} onClick={next}>Continue the conversation →</button>
    </div>}
    {currentQuestion && <div className="story-conversation-turn">
      <small>Question {state.step} of {questions.length} · Your idea: {state.idea.slice(0, 180)}{state.idea.length > 180 ? '…' : ''}</small>
      <label htmlFor="story-turn">{currentQuestion.title}</label>
      <p>{currentQuestion.prompt}</p>
      <textarea id="story-turn" value={answer} onChange={event => setAnswer(event.target.value)} maxLength={3000} placeholder={currentQuestion.example} />
      <div className="story-conversation-actions">
        <button type="button" onClick={() => setState(current => ({ ...current, step: Math.max(0, current.step - 1) }))}>← Back</button>
        <button type="button" onClick={() => {
          const key = currentQuestion.key
          setState(current => ({ ...current, answers: { ...current.answers, [key]: 'Let Ember propose ideas' }, step: current.step + 1 }))
        }}>Surprise me later</button>
        <button type="button" onClick={next}>Keep going →</button>
      </div>
    </div>}
    {finished && <div className="story-conversation-turn">
      <h4>Here's the story we're shaping</h4>
      <p>{state.idea}</p>
      {questions.map(q => <p key={q.key}><b>{q.title}</b> {state.answers[q.key] || 'Still open'}</p>)}
      <label>Length of first draft
        <select value={state.length} onChange={event => setState(current => ({ ...current, length: event.target.value as State['length'] }))}>
          <option value="short">Shorter book · about 30,000 words</option>
          <option value="novel">Novel · about 60,000 words</option>
          <option value="long">Long novel · about 90,000 words</option>
        </select>
      </label>
      <div className="story-conversation-actions">
        <button type="button" onClick={() => setState(current => ({ ...current, step: questions.length }))}>← Refine answers</button>
        <button type="button" className="primary" onClick={useBrief}>Use this direction in my blueprint →</button>
      </div>
      <small>The next screen lets you revise everything and ask your local AI to suggest chapters. No writing or chapters are automatically approved.</small>
    </div>}
  </section>
}
