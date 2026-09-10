export type MemoryFact = {
  id: string
  kind: string
  subject: string
  predicate: string
  object: string
  source_path: string
  confidence: number
  importance: number
  chapter_order: number
  metadata: Record<string, unknown>
  created_at: string
  updated_at: string
  score: number
}

export type MemoryStats = {
  facts: number
  documents: number
  by_kind: Record<string, number>
}

type Props = {
  facts: MemoryFact[]
  stats: MemoryStats
  query: string
  autoMemory: boolean
  busy: boolean
  canAnalyze: boolean
  onQueryChange: (value: string) => void
  onAutoMemoryChange: (value: boolean) => void
  onAnalyze: () => void
  onRefresh: () => void
  onOpenSource: (path: string) => void
}

function labelKind(kind: string) {
  return kind.replaceAll('_', ' ')
}

export default function MemoryPanel({
  facts,
  stats,
  query,
  autoMemory,
  busy,
  canAnalyze,
  onQueryChange,
  onAutoMemoryChange,
  onAnalyze,
  onRefresh,
  onOpenSource,
}: Props) {
  return (
    <details className="memory-panel" open>
      <summary>
        <span>Story memory</span>
        <small>{stats.facts} facts · {stats.documents} files</small>
      </summary>

      <div className="memory-toolbar">
        <button onClick={onAnalyze} disabled={busy || !canAnalyze}>
          {busy ? 'Analyzing…' : 'Analyze now'}
        </button>
        <button className="quiet" onClick={onRefresh} disabled={busy}>Refresh</button>
      </div>

      <label className="toggle-row">
        <input
          type="checkbox"
          checked={autoMemory}
          onChange={(event) => onAutoMemoryChange(event.target.checked)}
        />
        <span>
          <strong>Auto memory</strong>
          <small>Analyze changed manuscript files after you stop typing.</small>
        </span>
      </label>

      <input
        className="memory-search"
        value={query}
        onChange={(event) => onQueryChange(event.target.value)}
        placeholder="Search canon, people, secrets…"
      />

      {Object.keys(stats.by_kind).length > 0 && (
        <div className="memory-kinds">
          {Object.entries(stats.by_kind).map(([kind, count]) => (
            <span key={kind}>{labelKind(kind)} {count}</span>
          ))}
        </div>
      )}

      <div className="memory-list">
        {facts.length === 0 ? (
          <div className="memory-empty">
            No structured memory yet. Analyze a manuscript file to teach Ember what changed.
          </div>
        ) : facts.slice(0, 30).map((fact) => (
          <article className="memory-fact" key={fact.id}>
            <div className="memory-fact-head">
              <span className={`memory-kind kind-${fact.kind}`}>{labelKind(fact.kind)}</span>
              <span className="importance">{'◆'.repeat(Math.min(5, fact.importance))}</span>
            </div>
            <div className="memory-statement">
              <strong>{fact.subject}</strong> {fact.predicate} <strong>{fact.object}</strong>
            </div>
            <button className="memory-source" onClick={() => onOpenSource(fact.source_path)}>
              {fact.source_path} · {Math.round(fact.confidence * 100)}%
            </button>
          </article>
        ))}
      </div>
    </details>
  )
}
