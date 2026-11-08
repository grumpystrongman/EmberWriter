import { useEffect, useRef, useState } from 'react'

type Chapter = { path: string; title: string; status: string; filename: string }
type Batch = { exists: boolean; status: string; id?: string; engine?: string; total: number; completed: number;
  chapters?: Chapter[]; message?: string; stale?: boolean; stale_reason?: string }
type ProofChapter = { path: string; title: string; approved: boolean; reason: string; filename: string }
type Proof = { exists: boolean; approved: number; total: number; ready: boolean;
  stale: boolean; chapters: ProofChapter[] }
type Segment = { index: number; speaker: string; text: string; status: string }
type Export = { filename: string; chapters: number; format: string }

export default function NeuralBookQueue({ endpoint, disabled }: { endpoint: string; disabled: boolean }) {
  const [batch, setBatch] = useState<Batch | null>(null)
  const [chosenEngine, setChosenEngine] = useState("kokoro-onnx")
  const [kittenAvailable, setKittenAvailable] = useState(false)
  const [proof, setProof] = useState<Proof | null>(null)
  const [working, setWorking] = useState(false)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [listened, setListened] = useState<Record<string, number>>({})
  const [durations, setDurations] = useState<Record<string, number>>({})
  const playhead = useRef<Record<string, number>>({})
  const [confirmed, setConfirmed] = useState<Record<string, boolean>>({})
  const [parts, setParts] = useState<Record<string, Segment[]>>({})
  const [archive, setArchive] = useState<Export | null>(null)
  const [m4b, setM4b] = useState<Export | null>(null)
  const stop = useRef(false)
  const live = useRef(true)

  async function request(path: string, method: string = 'GET', body?: unknown) {
    const response = await fetch(endpoint + path, {
      method, ...(body === undefined ? {} : { body: JSON.stringify(body),
        headers: { 'Content-Type': 'application/json' } }),
    })
    const data = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(data.detail || 'Neural production request failed')
    return data
  }

  async function refresh() {
    const [job, approvals, kitten] = await Promise.all([
      request('/kokoro/book'), request('/kokoro/book/proof'), request('/kitten/status'),
    ])
    if (live.current) { setBatch(job as Batch); setProof(approvals as Proof)
      setKittenAvailable(!!(kitten as {installed?: boolean}).installed) }
  }

  useEffect(() => {
    live.current = true
    void refresh().catch(e => { if (live.current) setError(String(e)) })
    return () => { live.current = false; stop.current = true }
    // Reload only when switching projects. No AI starts without author action.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [endpoint])

  async function action(work: () => Promise<void>) {
    setWorking(true); setError(''); setNotice(''); setArchive(null); setM4b(null)
    try { await work(); await refresh() }
    catch (e) { setError(String(e)) }
    finally { setWorking(false) }
  }

  async function start() {
    await action(async () => {
      setBatch(await request('/kokoro/book', 'POST', {engine: chosenEngine}) as Batch)
      setParts({}); setConfirmed({}); setListened({}); setDurations({}); playhead.current = {}
      setNotice('New draft prepared. The original manuscript was not changed.')
    })
  }

  async function produce() {
    stop.current = false; setRunning(true); setError(''); setArchive(null)
    try {
      let current = batch
      while (!stop.current && live.current && current?.status !== 'completed') {
        current = await request('/kokoro/book/next', 'POST') as Batch
        if (live.current) setBatch(current)
      }
      if (live.current) {
        await refresh()
        setNotice('Generation stopped at a safe segment boundary. Listen and proof each completed chapter.')
      }
    } catch (e) { if (live.current) setError(String(e)) }
    finally { if (live.current) setRunning(false) }
  }

  async function approve(path: string) {
    await action(async () => {
      await request('/kokoro/book/proof', 'PUT', {
        path, listened_seconds: listened[path] ?? 0,
        full_listen: true, source_aligned: true,
      })
      setNotice('You approved the exact chapter audio after confirming a full listen and source alignment.')
    })
  }

  async function revoke(path: string) {
    await action(async () => {
      await request('/kokoro/book/proof', 'DELETE', { path })
      setNotice('Chapter approval revoked.')
    })
  }

  async function showSegments(path: string) {
    await action(async () => {
      const result = await request('/kokoro/book/segments?path=' + encodeURIComponent(path)) as { segments: Segment[] }
      setParts(current => ({ ...current, [path]: result.segments }))
    })
  }

  async function retake(path: string, segment: number) {
    await action(async () => {
      await request('/kokoro/book/retake', 'POST', { path, segment })
      setConfirmed(current => ({ ...current, [path]: false }))
      setListened(current => ({ ...current, [path]: 0 })); playhead.current[path] = 0
      setNotice('One voice segment was re-recorded. The chapter was rebuilt and requires new proof approval.')
    })
  }

  async function exportBook() {
    await action(async () => {
      const result = await request('/kokoro/book/export', 'POST') as Export
      setArchive(result)
      setNotice('Approved WAV chapter archive prepared. Retailer mastering and eligibility still require review.')
    })
  }

  async function encodeM4b() {
    await action(async () => {
      const result = await request('/kokoro/book/export-m4b', 'POST') as Export
      setM4b(result)
      setNotice('Your chapter-marked M4B is ready for listening and distribution eligibility review.')
    })
  }

  const total = batch?.total || 0
  const completed = batch?.completed || 0
  return <section className="neural-book-queue" aria-labelledby="neural-book-title">
    <div className="neural-book-heading">
      <span>OFFLINE · AUTHOR-DIRECTED</span>
      <h3 id="neural-book-title">Neural Audiobook Production</h3>
      <p>Generate your Binder Draft chapter by chapter with saved voices. Every performance remains a draft until <strong>you listen, correct, and explicitly approve it</strong>.</p>
    </div>
    {error && <p role="alert" className="audiobook-alert">{error}</p>}
    {notice && <p role="status">{notice}</p>}
    <div className="neural-book-progress">
      <strong>{completed} / {total} voice segments recorded</strong>
      <progress aria-label="Neural audiobook production" max={Math.max(total, 1)} value={completed} />
      <p role="status">{batch?.message || 'No neural audiobook job started.'}</p>
      {batch?.stale && <p role="alert" className="audiobook-alert">Source or casting changed: {batch.stale_reason}. Start a fresh batch after reviewing your edits.</p>}
    </div>
    <div className="neural-book-progress">
      <label>Voice engine for the next audiobook draft
        <select value={chosenEngine} disabled={disabled || working || running || batch?.status === 'queued' || batch?.status === 'running'}
          onChange={event => setChosenEngine(event.target.value)}>
          <option value="kokoro-onnx">Lightweight CPU · Kokoro (acoustic emotion)</option>
          <option value="kitten-tts-2" disabled={!kittenAvailable}>Native CPU emotion · KittenTTS 2 (optional licensed model)</option>
        </select>
      </label>
      <p><small>KittenTTS 2 needs separately installed CPU weights and author-assigned Kitten voices in Audio Director. Its model license has commercial conditions. No model is downloaded automatically. Current batch: <strong>{batch?.engine || 'none'}</strong>.</small></p>
    </div>
    <div className="audiobook-job-buttons">
      <button disabled={disabled || working || running || batch?.status === 'queued' || batch?.status === 'running'}
        type="button" onClick={() => void start()}>Prepare new audiobook draft</button>
      <button disabled={disabled || working || running || !batch?.exists || batch.status === 'completed' || !!batch.stale}
        type="button" onClick={() => void produce()}>Generate remaining chapters</button>
      {running && <button type="button" onClick={() => { stop.current = true }}>Pause after this segment</button>}
      <button type="button" disabled={working || running} onClick={() => void action(async () => {})}>Refresh recording status</button>
    </div>
    <p>Audio renders locally in short restart-safe increments. A closed browser stops sending new requests. Neither manuscript text nor already approved prose is overwritten.</p>

    {proof?.exists && <div className="neural-book-progress">
      <strong>Author's listening desk: {proof.approved} / {proof.total} chapters approved</strong>
      <progress aria-label="Chapter listening approvals" max={Math.max(proof.total, 1)} value={proof.approved} />
      <p>Every approval is bound to its source text, narrator settings, and exact recorded audio bytes. Listen to the complete chapter while comparing it to the manuscript; correct missing words or pronunciation before approval.</p>
    </div>}

    {batch?.chapters?.length ? <details open={false}>
      <summary>Listen, retake, and approve draft chapters ({batch.chapters.filter(ch => !!ch.filename).length} recorded)</summary>
      <div className="neural-book-chapters">
        {batch.chapters.map(ch => {
          const checked = proof?.chapters.find(row => row.path === ch.path)
          const isApproved = !!checked?.approved
          return <div key={ch.path}>
            <strong>{ch.title}</strong>
            <small>{ch.status === 'rendered_unapproved' ? (isApproved ? 'Author approved' : 'Awaiting full listen') : 'Not yet rendered'} · {ch.path}</small>
            {!!ch.filename && !batch.stale && <>
              <audio controls preload="metadata" aria-label={'Draft neural chapter ' + ch.title}
                onLoadedMetadata={e => {
                  const duration = e.currentTarget.duration
                  if (Number.isFinite(duration)) setDurations(old => ({ ...old, [ch.path]: duration }))
                  playhead.current[ch.path] = e.currentTarget.currentTime
                }}
                onSeeked={e => { playhead.current[ch.path] = e.currentTarget.currentTime }}
                onTimeUpdate={e => {
                  const now = e.currentTarget.currentTime
                  const previous = playhead.current[ch.path] ?? now
                  const delta = now - previous
                  playhead.current[ch.path] = now
                  if (!e.currentTarget.paused && delta > 0 && delta < 1.5) {
                    setListened(old => ({ ...old, [ch.path]: (old[ch.path] || 0) + delta }))
                  }
                }}
                src={endpoint + '/kokoro/book/audio/' + encodeURIComponent(ch.filename)} />
              <a download href={endpoint + '/kokoro/book/audio/' + encodeURIComponent(ch.filename)}>Save draft WAV</a>
              {!isApproved && <>
                <small>Actual playback recorded: {Math.floor(listened[ch.path] || 0)} / {Math.ceil(durations[ch.path] || 0)} seconds. Seeking does not count as listening.</small>
                <label className="neural-book-approval">
                  <input type="checkbox" checked={!!confirmed[ch.path]}
                    onChange={e => setConfirmed(old => ({ ...old, [ch.path]: e.target.checked }))} />
                  I listened to the entire recording and checked it line by line against my manuscript.
                </label>
                <button type="button" disabled={disabled || running || working || !confirmed[ch.path] ||
                    !(durations[ch.path] > 0 && (listened[ch.path] || 0) >= durations[ch.path] * .95)}
                  onClick={() => void approve(ch.path)}>Approve this exact recording</button>
              </>}
              {isApproved && <button type="button" disabled={disabled || running || working}
                onClick={() => void revoke(ch.path)}>Revoke chapter approval</button>}
              <button type="button" disabled={disabled || running || working}
                onClick={() => void showSegments(ch.path)}>Review individual voice segments</button>
              {parts[ch.path]?.length ? <div className="neural-book-segments">
                {parts[ch.path].map(part => <div key={part.index}>
                  <span><strong>{part.speaker}</strong> · {part.text.slice(0, 240)}</span>
                  <button type="button" disabled={disabled || running || working} onClick={() => void retake(ch.path, part.index)}>Retake this segment</button>
                </div>)}
              </div> : null}
            </>}
          </div>
        })}
      </div>
    </details> : null}
    {proof?.ready && <div className="neural-book-progress">
      <strong>All current chapters have author proof approval.</strong>
      <p>Export a lossless, source-linked chapter archive for listening and external mastering. This is not an ACX-certified or professionally mastered retailer delivery package.</p>
      <button type="button" disabled={working || disabled || running} onClick={() => void exportBook()}>Package approved WAV audiobook</button>
      {archive && <a download href={endpoint + '/kokoro/book/export/' + encodeURIComponent(archive.filename)}>
        Download approved audiobook WAV chapters ({archive.chapters} chapters)
      </a>}
      <button type="button" disabled={working || disabled || running} onClick={() => void encodeM4b()}>Encode complete chapter-marked M4B audiobook</button>
      {m4b && <a download href={endpoint + '/kokoro/book/export-m4b/' + encodeURIComponent(m4b.filename)}>
        Download approved audiobook M4B ({m4b.chapters} chapters)
      </a>}
    </div>}
    <p><strong>Release safeguard:</strong> author proof listening is not automated speech recognition. Final mastering, audio rights and retailer acceptance are independent steps.</p>
  </section>
}
