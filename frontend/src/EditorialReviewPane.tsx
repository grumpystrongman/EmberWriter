import type { EditorialFinding, EditorialFixProposal } from './EditorialPanel'
import './editorial-review.css'

type DiffOp = {
  kind: 'equal' | 'delete' | 'insert'
  token: string
}

type Props = {
  finding: EditorialFinding
  proposal: EditorialFixProposal
  busy: boolean
  onApply: () => Promise<unknown> | unknown
  onClose: () => void
}

function tokenize(text: string): string[] {
  return text.match(/\S+\s*/g) || []
}

function tokenDiff(older: string, newer: string): DiffOp[] | null {
  const left = tokenize(older)
  const right = tokenize(newer)
  if (left.length * right.length > 350_000) return null

  const width = right.length + 1
  const table = new Uint16Array((left.length + 1) * width)
  for (let i = 1; i <= left.length; i += 1) {
    for (let j = 1; j <= right.length; j += 1) {
      const index = i * width + j
      table[index] = left[i - 1] === right[j - 1]
        ? table[(i - 1) * width + j - 1] + 1
        : Math.max(table[(i - 1) * width + j], table[i * width + j - 1])
    }
  }

  const reversed: DiffOp[] = []
  let i = left.length
  let j = right.length
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && left[i - 1] === right[j - 1]) {
      reversed.push({ kind: 'equal', token: left[i - 1] })
      i -= 1
      j -= 1
      continue
    }
    if (j > 0 && (i === 0 || table[i * width + j - 1] >= table[(i - 1) * width + j])) {
      reversed.push({ kind: 'insert', token: right[j - 1] })
      j -= 1
      continue
    }
    if (i > 0) {
      reversed.push({ kind: 'delete', token: left[i - 1] })
      i -= 1
    }
  }
  return reversed.reverse()
}

function DiffText({ text, ops, side }: { text: string; ops: DiffOp[] | null; side: 'older' | 'newer' }) {
  if (!ops) return <div className="editorial-review-prose">{text}</div>
  return (
    <div className="editorial-review-prose">
      {ops.map((op, index) => {
        if (side === 'older' && op.kind === 'insert') return null
        if (side === 'newer' && op.kind === 'delete') return null
        const changed = side === 'older' ? op.kind === 'delete' : op.kind === 'insert'
        return <span key={`${index}-${op.kind}`} className={changed ? `editorial-token-${op.kind}` : undefined}>{op.token}</span>
      })}
    </div>
  )
}

export default function EditorialReviewPane({ finding, proposal, busy, onApply, onClose }: Props) {
  const ops = tokenDiff(proposal.original, proposal.replacement)
  const changedWords = ops?.filter((op) => op.kind !== 'equal').length ?? null

  return (
    <section className="editorial-review-pane">
      <header className="editorial-review-header">
        <div>
          <small>{finding.report_name} · {finding.path.split('/').at(-1)}:{finding.line}</small>
          <h2>Revision Review</h2>
          <p>{finding.message}</p>
        </div>
        <button type="button" className="quiet" onClick={onClose} disabled={busy}>Back to manuscript</button>
      </header>

      <div className="editorial-review-meta">
        <span><b>Original</b> {proposal.original.trim().split(/\s+/).filter(Boolean).length} words</span>
        <span><b>Proposed</b> {proposal.replacement.trim().split(/\s+/).filter(Boolean).length} words</span>
        {changedWords !== null && <span><b>{changedWords}</b> changed tokens</span>}
      </div>

      <div className="editorial-review-columns">
        <article className="editorial-review-side original">
          <div className="editorial-review-side-heading">
            <strong>Current manuscript</strong>
            <small>Removed or replaced language is highlighted</small>
          </div>
          <DiffText text={proposal.original} ops={ops} side="older" />
        </article>
        <article className="editorial-review-side proposed">
          <div className="editorial-review-side-heading">
            <strong>AI proposal</strong>
            <small>New language is highlighted</small>
          </div>
          <DiffText text={proposal.replacement} ops={ops} side="newer" />
        </article>
      </div>

      <div className="editorial-review-rationale">
        <strong>Why Ember suggested this</strong>
        <p>{proposal.rationale}</p>
        <small>{finding.suggestion}</small>
      </div>

      <footer className="editorial-review-actions">
        <button type="button" onClick={onClose} disabled={busy}>Keep original</button>
        <button type="button" className="primary" onClick={() => void onApply()} disabled={busy || !proposal.changed}>
          {busy ? 'Applying verified edit…' : 'Apply & resolve'}
        </button>
      </footer>
    </section>
  )
}
