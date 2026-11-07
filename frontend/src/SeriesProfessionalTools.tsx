import { useEffect, useMemo, useState } from 'react'
import './series-professional-tools.css'

const API = 'http://127.0.0.1:8000/api'
export type ProMode = 'guardian' | 'consequences' | 'ember'
type Volume = { id: string; title: string; ordinal: number }
type Entity = { id: string; name: string; kind: string }
type Claim = { subject_id: string; predicate: string; object_text: string;
  scope: string; knower_id: string | null }
type Reference = { quote: string; source_path: string; title: string; volume: string; book: number;
  source_id: string; start: number; end: number }
type Finding = { claim_key: string; subject_name: string; predicate: string; proposed_value: string;
  existing_values: string[]; reason: string; suppressed_by_author: boolean;
  exception?: { reason: string; note: string } | null; evidence: Reference[] }
type Mention = { name: string; kind: string; locations: { start: number; end: number; excerpt: string }[] }
type Scan = { mentions: Mention[]; findings: Finding[]; verified_claims: {
  subject_name: string; predicate: string; status: string; references?: Reference[]
}[]; limitations: string; read_only: boolean }
type Impact = {
  proposal_id: string; summary: { direct_canon: number; related_canon: number;
    documents_to_inspect: number; characters_scanned: number; truncated: boolean }
  direct: { fact_id: string; book: number; predicate: string; value: string;
    reference: Reference; why: string }[]
  related: { fact_id: string; book: number; predicate: string; value: string;
    reference: Reference; why: string }[]
  mentions: { book: number; volume: string; source_path: string; excerpt: string;
    first_offset: number; hit_count: number; why: string }[]
  read_only: boolean; changes_applied: number
}
type EmberReply = { answer: string; sources: Reference[]; actions: {
  kind: string; label: string; panel: string; changes_story: boolean }[];
  uncertain: boolean; spoiler_limit: number; mode: string; conflicts: unknown[] }
type Props = { mode: ProMode; seriesId: string; volumes: Volume[];
  entities: Entity[]; onOpenPanel: (panel: ProMode) => void }
async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(API + path, init)
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(typeof payload.detail === 'string' ? payload.detail : 'Series service unavailable')
  return payload as T
}
const json = (value: object): RequestInit => ({
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(value),
})
const reasons = [
  ['unreliable_narrator', 'Unreliable narrator'],
  ['false_belief', 'Intentional false belief'],
  ['intentional_misdirection', 'Deliberate misdirection'],
  ['intentional_retcon', 'Planned retcon'],
  ['draft_in_progress', 'Scene in progress'],
  ['other', 'Other author decision'],
]
function SourceCard({ evidence }: {evidence: Reference}) {
  return <details className="series-pro-source">
    <summary>{evidence.volume} · Book {evidence.book} · {evidence.source_path}</summary>
    <blockquote>“{evidence.quote}”</blockquote>
    <small>Source: {evidence.title} · characters {evidence.start}–{evidence.end}</small>
  </details>
}

export default function SeriesProfessionalTools({mode, seriesId, volumes, entities, onOpenPanel}: Props) {
  const first = volumes[0]?.ordinal || 1
  const last = volumes[volumes.length - 1]?.ordinal || 1
  const [book, setBook] = useState(last)
  const [scope, setScope] = useState('world')
  const [knower, setKnower] = useState('')
  const [scene, setScene] = useState('')
  const [claimSubject, setClaimSubject] = useState('')
  const [claimPredicate, setClaimPredicate] = useState('located_in')
  const [claimValue, setClaimValue] = useState('')
  const [claims, setClaims] = useState<Claim[]>([])
  const [scan, setScan] = useState<Scan | null>(null)
  const [exceptionReason, setExceptionReason] = useState('unreliable_narrator')
  const [exceptionNote, setExceptionNote] = useState('')
  const [exceptionKey, setExceptionKey] = useState('')
  const [impactSubject, setImpactSubject] = useState('')
  const [impactPredicate, setImpactPredicate] = useState('located_in')
  const [impactValue, setImpactValue] = useState('')
  const [includePast, setIncludePast] = useState(false)
  const [impact, setImpact] = useState<Impact | null>(null)
  const [impactNote, setImpactNote] = useState('')
  const [reviews, setReviews] = useState<{id:string;predicate:string;proposed_value:string;
    author_note:string;status:string;effective_book:number}[]>([])
  const [question, setQuestion] = useState('')
  const [reply, setReply] = useState<EmberReply | null>(null)
  const [models, setModels] = useState<string[]>([])
  const [model, setModel] = useState('')
  const [consent, setConsent] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  useEffect(() => {
    setBook(last); setClaims([]); setScan(null); setImpact(null); setReply(null)
  }, [seriesId, last])
  useEffect(() => {
    if (mode !== 'consequences') return
    let alive = true
    void api<typeof reviews>(`/series/${seriesId}/consequences/reviews`)
      .then(data => { if (alive) setReviews(data) })
      .catch(() => { if (alive) setReviews([]) })
    return () => { alive = false }
  }, [seriesId, mode])
  useEffect(() => {
    if (mode !== 'ember') return
    let alive = true
    void fetch(`${API}/models`, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({provider:'ollama',base_url:'http://127.0.0.1:11434',model:''}),
    }).then(r => r.ok ? r.json() : {models: []})
      .then((data:{models?:string[]}) => {
        if (alive) setModels((data.models || []).filter(
          item => !/(?:^|[-:])(cloud|remote)(?:$|[-:])/i.test(item)))
      }).catch(() => { if (alive) setModels([]) })
    return () => { alive = false }
  }, [mode])

  async function run(job: () => Promise<void>, successMessage = '') {
    setBusy(true); setError(''); setSuccess('')
    try { await job(); setSuccess(successMessage) }
    catch (cause) { setError((cause as Error).message) }
    finally { setBusy(false) }
  }
  function addClaim() {
    if (!claimSubject || !claimPredicate.trim() || !claimValue.trim()
      || (scope === 'character_belief' && !knower)) return
    setClaims(previous => [...previous, {
      subject_id:claimSubject, predicate:claimPredicate.trim(),
      object_text:claimValue.trim(), scope,
      knower_id:scope === 'character_belief' ? knower : null,
    }])
    setClaimValue(''); setScan(null)
  }
  async function check() {
    await run(async () => {
      const result = await api<Scan>(`/series/${seriesId}/continuity/check`,
        json({scene, book, assertions:claims}))
      setScan(result)
    }, 'Continuity check completed without changing your manuscript.')
  }
  async function saveException(claimKey: string) {
    await run(async () => {
      await api(`/series/${seriesId}/continuity/exceptions`, json({
        claim_key:claimKey, reason:exceptionReason, note:exceptionNote.trim(),
      }))
      const refreshed = await api<Scan>(`/series/${seriesId}/continuity/check`,
        json({scene, book, assertions:claims}))
      setScan(refreshed); setExceptionKey(''); setExceptionNote('')
    }, 'Your intent is recorded; the scene and approved canon have not changed.')
  }
  async function clearIntentionalException(claimKey: string) {
    await run(async () => {
      await api(`/series/${seriesId}/continuity/exceptions/${claimKey}`, {method:'DELETE'})
      setScan(await api<Scan>(`/series/${seriesId}/continuity/check`,
        json({scene, book, assertions:claims})))
    }, 'Exception cleared. The possible conflict is visible again for your review.')
  }

  async function previewImpact() {
    await run(async () => {
      const result = await api<Impact>(`/series/${seriesId}/consequences/preview`,
        json({subject_id:impactSubject, predicate:impactPredicate,
          proposed_value:impactValue, effective_book:book,
          scope, include_past:includePast}))
      setImpact(result)
    }, 'Consequence map prepared from existing approved canon and manuscript references.')
  }
  async function saveImpactNote() {
    if (!impact) return
    await run(async () => {
      await api(`/series/${seriesId}/consequences/reviews`, json({
        subject_id:impactSubject, predicate:impactPredicate, proposed_value:impactValue,
        effective_book:book, scope, include_past:includePast,
        proposal_id:impact.proposal_id, note:impactNote.trim(),
      }))
      setImpactNote('')
      setReviews(await api<typeof reviews>(`/series/${seriesId}/consequences/reviews`))
    }, 'Review note saved. No story text or canon was rewritten.')
  }
  async function dismissReview(id: string) {
    await run(async () => {
      await api(`/series/${seriesId}/consequences/reviews/${id}/dismiss`, {method:'POST'})
      setReviews(await api<typeof reviews>(`/series/${seriesId}/consequences/reviews`))
    }, 'Review dismissed. Your source material is unchanged.')
  }
  async function askEmber() {
    const useLocal = Boolean(model)
    const allowed = consent
    setConsent(false)
    await run(async () => {
      const result = await api<EmberReply>(`/series/${seriesId}/ember/ask`, json({
        question, book, scope, knower_id:scope === 'character_belief' ? knower : null,
        model, use_local_model:useLocal, allow_sources:allowed,
      }))
      setReply(result)
    })
  }

  const chosenSubject = useMemo(
    () => entities.find(item => item.id === impactSubject),
    [entities, impactSubject],
  )
  const header = {
    guardian: {
      kicker:'04 · SOURCE-BASED CHECKING',
      title:'Continuity Guardian',
      lead:'Check a scene against what your world has already established. Ember surfaces evidence and never decides what you should change.',
    },
    consequences: {
      kicker:'05 · THE COST OF A STORY DECISION',
      title:'Consequence Map',
      lead:'Before changing a rule, relationship, or artifact, find which later scenes and canon facts deserve another look.',
    },
    ember: {
      kicker:'06 · YOUR SERIES LIBRARIAN',
      title:'Ask Ember',
      lead:'Ask about your fictional universe or how to use EmberWriter. Sources come only from approved facts available at your chosen book.',
    },
  }[mode]

  return <section className="series-pro">
    <header className="series-pro-header">
      <small>{header.kicker}</small><h2>{header.title}</h2>
      <p>{header.lead}</p>
    </header>
    {error && <p className="series-pro-error" role="alert">{error}</p>}
    {success && <p className="series-pro-success" role="status">{success}</p>}
    {!volumes.length && <p className="series-pro-empty">
      Add an authorized book to your Series Vault before researching its canon.
      <button type="button" onClick={() => onOpenPanel('guardian')}>Open writing tools</button>
    </p>}
    {volumes.length > 0 && <div className="series-pro-grid">
      <div className="series-pro-panel">
        <div className="series-pro-controls">
          <label>Story point
            <select value={book} onChange={event => {
              setBook(Number(event.target.value)); setScan(null); setImpact(null); setReply(null)
            }}>
              {volumes.map(item => <option key={item.id} value={item.ordinal}>
                Book {item.ordinal} · {item.title}</option>)}
            </select></label>
          {mode !== 'guardian' && <label>Knowledge perspective
            <select value={scope} onChange={event => { setScope(event.target.value); setReply(null); setImpact(null) }}>
              <option value="world">Objective world canon</option>
              <option value="character_belief">What a character believes</option>
              <option value="reader_reveal">What the reader knows</option>
            </select></label>}
          {mode === 'guardian' && <label>Scope of scene claims
            <select value={scope} onChange={event => setScope(event.target.value)}>
              <option value="world">World truth</option>
              <option value="character_belief">Character belief</option>
              <option value="reader_reveal">Reader reveal</option>
            </select></label>}
          {scope === 'character_belief' && <label>Whose belief?
            <select value={knower} onChange={event => setKnower(event.target.value)}>
              <option value="">Choose character</option>
              {entities.filter(item => item.kind === 'character').map(item =>
                <option key={item.id} value={item.id}>{item.name}</option>)}
            </select></label>}
        </div>
        {mode === 'guardian' && <>
          <label>Scene to check (not saved to the manuscript)
            <textarea rows={10} value={scene} maxLength={35000}
              placeholder="Paste the proposed scene here. This is only a scratchpad for continuity review."
              onChange={event => { setScene(event.target.value); setScan(null) }} /></label>
          <h3>Claims to compare</h3>
          <p className="series-pro-note">Mentioning a character isn't proof of a contradiction. Declare a concrete claim from the draft, such as “Moon Key · located_in · ocean,” to receive a source-backed result.</p>
          <div className="series-pro-fields">
            <label>Character, item, place or rule
              <select value={claimSubject} onChange={event => setClaimSubject(event.target.value)}>
                <option value="">Choose entity</option>
                {entities.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select></label>
            <label>Relationship <input value={claimPredicate} onChange={event => setClaimPredicate(event.target.value)} maxLength={60} placeholder="located_in" /></label>
            <label>Scene's asserted value <input value={claimValue} onChange={event => setClaimValue(event.target.value)} maxLength={500} placeholder="ocean" /></label>
            <button type="button" disabled={!claimSubject || !claimPredicate.trim() || !claimValue.trim() || busy ||
              (scope === 'character_belief' && !knower)} onClick={addClaim}>
              ＋ Add scene claim</button>
          </div>
          {claims.length > 0 && <div className="series-pro-claims">
            {claims.map((claim, index) => <div key={index}>
              <span>{entities.find(item => item.id === claim.subject_id)?.name || 'Unknown'} · {claim.predicate} · {claim.object_text}</span>
              <button type="button" onClick={() => { setClaims(previous => previous.filter((_, i) => i !== index)); setScan(null) }}
                aria-label={`Remove scene claim ${index + 1}`}>✕</button>
            </div>)}
          </div>}
          <button type="button" className="series-pro-primary" disabled={busy || !scene.trim()}
            onClick={() => void check()}>Check continuity without editing</button>
        </>}
        {mode === 'consequences' && <>
          <div className="series-pro-fields">
            <label>What is changing?
              <select value={impactSubject} onChange={event => { setImpactSubject(event.target.value); setImpact(null) }}>
                <option value="">Choose entity or rule</option>
                {entities.map(item => <option key={item.id} value={item.id}>{item.name} · {item.kind}</option>)}
              </select></label>
            <label>Relationship or rule <input value={impactPredicate} maxLength={60}
              onChange={event => { setImpactPredicate(event.target.value); setImpact(null) }} /></label>
            <label>Proposed new value <input value={impactValue} maxLength={500}
              placeholder="inside the lighthouse"
              onChange={event => { setImpactValue(event.target.value); setImpact(null) }} /></label>
            <label className="series-pro-checkbox"><input type="checkbox" checked={includePast}
              onChange={event => { setIncludePast(event.target.checked); setImpact(null) }} />
              <span>Also inspect earlier books (a retroactive change)</span></label>
            <button type="button" className="series-pro-primary"
              disabled={busy || !impactSubject || !impactPredicate.trim() || !impactValue.trim()}
              onClick={() => void previewImpact()}>
              Preview the consequences
            </button>
          </div>
          <p className="series-pro-note">A preview never edits the source books. A mention means “inspect this passage,” not “this scene is wrong.”</p>
          {impact && <div className="series-pro-review">
            <h3>Keep a decision for later</h3>
            <p className="series-pro-note">Record a pending author review note. This does not accept a retcon or rewrite canon.</p>
            <label>My creative decision and considerations
              <textarea rows={3} value={impactNote} maxLength={1500}
                onChange={event => setImpactNote(event.target.value)}
                placeholder="Before moving this artifact, revisit the tower scene in Book 2…" /></label>
            <button type="button" disabled={busy || !impactNote.trim()} onClick={() => void saveImpactNote()}>
              Save review note (no story changes)
            </button>
          </div>}
        </>}
        {mode === 'ember' && <>
          <label>Ask a question about your series or the application
            <textarea rows={5} value={question} maxLength={1500}
              onChange={event => setQuestion(event.target.value)}
              placeholder="Where was the Moon Key by the end of Book 2? Why does Mira believe the gate is safe?" /></label>
          <label>Answer mode
            <select value={model} onChange={event => setModel(event.target.value)}>
              <option value="">Grounded offline research + app guidance</option>
              {models.map(item => <option value={item} key={item}>Local Ollama · {item}</option>)}
            </select></label>
          {model && <label className="series-pro-checkbox">
            <input type="checkbox" checked={consent} onChange={event => setConsent(event.target.checked)} />
            <span>For this question only, share the selected book's approved evidence with my local model. Never use cloud inference.</span>
          </label>}
          <button type="button" className="series-pro-primary"
            disabled={busy || !question.trim() || (scope === 'character_belief' && !knower) ||
              (Boolean(model) && !consent)}
            onClick={() => void askEmber()}>Ask Ember</button>
          <p className="series-pro-note">No AI is needed for grounded research. Optional local AI can phrase the answer conversationally, but cannot make edits, promote canon, or create new facts.</p>
        </>}
      </div>
      <div className="series-pro-panel series-pro-results">
        {mode === 'guardian' && <>
          <h3>Evidence and review</h3>
          {!scan && <p className="series-pro-empty">The next check will show entity mentions, evidence-supported claims and possible conflicts. Until you declare specific claims, no continuity contradictions are assumed.</p>}
          {scan && <>
            <p className="series-pro-note">{scan.limitations}</p>
            <div className="series-pro-stats">
              <div><strong>{scan.findings.filter(x => !x.suppressed_by_author).length}</strong><span>Possible conflicts</span></div>
              <div><strong>{scan.verified_claims.filter(x => x.status === 'supported').length}</strong><span>Supported claims</span></div>
              <div><strong>{scan.mentions.length}</strong><span>Entity mentions</span></div>
            </div>
            {scan.findings.map(finding => <article className="series-pro-finding" key={finding.claim_key}>
              <strong>{finding.subject_name} · {finding.predicate.replaceAll('_',' ')}</strong>
              <p>Scene says: <b>{finding.proposed_value}</b>. Approved canon says: <b>{finding.existing_values.join(' / ')}</b>.</p>
              {finding.suppressed_by_author && <div className="series-pro-review">
                <p className="series-pro-ok">Author-marked intentional: {finding.exception?.reason} · {finding.exception?.note}</p>
                <button type="button" disabled={busy}
                  onClick={() => void clearIntentionalException(finding.claim_key)}>Reopen this finding</button>
              </div>}
              {finding.evidence.map((source, index) => <SourceCard key={index} evidence={source} />)}
              {!finding.suppressed_by_author && <>
                <button type="button" onClick={() => { setExceptionKey(finding.claim_key); setExceptionNote('') }}>
                  Mark as intentional / explain
                </button>
                {exceptionKey === finding.claim_key && <div className="series-pro-review">
                  <label>Why is the difference intentional?
                    <select value={exceptionReason} onChange={event => setExceptionReason(event.target.value)}>
                      {reasons.map(([value,label]) => <option value={value} key={value}>{label}</option>)}
                    </select></label>
                  <label>Author note <textarea value={exceptionNote} maxLength={1000} rows={3}
                    onChange={event => setExceptionNote(event.target.value)}
                    placeholder="The narrator is deliberately mistaken…" /></label>
                  <button disabled={busy || !exceptionNote.trim()}
                    onClick={() => void saveException(finding.claim_key)}>Save author exception</button>
                </div>}
              </>}
            </article>)}
            {scan.verified_claims.map((item, index) => <article key={index} className="series-pro-supported">
              <strong>{item.subject_name} · {item.predicate.replaceAll('_',' ')}</strong>
              <p>{item.status === 'supported' ? 'Supported by approved evidence' : 'No approved fact found for this claim; investigate manually'}</p>
              {item.references?.map((source, i) => <SourceCard key={i} evidence={source} />)}
            </article>)}
            {scan.mentions.length > 0 && <details className="series-pro-mentions">
              <summary>Show matching entity mentions (not verified facts)</summary>
              {scan.mentions.map(item => <div key={item.name}>
                <strong>{item.name} · {item.locations.length} shown</strong>
                <p>{item.locations[0]?.excerpt}</p>
              </div>)}
            </details>}
          </>}
        </>}
        {mode === 'consequences' && <>
          <h3>What might change?</h3>
          {!impact && <p className="series-pro-empty">Choose an established entity and describe one proposed change. A source-linked impact map will appear here.</p>}
          {impact && <>
            <p className="series-pro-note">{chosenSubject?.name} · {impactPredicate.replaceAll('_',' ')} · {impactValue}</p>
            <div className="series-pro-stats">
              <div><strong>{impact.summary.direct_canon}</strong><span>Direct canon facts</span></div>
              <div><strong>{impact.summary.related_canon}</strong><span>Related canon</span></div>
              <div><strong>{impact.summary.documents_to_inspect}</strong><span>Documents to inspect</span></div>
            </div>
            {impact.summary.truncated && <p className="series-pro-error">Results reached the safe scan limit. This is a partial impact map, not complete series coverage.</p>}
            {[...impact.direct, ...impact.related].map(item => <article key={item.fact_id} className="series-pro-finding">
              <strong>Book {item.book} · {item.predicate} · {item.value}</strong>
              <p>{item.why}</p><SourceCard evidence={item.reference} />
            </article>)}
            <details className="series-pro-mentions" open>
              <summary>{impact.mentions.length} manuscript document(s) mentioning the affected entity</summary>
              {impact.mentions.map((item,index) => <article key={index}>
                <strong>Book {item.book}: {item.volume}</strong>
                <small>{item.source_path} · {item.hit_count} appearance(s) found</small>
                <blockquote>“{item.excerpt}”</blockquote>
                <p className="series-pro-note">{item.why}</p>
              </article>)}
            </details>
          </>}
          <h3>Open author review notes</h3>
          {reviews.filter(row => row.status === 'open').map(row => <div className="series-pro-review" key={row.id}>
            <strong>Book {row.effective_book} · {row.predicate} → {row.proposed_value}</strong>
            <p>{row.author_note}</p>
            <button type="button" disabled={busy} onClick={() => void dismissReview(row.id)}>Dismiss review (no story edits)</button>
          </div>)}
          {!reviews.some(row => row.status === 'open') && <p className="series-pro-empty">No open change reviews.</p>}
        </>}
        {mode === 'ember' && <>
          <h3>Ember's research desk</h3>
          {!reply && <div className="series-pro-empty">
            <p>Try asking “What does Mira believe at the end of Book 1?” or “How do I use the Consequence Map?”</p>
            <p>Offline research is grounded in your approved Canon Graph, not an outside model's memories of other books.</p>
            <div className="series-pro-actions">
              <button type="button" onClick={() => onOpenPanel('guardian')}>Open Continuity Guardian</button>
              <button type="button" onClick={() => onOpenPanel('consequences')}>Open Consequence Map</button>
            </div>
          </div>}
          {reply && <div className="series-pro-answer">
            <p>{reply.answer}</p>
            <small>Book {reply.spoiler_limit} · {reply.mode.replaceAll('_',' ')} · Read-only</small>
            {reply.uncertain && <p className="series-pro-note">Not enough approved evidence to establish every requested detail. Try reviewing source passages or proposing a missing fact.</p>}
            {reply.sources.map((source,index) => <SourceCard key={index} evidence={source} />)}
            {reply.actions.map(item =>
              <button key={item.panel} type="button"
                onClick={() => {
                  if (item.panel === 'guardian' || item.panel === 'consequences' || item.panel === 'ember') {
                    onOpenPanel(item.panel as ProMode)
                  } else if (item.panel === 'recovery') {
                    window.dispatchEvent(new CustomEvent('emberwriter:open-recovery'))
                  } else {
                    window.dispatchEvent(new CustomEvent('emberwriter:series-panel',
                      {detail:{panel:item.panel}}))
                  }
                }}>{item.label} →</button>)}
          </div>}
        </>}
      </div>
    </div>}
  </section>
}
