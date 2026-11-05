import { useEffect, useState } from 'react'

type ChapterStatus = {
  path: string
  title: string
  words: number
  assigned_dialogue: number
  missing_neural_references: string[]
  has_sapi_recording: boolean
  recording_proof_approved: boolean
  open_proof_notes: number
  neural_drama_ready_for_rehearsal: boolean
}
type Readiness = {
  title: string
  total_chapters: number
  total_words: number
  dialogue_selections: number
  neural_plan_ready_chapters: number
  chapters_missing_voice_references: number
  sapi_recorded_chapters: number
  proof_approved_recordings: number
  estimated_narrated_hours: number
  estimated_hours_note: string
  publication_ready: boolean
  publication_note: string
  next_steps: string[]
  chapters: ChapterStatus[]
}

export default function AuthorProductionDesk({ endpoint }: { endpoint: string }) {
  const [data, setData] = useState<Readiness | null>(null)
  const [error, setError] = useState('')
  const [refreshing, setRefreshing] = useState(false)
  const [showDetails, setShowDetails] = useState(false)
  const [referenceCost, setReferenceCost] = useState('')
  const [actualSpend, setActualSpend] = useState('')

  async function refresh() {
    setRefreshing(true); setError('')
    try {
      const response = await fetch(endpoint + '/production-readiness')
      if (!response.ok) throw new Error('Could not calculate production readiness')
      setData(await response.json() as Readiness)
    } catch (cause) { setError(String(cause)) }
    finally { setRefreshing(false) }
  }

  useEffect(() => {
    void refresh()
    // The author deliberately refreshes after editing casting, narration or approvals.
    // Do not poll or begin costly AI work automatically.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [endpoint])

  const compare = referenceCost === '' ? null : Number(referenceCost)
  const spend = actualSpend === '' ? null : Number(actualSpend)
  const difference = compare !== null && spend !== null && compare >= 0 && spend >= 0
    ? compare - spend : null

  return <section className="author-production-desk" aria-labelledby="author-desk-title">
    <div className="author-desk-heading">
      <div>
        <span className="author-desk-eyebrow">YOUR STORY. YOUR VOICES. YOUR DECISIONS.</span>
        <h3 id="author-desk-title">Author's Production Desk</h3>
        <p>Track your book from manuscript to performed audio. Creative decisions and final approvals belong to you; AI assists only when you ask.</p>
      </div>
      <button type="button" disabled={refreshing} onClick={() => void refresh()}>
        {refreshing ? 'Checking…' : 'Refresh production status'}
      </button>
    </div>
    {error && <p role="alert" className="audiobook-alert">{error}</p>}
    {data && <>
      <div className="author-desk-stats" aria-label="Novel and audiobook progress">
        <div><strong>{data.total_words.toLocaleString()}</strong><span>manuscript words</span></div>
        <div><strong>{data.total_chapters}</strong><span>Binder chapters</span></div>
        <div><strong>{data.dialogue_selections}</strong><span>author-assigned lines</span></div>
        <div><strong>{data.neural_plan_ready_chapters} / {data.total_chapters}</strong><span>voice plans complete</span></div>
        <div><strong>{data.proof_approved_recordings} / {data.total_chapters}</strong><span>recordings author-approved</span></div>
      </div>
      <p className="author-desk-disclaimer"><strong>Author approval is required.</strong> A complete voice plan does not mean an audiobook has been generated. Neural rehearsals are not final recordings. {data.publication_note}</p>
      <div className="author-desk-actions">
        <div>
          <h4>Next steps under your control</h4>
          <ul>{data.next_steps.map((step,index)=><li key={index}>{step}</li>)}</ul>
        </div>
        <div>
          <h4>Production time planning</h4>
          <strong>{data.estimated_narrated_hours.toFixed(1)} estimated audio hours</strong>
          <p>{data.estimated_hours_note}</p>
        </div>
      </div>
      <details className="author-desk-finances">
        <summary>Illustrative production-cost comparison (your numbers only)</summary>
        <p>Set a quote or budget for an alternative production and your actual project costs. This calculator makes no claims about market prices, savings, quality, distribution fees, licensing, equipment, electricity, or time.</p>
        <div className="audiobook-editor-row">
          <label>Alternative production quote (USD)<input type="number" min="0" step=".01" value={referenceCost} onChange={event=>setReferenceCost(event.target.value)} placeholder="Enter your quote" /></label>
          <label>Your total production costs (USD)<input type="number" min="0" step=".01" value={actualSpend} onChange={event=>setActualSpend(event.target.value)} placeholder="Include time and fees" /></label>
        </div>
        {difference !== null && <p role="status"><strong>Illustrative difference: {difference.toLocaleString('en-US',{style:'currency',currency:'USD'})}</strong> {difference >= 0 ? 'less than your comparison quote' : 'more than your comparison quote'}. These figures are not saved or sent to an AI service.</p>}
      </details>
      <button className="author-desk-detail-toggle" type="button" aria-expanded={showDetails} onClick={()=>setShowDetails(value=>!value)}>
        {showDetails ? 'Hide chapter-by-chapter status' : 'Review chapter-by-chapter status'}
      </button>
      {showDetails && <div className="author-desk-chapters">
        {data.chapters.map(ch=><div key={ch.path}>
          <strong>{ch.title}</strong>
          <span>{ch.words.toLocaleString()} words · {ch.assigned_dialogue} assigned dialogue lines</span>
          <span>{ch.recording_proof_approved ? 'Recording author-approved' : ch.has_sapi_recording ? 'Recording awaits author approval' : 'No approved recording yet'}</span>
          {ch.missing_neural_references.length > 0 && <span>Missing voice references: {ch.missing_neural_references.join(', ')}</span>}
          {ch.open_proof_notes > 0 && <span>{ch.open_proof_notes} unresolved listening notes</span>}
        </div>)}
      </div>}
    </>}
  </section>
}
