import { useEffect, useMemo, useState } from 'react'

type Provider = {
  provider: 'ollama' | 'openai_compatible'
  base_url: string
  model: string
  api_key?: string
}

type EmbeddingConfig = Provider

type KnowledgeSource = {
  id: string
  category: 'grammar' | 'publishing'
  authority: string
  title: string
  url: string
  refresh_days: number
  last_checked_at: string | null
  last_success_at: string | null
  content_hash: string
  status: 'seeded' | 'current' | 'stale' | 'error' | 'never_checked'
  error: string
  chunks: number
}

type KnowledgeChunk = {
  id: string
  source_id: string
  category: 'grammar' | 'publishing'
  authority: string
  source_title: string
  source_url: string
  title: string
  body: string
  checked_at: string | null
  score: number
  semantic_score: number | null
}

type GrammarIssue = {
  quote: string
  rule_ids: string[]
  explanation: string
  suggestion: string
  confidence: number
  intentional_style_possible: boolean
}

type GrammarReview = {
  summary: string
  issues: GrammarIssue[]
  rules: KnowledgeChunk[]
}

type Props = {
  apiBase: string
  slug: string
  activePath: string
  disabled: boolean
}

const fallbackProvider: Provider = {
  provider: 'ollama',
  base_url: 'http://localhost:11434',
  model: '',
  api_key: '',
}

function currentProvider(): Provider {
  try {
    const raw = localStorage.getItem('emberwriter.provider')
    return raw ? { ...fallbackProvider, ...JSON.parse(raw) } : fallbackProvider
  } catch {
    return fallbackProvider
  }
}

function initialEmbedding(): EmbeddingConfig {
  try {
    const raw = localStorage.getItem('emberwriter.embedding')
    if (raw) return { ...fallbackProvider, ...JSON.parse(raw) }
  } catch {
    // Fall through to the current chat provider as a starting point.
  }
  const provider = currentProvider()
  return { ...provider, model: '' }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || `${response.status} ${response.statusText}`)
  }
  return response.json() as Promise<T>
}

function sourceStatus(source: KnowledgeSource) {
  const checked = source.last_checked_at ? new Date(source.last_checked_at).toLocaleDateString() : 'never'
  return `${source.status.replaceAll('_', ' ')} · checked ${checked} · ${source.chunks} chunks`
}

export default function KnowledgePanel({ apiBase, slug, activePath, disabled }: Props) {
  const [sources, setSources] = useState<KnowledgeSource[]>([])
  const [category, setCategory] = useState<'grammar' | 'publishing'>('publishing')
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<KnowledgeChunk[]>([])
  const [answer, setAnswer] = useState('')
  const [grammar, setGrammar] = useState<GrammarReview | null>(null)
  const [embedding, setEmbedding] = useState<EmbeddingConfig>(initialEmbedding)
  const [semantic, setSemantic] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const categorySources = useMemo(
    () => sources.filter((source) => source.category === category),
    [sources, category],
  )
  const staleCount = sources.filter((source) => source.status !== 'current' && source.status !== 'seeded').length

  async function refreshSources() {
    setSources(await request<KnowledgeSource[]>(`${apiBase}/knowledge/sources`))
  }

  useEffect(() => {
    void refreshSources().catch((cause) => setError((cause as Error).message))
  }, [apiBase])

  useEffect(() => {
    localStorage.setItem('emberwriter.embedding', JSON.stringify(embedding))
  }, [embedding])

  async function search() {
    if (!query.trim() || busy) return
    setBusy(true)
    setError('')
    setAnswer('')
    try {
      setResults(await request<KnowledgeChunk[]>(`${apiBase}/knowledge/search`, {
        method: 'POST',
        body: JSON.stringify({
          query: query.trim(),
          categories: [category],
          limit: 12,
          semantic: semantic && Boolean(embedding.model.trim()),
          embedding: semantic && embedding.model.trim() ? embedding : null,
        }),
      }))
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function ask() {
    const provider = currentProvider()
    if (!query.trim() || !provider.model || busy) return
    setBusy(true)
    setError('')
    try {
      const result = await request<{ answer: string; rules: KnowledgeChunk[] }>(`${apiBase}/knowledge/answer`, {
        method: 'POST',
        body: JSON.stringify({ question: query.trim(), category, provider }),
      })
      setAnswer(result.answer)
      setResults(result.rules)
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function refreshDue() {
    if (busy) return
    setBusy(true)
    setError('')
    try {
      const result = await request<{ checked: number; updated: number; unchanged: number; failed: number }>(
        `${apiBase}/knowledge/refresh`,
        { method: 'POST', body: JSON.stringify({ source_ids: [] }) },
      )
      await refreshSources()
      setAnswer(`Refresh checked ${result.checked} source(s): ${result.updated} updated, ${result.unchanged} unchanged, ${result.failed} failed.`)
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function buildVectorIndex() {
    if (!embedding.model.trim() || busy) return
    setBusy(true)
    setError('')
    try {
      const result = await request<{ model: string; chunks_indexed: number; dimensions: number }>(
        `${apiBase}/knowledge/embeddings/index`,
        {
          method: 'POST',
          body: JSON.stringify({ embedding, categories: [], force: false }),
        },
      )
      setSemantic(true)
      setAnswer(`Semantic index ready: ${result.chunks_indexed} new/changed chunks using ${result.model} (${result.dimensions} dimensions).`)
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function reviewGrammar() {
    const provider = currentProvider()
    if (!slug || !activePath || !provider.model || busy) return
    setBusy(true)
    setError('')
    setGrammar(null)
    try {
      const file = await request<{ content: string }>(
        `${apiBase}/projects/${slug}/file?path=${encodeURIComponent(activePath)}`,
      )
      const text = file.content.length > 50000 ? file.content.slice(0, 50000) : file.content
      const result = await request<GrammarReview>(`${apiBase}/knowledge/grammar/review`, {
        method: 'POST',
        body: JSON.stringify({
          text,
          provider,
          context: `Fiction manuscript document: ${activePath}. Preserve intentional character voice and stylistic fragments.`,
        }),
      })
      setGrammar(result)
      setCategory('grammar')
      setResults(result.rules)
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <details className="knowledge-panel">
      <summary>
        Grammar & Publishing Knowledge
        <small>{sources.length} trusted sources · {staleCount ? `${staleCount} need refresh` : 'current'}</small>
      </summary>
      <div className="knowledge-body">
        <div className="editorial-scope">
          <button type="button" className={category === 'grammar' ? 'active' : ''} onClick={() => setCategory('grammar')}>Grammar</button>
          <button type="button" className={category === 'publishing' ? 'active' : ''} onClick={() => setCategory('publishing')}>Publishing</button>
        </div>

        <label>Search trusted rules</label>
        <div className="knowledge-search-row">
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={category === 'grammar' ? 'comma splice, fragments, passive voice…' : 'KDP cover bleed, EPUB cover, print PDF…'} />
          <button type="button" onClick={() => void search()} disabled={busy || !query.trim()}>Search</button>
        </div>
        <div className="knowledge-actions">
          <button type="button" onClick={() => void ask()} disabled={busy || !query.trim() || !currentProvider().model}>Ask with citations</button>
          <button type="button" onClick={() => void refreshDue()} disabled={busy}>Refresh due sources</button>
          {activePath && <button type="button" onClick={() => void reviewGrammar()} disabled={busy || disabled || !currentProvider().model}>Review current document grammar</button>}
        </div>

        <details className="knowledge-vector-settings">
          <summary>Semantic/vector search</summary>
          <label>Embedding provider
            <select value={embedding.provider} onChange={(event) => setEmbedding({ ...embedding, provider: event.target.value as EmbeddingConfig['provider'] })}>
              <option value="ollama">Ollama</option>
              <option value="openai_compatible">OpenAI-compatible</option>
            </select>
          </label>
          <label>Embedding server<input value={embedding.base_url} onChange={(event) => setEmbedding({ ...embedding, base_url: event.target.value })} /></label>
          <label>Embedding model<input value={embedding.model} onChange={(event) => setEmbedding({ ...embedding, model: event.target.value })} placeholder="e.g. nomic-embed-text" /></label>
          {embedding.provider === 'openai_compatible' && <label>API key<input type="password" value={embedding.api_key || ''} onChange={(event) => setEmbedding({ ...embedding, api_key: event.target.value })} /></label>}
          <button type="button" onClick={() => void buildVectorIndex()} disabled={busy || !embedding.model.trim()}>Index changed knowledge chunks</button>
          <label className="knowledge-semantic-toggle"><input type="checkbox" checked={semantic} onChange={(event) => setSemantic(event.target.checked)} disabled={!embedding.model.trim()} /> Use semantic search when index is available</label>
        </details>

        {answer && <div className="knowledge-answer">{answer}</div>}

        {grammar && (
          <div className="grammar-review">
            <strong>Grammar review</strong>
            <p>{grammar.summary}</p>
            {grammar.issues.length === 0 && <small>No source-grounded grammar issues were returned.</small>}
            {grammar.issues.map((issue, index) => (
              <article key={`${issue.quote}-${index}`}>
                <blockquote>{issue.quote}</blockquote>
                <p>{issue.explanation}</p>
                <small><b>Suggestion:</b> {issue.suggestion}</small>
                <small><b>Rules:</b> {issue.rule_ids.join(', ')} · confidence {Math.round(issue.confidence * 100)}%{issue.intentional_style_possible ? ' · may be intentional fiction style' : ''}</small>
              </article>
            ))}
          </div>
        )}

        {results.length > 0 && (
          <div className="knowledge-results">
            {results.map((item) => (
              <article key={item.id}>
                <strong>{item.title}</strong>
                <small>{item.authority} · {item.source_title}{item.checked_at ? ` · checked ${new Date(item.checked_at).toLocaleDateString()}` : ''}</small>
                <p>{item.body}</p>
                <a href={item.source_url} target="_blank" rel="noreferrer">Open authority source</a>
              </article>
            ))}
          </div>
        )}

        <details className="knowledge-sources">
          <summary>{categorySources.length} {category} sources</summary>
          {categorySources.map((source) => (
            <article key={source.id} className={source.status === 'error' ? 'source-error' : ''}>
              <strong>{source.authority}</strong>
              <span>{source.title}</span>
              <small>{sourceStatus(source)}</small>
              {source.error && <small className="panel-error">{source.error}</small>}
              <a href={source.url} target="_blank" rel="noreferrer">Source</a>
            </article>
          ))}
        </details>
        {error && <small className="panel-error">{error}</small>}
      </div>
    </details>
  )
}
