import './diff.css'

export type DiffRow = {
  kind: 'equal' | 'change' | 'delete' | 'insert'
  older_line: number | null
  newer_line: number | null
  older_text: string
  newer_text: string
}

type Props = {
  olderLabel?: string
  newerLabel?: string
  olderText?: string
  newerText?: string
  rows?: DiffRow[]
  compact?: boolean
}

function localRows(olderText: string, newerText: string): DiffRow[] {
  const older = olderText.split(/\r?\n/)
  const newer = newerText.split(/\r?\n/)
  const size = Math.max(older.length, newer.length)
  const rows: DiffRow[] = []
  for (let index = 0; index < size; index += 1) {
    const oldValue = older[index]
    const newValue = newer[index]
    const hasOld = oldValue !== undefined
    const hasNew = newValue !== undefined
    rows.push({
      kind: hasOld && hasNew ? (oldValue === newValue ? 'equal' : 'change') : (hasOld ? 'delete' : 'insert'),
      older_line: hasOld ? index + 1 : null,
      newer_line: hasNew ? index + 1 : null,
      older_text: oldValue ?? '',
      newer_text: newValue ?? '',
    })
  }
  return rows
}

export default function DiffViewer({
  olderLabel = 'Before',
  newerLabel = 'After',
  olderText = '',
  newerText = '',
  rows,
  compact = false,
}: Props) {
  const aligned = rows ?? localRows(olderText, newerText)
  const changed = aligned.filter((row) => row.kind !== 'equal').length

  return (
    <div className={`split-diff ${compact ? 'compact' : ''}`}>
      <div className="split-diff-head">
        <span>{olderLabel}</span>
        <small>{changed} changed line{changed === 1 ? '' : 's'}</small>
        <span>{newerLabel}</span>
      </div>
      <div className="split-diff-grid" role="table" aria-label={`${olderLabel} compared with ${newerLabel}`}>
        {aligned.map((row, index) => (
          <div className={`split-diff-row kind-${row.kind}`} role="row" key={`${index}-${row.older_line ?? 'x'}-${row.newer_line ?? 'x'}`}>
            <div className="diff-cell diff-old" role="cell">
              <span className="diff-line-number">{row.older_line ?? ''}</span>
              <pre>{row.older_text || ' '}</pre>
            </div>
            <div className="diff-cell diff-new" role="cell">
              <span className="diff-line-number">{row.newer_line ?? ''}</span>
              <pre>{row.newer_text || ' '}</pre>
            </div>
          </div>
        ))}
        {aligned.length === 0 && <div className="split-diff-empty">No textual differences.</div>}
      </div>
    </div>
  )
}
