import { useEffect, useState } from 'react'

export type StyleFidelity = {
  schema_version: number
  metrics: Record<string, number>
  human_irregularities: string[]
  anti_ai_rules: string[]
  dialogue_rules: string[]
  interiority_rules: string[]
  author_notes: string
}

type Props = {
  value: StyleFidelity
  disabled?: boolean
  onSave: (value: StyleFidelity) => Promise<void>
}

function text(values: string[]) {
  return values.join('\n')
}

function lines(value: string) {
  return value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean)
}

export default function StyleFidelityEditor({ value, disabled = false, onSave }: Props) {
  const [irregularities, setIrregularities] = useState(text(value.human_irregularities))
  const [antiAi, setAntiAi] = useState(text(value.anti_ai_rules))
  const [dialogue, setDialogue] = useState(text(value.dialogue_rules))
  const [interiority, setInteriority] = useState(text(value.interiority_rules))
  const [notes, setNotes] = useState(value.author_notes)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    setIrregularities(text(value.human_irregularities))
    setAntiAi(text(value.anti_ai_rules))
    setDialogue(text(value.dialogue_rules))
    setInteriority(text(value.interiority_rules))
    setNotes(value.author_notes)
  }, [value])

  async function save() {
    setBusy(true)
    try {
      await onSave({
        ...value,
        human_irregularities: lines(irregularities),
        anti_ai_rules: lines(antiAi),
        dialogue_rules: lines(dialogue),
        interiority_rules: lines(interiority),
        author_notes: notes.trim(),
      })
    } finally {
      setBusy(false)
    }
  }

  const metrics = Object.entries(value.metrics || {})

  return <section className="style-fidelity-editor">
    <header><div><h3>Style Fidelity</h3><p>Measured tendencies plus author-owned rules. These feed Voice Lock and Craft Pass.</p></div></header>
    {metrics.length > 0 && <div className="style-metric-grid">
      {metrics.map(([key, metric]) => <div key={key}><small>{key.replaceAll('_', ' ')}</small><strong>{metric}</strong></div>)}
    </div>}
    <div className="style-rule-grid">
      <label>Human irregularities to preserve<textarea rows={5} value={irregularities} onChange={(event) => setIrregularities(event.target.value)} /></label>
      <label>AI tells to avoid<textarea rows={5} value={antiAi} onChange={(event) => setAntiAi(event.target.value)} /></label>
      <label>Dialogue rules<textarea rows={5} value={dialogue} onChange={(event) => setDialogue(event.target.value)} /></label>
      <label>Interiority rules<textarea rows={5} value={interiority} onChange={(event) => setInteriority(event.target.value)} /></label>
    </div>
    <label>Author overrides<textarea rows={4} value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Your rule wins over the learned profile." /></label>
    <button type="button" className="primary" disabled={disabled || busy} onClick={() => void save()}>{busy ? 'Saving…' : 'Save author style rules'}</button>
  </section>
}
