import { useCallback, useEffect, useMemo, useState } from 'react'
import type { WorkspaceProject } from './workspace-types'
import SeriesProfessionalTools, { type ProMode } from './SeriesProfessionalTools'
import StoryObservatory from './StoryObservatory'
import './series-desk.css'

const API = 'http://127.0.0.1:8000/api'
type Source = { id: string; title: string; source_path: string; sequence: number; sha256: string; linked_project_changed?: boolean }
type Volume = { id: string; title: string; ordinal: number; kind: string; edition_status: string; project_slug: string | null; sources: Source[]; source_count: number }
type Series = { id: string; title: string; description: string; volume_count?: number; volumes?: Volume[] }
type Entity = { id: string; name: string; kind: string; aliases: string[]; description: string }
type Reference = { source_id: string; source_path: string; title: string; volume: string; book: number; quote: string; start: number; end: number }
type Fact = { id: string; subject_name: string; subject_id: string; predicate: string; object_text: string; object_name: string | null; scope: string; knower_name: string | null; status: string; start_book: number; end_book: number | null; quote: string; reference: Reference }
type AsOf = { answer?: string; facts: Fact[]; conflicts: { subject: string; predicate: string; assertion_ids: string[] }[]; sources?: Reference[]; evidence_only?: boolean }
type Excerpt = { found: boolean; excerpt: string; excerpt_start: number; excerpt_end: number; total_characters: number }
type Project = { slug: string; name: string }
type Suggestion = { subject_id: string; subject_name: string; predicate: string; object_text: string;
  scope: 'world' | 'character_belief' | 'reader_reveal'; knower_id: string | null;
  quote: string; quote_start: number; quote_end: number; start_book: number }

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(API + path, options)
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Could not complete that request')
  return data as T
}
const json = (body: object): RequestInit => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
const formats = [
  { value: 'novel', label: 'Novel' }, { value: 'novella', label: 'Novella' },
  { value: 'short_story', label: 'Short story' }, { value: 'companion', label: 'Companion' },
  { value: 'notes', label: 'Research notes' }, { value: 'other', label: 'Other' },
]
const statuses = [
  { value: 'published', label: 'Published edition' },
  { value: 'approved', label: 'Author-approved manuscript' },
  { value: 'draft', label: 'Working draft' }, { value: 'reference', label: 'Reference only' },
]

export default function SeriesDesk({ project }: { project: WorkspaceProject | null }) {
  const [seriesList, setSeriesList] = useState<Series[]>([])
  const [selectedId, setSelectedId] = useState('')
  const [series, setSeries] = useState<Series | null>(null)
  const [projects, setProjects] = useState<Project[]>([])
  const [view, setView] = useState<'observatory' | 'vault' | 'canon' | 'timeline' | ProMode>('observatory')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [newTitle, setNewTitle] = useState('')
  const [newDescription, setNewDescription] = useState('')
  const [deleteConfirmation, setDeleteConfirmation] = useState('')
  const [restoreFile, setRestoreFile] = useState<File | null>(null)
  const [restoreRights, setRestoreRights] = useState(false)
  const [volumeTitle, setVolumeTitle] = useState('')
  const [volumeOrdinal, setVolumeOrdinal] = useState(1)
  const [volumeKind, setVolumeKind] = useState('novel')
  const [editionStatus, setEditionStatus] = useState('draft')
  const [linkProject, setLinkProject] = useState('')
  const [documentFile, setDocumentFile] = useState<File | null>(null)
  const [volumeEdits, setVolumeEdits] = useState<Record<string, {title: string; ordinal: number; kind: string; edition_status: string}>>({})
  const [rightsConfirmed, setRightsConfirmed] = useState(false)
  const [addMode, setAddMode] = useState<'project' | 'document'>('project')
  const [entities, setEntities] = useState<Entity[]>([])
  const [facts, setFacts] = useState<Fact[]>([])
  const [entityName, setEntityName] = useState('')
  const [entityKind, setEntityKind] = useState('character')
  const [entityAliases, setEntityAliases] = useState('')
  const [sourceId, setSourceId] = useState('')
  const [sourceQuery, setSourceQuery] = useState('')
  const [excerpt, setExcerpt] = useState<Excerpt | null>(null)
  const [quote, setQuote] = useState('')
  const [subjectId, setSubjectId] = useState('')
  const [predicate, setPredicate] = useState('located_in')
  const [objectText, setObjectText] = useState('')
  const [objectEntityId, setObjectEntityId] = useState('')
  const [scope, setScope] = useState<'world' | 'character_belief' | 'reader_reveal'>('world')
  const [knowerId, setKnowerId] = useState('')
  const [startBook, setStartBook] = useState(1)
  const [startSequence, setStartSequence] = useState(0)
  const [endBook, setEndBook] = useState('')
  const [pointBook, setPointBook] = useState(1)
  const [pointSequence, setPointSequence] = useState(999999)
  const [question, setQuestion] = useState('Where is the artifact now?')
  const [querySubjectId, setQuerySubjectId] = useState('')
  const [answer, setAnswer] = useState<AsOf | null>(null)
  const [timeline, setTimeline] = useState<Fact[]>([])
  const [showPending, setShowPending] = useState(true)
  const [localModels, setLocalModels] = useState<string[]>([])
  const [suggestionModel, setSuggestionModel] = useState('')
  const [suggestions, setSuggestions] = useState<Suggestion[]>([])
  const [discardedSuggestions, setDiscardedSuggestions] = useState(0)

  const sources = useMemo(() => (series?.volumes || []).flatMap(volume =>
    volume.sources.map(source => ({ ...source, ordinal: volume.ordinal, volumeTitle: volume.title }))),
  [series])
  const selectedSource = sources.find(row => row.id === sourceId)
  const quotePosition = excerpt && quote ? excerpt.excerpt.indexOf(quote) : -1
  const quoteStart = excerpt && quotePosition >= 0 ? excerpt.excerpt_start + quotePosition : -1
  const quoteEnd = quoteStart >= 0 ? quoteStart + quote.length : -1

  const loadSeries = useCallback(async (preferred?: string) => {
    const listing = await request<Series[]>('/series')
    setSeriesList(listing)
    setSelectedId(previous => {
      const choice = preferred || previous
      return listing.some(item => item.id === choice) ? choice : (listing[0]?.id || '')
    })
  }, [])
  const loadSelected = useCallback(async (id: string) => {
    if (!id) { setSeries(null); setEntities([]); setFacts([]); setTimeline([]); return }
    const [detail, people, assertions, chronology] = await Promise.all([
      request<Series>('/series/' + id),
      request<Entity[]>(`/series/${id}/entities`),
      request<Fact[]>(`/series/${id}/assertions`),
      request<{ events: Fact[] }>(`/series/${id}/timeline`),
    ])
    setSeries(detail); setEntities(people); setFacts(assertions); setTimeline(chronology.events)
  }, [])

  useEffect(() => {
    void Promise.all([loadSeries(), request<Project[]>('/projects')])
      .then(([, available]) => setProjects(available))
      .catch(cause => setError(String(cause)))
  }, [loadSeries])
  useEffect(() => {
    void loadSelected(selectedId).catch(cause => setError(String(cause)))
    setAnswer(null)
  }, [selectedId, loadSelected])
  useEffect(() => {
    const onOpenPanel = (event: Event) => {
      const panel = (event as CustomEvent<{panel: string}>).detail?.panel
      if (['observatory','vault','canon','timeline','guardian','consequences','ember'].includes(panel)) {
        setView(panel as typeof view)
      }
    }
    window.addEventListener('emberwriter:series-panel', onOpenPanel)
    return () => window.removeEventListener('emberwriter:series-panel', onOpenPanel)
  }, [])

  useEffect(() => {
    if (!series?.volumes?.length) return
    setVolumeOrdinal(Math.max(...series.volumes.map(item => item.ordinal)) + 1)
    setStartBook(series.volumes[0].ordinal)
    setPointBook(series.volumes[series.volumes.length - 1].ordinal)
  }, [series?.id, series?.volumes?.length])
  useEffect(() => {
    if (sourceId && sources.some(item => item.id === sourceId)) return
    setSourceId(sources[0]?.id || '')
  }, [sourceId, sources])
  useEffect(() => {
    if (view !== 'canon' || !selectedId) return
    let alive = true
    void fetch(API + '/models', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({provider:'ollama', base_url:'http://127.0.0.1:11434', model:''}),
    }).then(r => r.ok ? r.json() : {models: []})
      .then((data: {models?: string[]}) => {
        if (!alive) return
        const available = (data.models || []).filter(name => !/(?:-cloud|:cloud)(?:$|[-:])/i.test(name))
        setLocalModels(available)
      }).catch(() => { if (alive) setLocalModels([]) })
    return () => { alive = false }
  }, [view, selectedId])

  useEffect(() => {
    setSuggestions([])
    // On series switch, React may briefly retain the prior book's source ID.
    // Never issue a cross-series fetch or expose a stale excerpt as evidence.
    if (!sourceId || !selectedId || series?.id !== selectedId
        || !sources.some(item => item.id === sourceId)) {
      setExcerpt(null)
      return
    }
    let active = true
    const query = new URLSearchParams({ query: sourceQuery, limit: '4000' })
    void request<Excerpt>(`/series/${selectedId}/sources/${sourceId}/excerpt?${query}`)
      .then(result => { if (active) setExcerpt(result) })
      .catch(cause => { if (active) { setExcerpt(null); setError(String(cause)) } })
    return () => { active = false }
  }, [sourceId, sourceQuery, selectedId, series?.id, sources])

  async function execute(operation: () => Promise<void>, success: string) {
    setBusy(true); setError(''); setNotice('')
    try { await operation(); setNotice(success) }
    catch (cause) { setError((cause as Error).message) }
    finally { setBusy(false) }
  }

  async function createSeries() {
    await execute(async () => {
      const created = await request<Series>('/series', json({
        title: newTitle, description: newDescription,
      }))
      setNewTitle(''); setNewDescription('')
      await loadSeries(created.id)
    }, 'Your private series has been created. Add books when you are ready.')
  }

  async function deleteSelectedSeries() {
    if (!series || deleteConfirmation !== series.title) return
    const oldTitle = series.title
    await execute(async () => {
      await request<{deleted: boolean}>(`/series/${series.id}/delete`,
        json({confirmation: deleteConfirmation}))
      setDeleteConfirmation('')
      setSeries(null); setSelectedId('')
      await loadSeries()
    }, `The Series Vault for "${oldTitle}" was deleted. Linked writing projects were left untouched.`)
  }

  async function restoreSeries() {
    if (!restoreFile) return
    await execute(async () => {
      const data = new FormData()
      data.append('file', restoreFile)
      data.append('rights_confirmed', String(restoreRights))
      const created = await request<Series>('/series/restore', {
        method: 'POST', body: data,
      })
      setRestoreFile(null); setRestoreRights(false)
      await loadSeries(created.id)
    }, 'Backup verified and restored as a separate series. Existing manuscripts were not changed.')
  }

  async function addVolume() {
    if (!series) return
    await execute(async () => {
      if (addMode === 'project') {
        await request<Series>(`/series/${series.id}/volumes/project`, json({
          project_slug: linkProject || project?.slug,
          ordinal: volumeOrdinal, title: volumeTitle || null,
          kind: volumeKind, edition_status: editionStatus,
          rights_confirmed: rightsConfirmed,
        }))
      } else {
        if (!documentFile) throw new Error('Choose a document to import.')
        const data = new FormData()
        data.append('file', documentFile)
        data.append('ordinal', String(volumeOrdinal))
        data.append('title', volumeTitle)
        data.append('kind', volumeKind)
        data.append('edition_status', editionStatus)
        data.append('rights_confirmed', String(rightsConfirmed))
        await request<Series>(`/series/${series.id}/volumes/import`, { method: 'POST', body: data })
      }
      setRightsConfirmed(false); setVolumeTitle(''); setDocumentFile(null)
      await loadSelected(series.id)
    }, 'Book added to the Series Vault. Its source snapshot is preserved and no canon was approved automatically.')
  }

  async function saveVolume(book: Volume) {
    if (!series) return
    await execute(async () => {
      const edit = volumeEdits[book.id] || {
        title: book.title, ordinal: book.ordinal, kind: book.kind,
        edition_status: book.edition_status,
      }
      await request<Series>(`/series/${series.id}/volumes/${book.id}`, {
        method: 'PUT', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(edit),
      })
      setVolumeEdits(previous => {
        const result = {...previous}
        delete result[book.id]
        return result
      })
      await loadSelected(series.id)
    }, 'Book metadata updated. Historical canon assertions were not rewritten.')
  }

  async function createEntity() {
    if (!series) return
    await execute(async () => {
      await request<Entity>(`/series/${series.id}/entities`, json({
        name: entityName, kind: entityKind,
        aliases: entityAliases.split(',').map(s => s.trim()).filter(Boolean),
      }))
      setEntityName(''); setEntityAliases('')
      await loadSelected(series.id)
    }, 'Entity saved in the series index. Its facts still require source evidence and approval.')
  }

  async function suggestFromSource() {
    if (!series || !selectedSource || !excerpt?.found || !suggestionModel) return
    await execute(async () => {
      const selectionStart = quoteStart >= 0 ? quoteStart : excerpt.excerpt_start
      const selectionEnd = quoteEnd >= 0 ? quoteEnd :
        Math.min(excerpt.excerpt_end, selectionStart + 1900)
      const response = await request<{suggestions: Suggestion[]; discarded: number}>(
        `/series/${series.id}/sources/${selectedSource.id}/suggest`,
        json({model: suggestionModel, start: selectionStart, end: selectionEnd}))
      setSuggestions(response.suggestions)
      setDiscardedSuggestions(response.discarded)
    }, 'Local AI suggestions are ready for inspection. No assertion was saved or approved.')
  }

  function useSuggestion(item: Suggestion) {
    setSubjectId(item.subject_id)
    setPredicate(item.predicate)
    setObjectText(item.object_text)
    setObjectEntityId('')
    setScope(item.scope)
    setKnowerId(item.knower_id || '')
    setStartBook(item.start_book)
    setStartSequence(0)
    setQuote(item.quote)
    setNotice('Review the filled form and exact citation, then explicitly save the proposal.')
  }

  async function proposeFact() {
    if (!series || quoteStart < 0 || quoteEnd < 0 || !sourceId) return
    await execute(async () => {
      await request<Fact>(`/series/${series.id}/assertions`, json({
        subject_id: subjectId, predicate,
        object_text: objectText, object_entity_id: objectEntityId || null,
        scope, knower_id: scope === 'character_belief' ? knowerId : null,
        start_book: startBook, start_sequence: startSequence,
        end_book: endBook ? Number(endBook) : null,
        source_id: sourceId, quote_start: quoteStart, quote_end: quoteEnd,
        quote, note: 'Author-created evidence proposal; not canon until reviewed.',
      }))
      setQuote(''); setObjectText(''); setObjectEntityId(''); setEndBook('')
      await loadSelected(series.id)
    }, 'Proposed fact saved. Review and approve it before it becomes canon.')
  }

  async function reviewFact(factId: string, decision: 'approved' | 'rejected') {
    if (!series) return
    await execute(async () => {
      await request<Fact>(`/series/${series.id}/assertions/${factId}/review`,
        json({ decision }))
      await loadSelected(series.id)
    }, decision === 'approved' ? 'You approved this fact as series canon.' : 'You rejected the proposed fact.')
  }

  async function ask() {
    if (!series) return
    await execute(async () => {
      const response = await request<AsOf>(`/series/${series.id}/ask`,
        json({ question, book: pointBook, sequence: pointSequence,
          scope, knower_id: scope === 'character_belief' ? knowerId : null,
          subject_id: querySubjectId || null }))
      setAnswer(response)
    }, 'The answer is assembled from approved facts available at the selected story point.')
  }

  return <section className="series-desk">
    <header className="series-desk-heading">
      <div><span>THE AUTHOR'S UNIVERSE</span><h1>Series Desk</h1>
        <p>Your books, your facts, your timeline. Nothing becomes canon until you approve its evidence.</p>
      </div>
      <div className="series-desk-select"><label>Working in
        <select aria-label="Select a series" value={selectedId} onChange={event => setSelectedId(event.target.value)}>
          {!seriesList.length && <option value="">No series yet</option>}
          {seriesList.map(item => <option key={item.id} value={item.id}>{item.title} ({item.volume_count || 0} books)</option>)}
        </select></label></div>
    </header>
    {error && <p role="alert" className="series-desk-error">{error}</p>}
    {notice && <p role="status" className="series-desk-success">{notice}</p>}
    <div className="series-desk-create">
      <details open={!seriesList.length}>
        <summary>＋ Create a new fictional universe</summary>
        <div className="series-desk-inline">
          <label>Series name <input value={newTitle} maxLength={160}
            onChange={event => setNewTitle(event.target.value)} placeholder="The Starfall Cycle" /></label>
          <label>Short description (optional) <input value={newDescription} maxLength={2000}
            onChange={event => setNewDescription(event.target.value)} placeholder="An intergenerational fantasy series" /></label>
          <button type="button" disabled={busy || !newTitle.trim()} onClick={() => void createSeries()}>
            Create series</button>
        </div>
      </details>
      <details>
        <summary>↥ Restore a private Series Vault backup (.zip)</summary>
        <div className="series-desk-inline">
          <label>Series Vault backup
            <input type="file" accept=".zip,application/zip"
              onChange={event => setRestoreFile(event.target.files?.[0] || null)} />
          </label>
          <label className="series-desk-check">
            <input type="checkbox" checked={restoreRights}
              onChange={event => setRestoreRights(event.target.checked)} />
            <span>I own or have permission to restore the manuscripts in this backup.</span>
          </label>
          <button type="button" disabled={busy || !restoreFile || !restoreRights}
            onClick={() => void restoreSeries()}>Restore as a new series</button>
        </div>
      </details>
    </div>
    {series && <>
      <nav className="series-desk-tabs" aria-label="Series Desk views">
        <button type="button" className={view === 'observatory' ? 'active' : ''} onClick={() => setView('observatory')}>✧ · Story Observatory</button>
        <button type="button" className={view === 'vault' ? 'active' : ''} onClick={() => setView('vault')}>01 · Series Vault</button>
        <button type="button" className={view === 'canon' ? 'active' : ''} onClick={() => setView('canon')}>02 · Canon Graph <small>{facts.filter(item => item.status === 'proposed').length} waiting</small></button>
        <button type="button" className={view === 'timeline' ? 'active' : ''} onClick={() => setView('timeline')}>03 · Time & Knowledge</button>
        <button type="button" className={view === 'guardian' ? 'active' : ''} onClick={() => setView('guardian')}>04 · Continuity</button>
        <button type="button" className={view === 'consequences' ? 'active' : ''} onClick={() => setView('consequences')}>05 · Consequences</button>
        <button type="button" className={view === 'ember' ? 'active' : ''} onClick={() => setView('ember')}>06 · Ask Ember</button>
      </nav>
      {view === 'observatory' && <StoryObservatory
        key={series.id} seriesId={series.id} entities={entities} facts={facts} volumes={series.volumes || []}
        busy={busy} onReview={(factId, decision) => void reviewFact(factId, decision)}
        onOpenCanon={() => setView('canon')} onOpenVault={() => setView('vault')}
        onDiscoverySaved={() => void loadSelected(series.id)}
        onInspectSource={id => { setSourceId(id); setView('canon') }} />}
      {(view === 'guardian' || view === 'consequences' || view === 'ember') &&
        <SeriesProfessionalTools mode={view} seriesId={series.id}
          volumes={series.volumes || []} entities={entities}
          onOpenPanel={panel => setView(panel)} />}
      {view === 'vault' && <div className="series-desk-content">
        <div className="series-desk-card">
          <h2>Books in {series.title}</h2>
          <p><a className="series-desk-backup" href={`${API}/series/${series.id}/backup`}
            download="emberwriter-series-backup.zip">↓ Download private series backup (.zip)</a></p>
          <p className="series-desk-hint">This portable archive includes your source snapshots, approved and pending canon, and book structure. Keep it private: it contains manuscript text.</p>
          <p className="series-desk-hint">The vault preserves a source snapshot when a book is added. Later edits to a linked project are flagged rather than silently replacing the evidence.</p>
          <details className="series-desk-danger">
            <summary>Delete this series vault (does not delete manuscript projects)</summary>
            <p>Permanent: removes this series, its archived source snapshots and canon facts. Your original linked books remain separate and untouched. Download a backup first if you may need the vault again.</p>
            <label>Type the full series title: <strong>{series.title}</strong>
              <input value={deleteConfirmation} maxLength={160}
                onChange={event => setDeleteConfirmation(event.target.value)}
                placeholder="Type the exact series title" /></label>
            <button type="button" disabled={busy || deleteConfirmation !== series.title}
              onClick={() => void deleteSelectedSeries()}>Permanently delete this series vault</button>
          </details>
          {series.volumes?.length ? <div className="series-desk-books">
            {series.volumes.map(book => <article key={book.id}>
              <div className="series-desk-book-index">{String(book.ordinal).padStart(2, '0')}</div>
              <div><strong>{book.title}</strong><p>{book.kind.replaceAll('_', ' ')} · {book.edition_status} · {book.source_count} sources</p>
                {book.project_slug && <small>Linked project: {book.project_slug}</small>}
                <details><summary>Source documents</summary>
                  {book.sources.map(src => <button key={src.id} type="button"
                    onClick={() => { setSourceId(src.id); setView('canon') }}>
                    {src.title} · inspect evidence →</button>)}
                </details>
                <details className="series-desk-edit-volume"><summary>Edit book details</summary>
                  <label>Book title <input value={volumeEdits[book.id]?.title ?? book.title}
                    onChange={event => setVolumeEdits(prev => ({
                      ...prev, [book.id]: {title: event.target.value,
                        ordinal: prev[book.id]?.ordinal ?? book.ordinal,
                        kind: prev[book.id]?.kind ?? book.kind,
                        edition_status: prev[book.id]?.edition_status ?? book.edition_status},
                    }))} /></label>
                  <label>Book order <input type="number" min={1} max={9999}
                    value={volumeEdits[book.id]?.ordinal ?? book.ordinal}
                    onChange={event => setVolumeEdits(prev => ({
                      ...prev, [book.id]: {title: prev[book.id]?.title ?? book.title,
                        ordinal: Number(event.target.value),
                        kind: prev[book.id]?.kind ?? book.kind,
                        edition_status: prev[book.id]?.edition_status ?? book.edition_status},
                    }))} /></label>
                  <label>Edition status <select
                    value={volumeEdits[book.id]?.edition_status ?? book.edition_status}
                    onChange={event => setVolumeEdits(prev => ({
                      ...prev, [book.id]: {title: prev[book.id]?.title ?? book.title,
                        ordinal: prev[book.id]?.ordinal ?? book.ordinal,
                        kind: prev[book.id]?.kind ?? book.kind,
                        edition_status: event.target.value},
                    }))}>
                    {statuses.map(item => <option value={item.value} key={item.value}>{item.label}</option>)}
                  </select></label>
                  <button type="button" disabled={busy || !volumeEdits[book.id]}
                    onClick={() => void saveVolume(book)}>Save book details</button>
                </details>
              </div>
            </article>)}
          </div> : <div className="series-desk-empty">No books yet. Add the first volume below. Nothing needs to be retyped.</div>}
        </div>
        <div className="series-desk-card">
          <h2>Add a book or story</h2>
          <p className="series-desk-hint">Link one of your existing EmberWriter books or import an authorized source file. Your original is never edited.</p>
          <div className="series-desk-switch"><button type="button" className={addMode === 'project' ? 'active' : ''}
            onClick={() => setAddMode('project')}>Use an existing writing project</button>
            <button type="button" className={addMode === 'document' ? 'active' : ''}
              onClick={() => setAddMode('document')}>Import a manuscript file</button></div>
          <div className="series-desk-form">
            {addMode === 'project' ? <label>Project to link
              <select value={linkProject || project?.slug || ''} onChange={event => setLinkProject(event.target.value)}>
                {!projects.length && <option value="">No writing projects found</option>}
                {projects.map(p => <option key={p.slug} value={p.slug}>{p.name}</option>)}
              </select>
            </label> : <label>Choose TXT, Markdown, DOCX, EPUB or text-based PDF (25 MB maximum)
              <input type="file" accept=".txt,.md,.docx,.epub,.pdf" onChange={event => setDocumentFile(event.target.files?.[0] || null)} />
            </label>}
            <label>Book order <input type="number" min={1} max={9999} value={volumeOrdinal}
              onChange={event => setVolumeOrdinal(Number(event.target.value))} /></label>
            <label>Book title (optional) <input value={volumeTitle} onChange={event => setVolumeTitle(event.target.value)}
              maxLength={180} placeholder="Use the existing title" /></label>
            <label>Type <select value={volumeKind} onChange={event => setVolumeKind(event.target.value)}>
              {formats.map(f => <option key={f.value} value={f.value}>{f.label}</option>)}</select></label>
            <label>Editorial status <select value={editionStatus}
              onChange={event => setEditionStatus(event.target.value)}>
              {statuses.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}
            </select></label>
            <label className="series-desk-check"><input type="checkbox" checked={rightsConfirmed}
              onChange={event => setRightsConfirmed(event.target.checked)} />
              <span>I own or have permission to add this material to my private series library.</span></label>
            <button type="button" className="series-desk-primary" disabled={busy || !rightsConfirmed ||
              (addMode === 'document' && !documentFile) || (addMode === 'project' && !projects.length)}
              onClick={() => void addVolume()}>Add to Series Vault</button>
          </div>
        </div>
      </div>}
      {view === 'canon' && <div className="series-desk-content">
        <div className="series-desk-card">
          <h2>People, places, objects & rules</h2>
          <p className="series-desk-hint">Entities are names in the index. They become a canon graph through source-linked facts that you approve.</p>
          <div className="series-desk-inline">
            <label>Name <input value={entityName} onChange={event => setEntityName(event.target.value)}
              maxLength={120} placeholder="Moon Key" /></label>
            <label>Kind <select value={entityKind} onChange={event => setEntityKind(event.target.value)}>
              {['character','place','artifact','faction','species','rule','event','concept'].map(kind =>
                <option key={kind} value={kind}>{kind}</option>)}</select></label>
            <label>Aliases, separated by commas <input value={entityAliases}
              onChange={event => setEntityAliases(event.target.value)} placeholder="the key, silver key" /></label>
            <button type="button" disabled={busy || !entityName.trim()} onClick={() => void createEntity()}>Add to index</button>
          </div>
          <div className="series-desk-entity-list">
            {entities.map(item => <div key={item.id}><strong>{item.name}</strong><small>{item.kind}
              {item.aliases.length ? ` · also ${item.aliases.join(', ')}` : ''}</small></div>)}
            {!entities.length && <p>Add a character or world element to begin your graph.</p>}
          </div>
        </div>
        <div className="series-desk-card">
          <h2>Propose an evidenced fact</h2>
          <p className="series-desk-hint">Select an exact passage in one of your books. A proposal is not canon until you approve it.</p>
          <div className="series-desk-form">
            <label>Source document
              <select value={sourceId} onChange={event => { setSourceId(event.target.value); setQuote(''); setSourceQuery('');
                setStartBook(sources.find(item => item.id === event.target.value)?.ordinal || 1)
                setStartSequence(0); setEndBook('') }}>
                {!sources.length && <option value="">Add a book first</option>}
                {sources.map(row => <option key={row.id} value={row.id}>Book {row.ordinal} · {row.volumeTitle} · {row.title}</option>)}
              </select></label>
            <label>Find a phrase in this book <input value={sourceQuery} maxLength={400}
              onChange={event => { setSourceQuery(event.target.value); setQuote('') }}
              placeholder="Enter exact words to locate evidence" /></label>
            {selectedSource && <div className="series-desk-evidence">
              <small>Immutable evidence snapshot · {selectedSource.source_path}</small>
              {excerpt?.found ? <>
                <pre className="series-desk-excerpt">{excerpt.excerpt}</pre>
                <button type="button" onClick={() => {
                  const selected = window.getSelection()?.toString().trim() || ''
                  if (selected && selected.length <= 2000 && excerpt.excerpt.includes(selected)) setQuote(selected)
                  else setError('Highlight up to 2,000 characters within the excerpt, then select this action.')
                }}>Use my highlighted text as evidence</button>
                <small>Showing characters {excerpt.excerpt_start + 1}–{excerpt.excerpt_end} of {excerpt.total_characters}. Search another phrase to reach later pages.</small>
              </> : <p>No matching passage. Try a different phrase.</p>}
            </div>}
            {excerpt?.found && <div className="series-desk-suggest">
              <strong>Optional · let local AI suggest possible canon facts</strong>
              <p className="series-desk-hint">This sends only your selected quote—or up to 1,900 characters of the visible excerpt—to your installed local Ollama model. The model cannot save or approve canon. Its suggested quotes must match your source exactly.</p>
              <label>Local model <select value={suggestionModel} onChange={event => setSuggestionModel(event.target.value)}>
                <option value="">Choose an installed local AI model</option>
                {localModels.map(item => <option key={item} value={item}>{item}</option>)}
              </select></label>
              <button type="button" disabled={busy || !suggestionModel ||
                (quoteStart >= 0 && quote.length > 2000)}
                onClick={() => void suggestFromSource()}>Suggest facts from this passage</button>
              {discardedSuggestions > 0 && <p className="series-desk-hint">{discardedSuggestions} unverified or unsupported suggestion(s) discarded.</p>}
              {suggestions.map((candidate, index) => <div className="series-desk-candidate" key={index}>
                <strong>{candidate.subject_name} — {candidate.predicate.replaceAll('_',' ')} — {candidate.object_text}</strong>
                <small>{candidate.scope.replaceAll('_',' ')}</small>
                <blockquote>“{candidate.quote}”</blockquote>
                <button type="button" onClick={() => useSuggestion(candidate)}>Use this in the proposal form</button>
              </div>)}
            </div>}
            <label>Exact quote (copy from the excerpt above) <textarea rows={3} maxLength={2000}
              value={quote} onChange={event => setQuote(event.target.value)} /></label>
            <p className={quoteStart >= 0 ? 'series-desk-success' : 'series-desk-hint'}>
              {quoteStart >= 0 ? `Exact source confirmed · characters ${quoteStart}–${quoteEnd}`
                : 'Copy or highlight the precise source text before proposing a fact.'}</p>
            <label>Subject <select value={subjectId} onChange={event => setSubjectId(event.target.value)}>
              <option value="">Choose subject</option>
              {entities.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
            <label>Relationship / rule (snake_case) <input value={predicate}
              onChange={event => setPredicate(event.target.value)} maxLength={60}
              placeholder="located_in, knows, cannot_use" /></label>
            <label>Value (if not another entity) <input value={objectText} maxLength={500}
              onChange={event => setObjectText(event.target.value)} placeholder="The north tower" /></label>
            <label>Or target another entity <select value={objectEntityId}
              onChange={event => setObjectEntityId(event.target.value)}>
              <option value="">A text value instead</option>
              {entities.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select></label>
            <label>Knowledge category <select value={scope}
              onChange={event => { setScope(event.target.value as typeof scope); setAnswer(null) }}>
              <option value="world">World truth (author-established)</option>
              <option value="character_belief">What a character believes</option>
              <option value="reader_reveal">What readers have learned</option>
            </select></label>
            {scope === 'character_belief' && <label>Who believes it?
              <select value={knowerId} onChange={event => setKnowerId(event.target.value)}>
                <option value="">Choose character</option>
                {entities.filter(e => e.kind === 'character').map(item =>
                  <option key={item.id} value={item.id}>{item.name}</option>)}
              </select></label>}
            <label>True or known starting in book
              <select value={startBook} onChange={event => setStartBook(Number(event.target.value))}>
                {series.volumes?.map(item => <option key={item.id} value={item.ordinal}>
                  {item.ordinal} · {item.title}</option>)}
              </select></label>
            <details><summary>Advanced: scene sequence and when a fact stops being true</summary>
              <label>Sequence in book (0 = beginning, 999999 = end)
                <input type="number" min={0} max={999999} value={startSequence}
                  onChange={event => setStartSequence(Number(event.target.value))} /></label>
              <label>Last book in which this fact applies (optional)
                <select value={endBook} onChange={event => setEndBook(event.target.value)}>
                  <option value="">Still true / unknown</option>
                  {series.volumes?.map(item => <option key={item.id} value={item.ordinal}>{item.ordinal} · {item.title}</option>)}
                </select></label>
            </details>
            <button type="button" className="series-desk-primary"
              disabled={busy || !subjectId || quoteStart < 0 || !sourceId || !predicate.trim() ||
                (!objectText.trim() && !objectEntityId) || (scope === 'character_belief' && !knowerId)}
              onClick={() => void proposeFact()}>Save proposal for author review</button>
          </div>
        </div>
        <div className="series-desk-card series-desk-review">
          <h2>Canon review board</h2>
          <label className="series-desk-check"><input type="checkbox" checked={showPending}
            onChange={event => setShowPending(event.target.checked)} />
            <span>Show proposals awaiting review only</span></label>
          {facts.filter(item => !showPending || item.status === 'proposed').map(item =>
            <article key={item.id} className="series-desk-fact">
              <div className="series-desk-fact-head"><strong>{item.subject_name} · {item.predicate.replaceAll('_', ' ')}</strong>
                <span>{item.status}</span></div>
              <p>{item.object_name || item.object_text} · {item.scope.replaceAll('_', ' ')}
                {item.knower_name ? ` · believed by ${item.knower_name}` : ''}</p>
              <blockquote>“{item.quote}”</blockquote>
              <small>Book {item.reference.book} · {item.reference.volume} · {item.reference.source_path}</small>
              {item.status === 'proposed' && <div className="series-desk-actions">
                <button type="button" disabled={busy} onClick={() => void reviewFact(item.id, 'approved')}>Approve as canon</button>
                <button type="button" disabled={busy} onClick={() => void reviewFact(item.id, 'rejected')}>Reject proposal</button>
              </div>}
            </article>)}
          {!facts.some(item => !showPending || item.status === 'proposed') &&
            <p className="series-desk-hint">Nothing waiting. Approved facts appear in the timeline view.</p>}
        </div>
      </div>}
      {view === 'timeline' && <div className="series-desk-content">
        <div className="series-desk-card">
          <h2>What was true, believed, or revealed?</h2>
          <p className="series-desk-hint">Use an as-of book boundary. EmberWriter will not cite a later book or invent a missing fact.</p>
          <div className="series-desk-form">
            <label>As of book <select value={pointBook} onChange={event => { setPointBook(Number(event.target.value)); setAnswer(null) }}>
              {series.volumes?.map(item => <option value={item.ordinal} key={item.id}>
                Book {item.ordinal} · {item.title}</option>)}
            </select></label>
            <label>Knowledge point <select value={scope} onChange={event => { setScope(event.target.value as typeof scope); setAnswer(null) }}>
              <option value="world">Established world truth</option>
              <option value="character_belief">A character's beliefs</option>
              <option value="reader_reveal">What readers have learned</option>
            </select></label>
            {scope === 'character_belief' && <label>Which character?
              <select value={knowerId} onChange={event => setKnowerId(event.target.value)}>
                <option value="">Choose a character</option>
                {entities.filter(item => item.kind === 'character').map(item =>
                  <option key={item.id} value={item.id}>{item.name}</option>)}
              </select></label>}
            <details><summary>Advanced: stop at a moment within this book</summary>
              <label>As-of scene sequence <input type="number" min={0} max={999999}
                value={pointSequence} onChange={event => setPointSequence(Number(event.target.value))} /></label>
            </details>
            <label>Specific character, place or artifact (optional)
              <select value={querySubjectId} onChange={event => setQuerySubjectId(event.target.value)}>
                <option value="">Recognize entity from question</option>
                {entities.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
            </label>
            <label>Ask the universe <textarea rows={3} value={question}
              onChange={event => setQuestion(event.target.value)}
              placeholder="What does Lyra know about the Moon Key?" /></label>
            <button type="button" className="series-desk-primary" disabled={busy || !series.volumes?.length ||
              !question.trim() || (scope === 'character_belief' && !knowerId)}
              onClick={() => void ask()}>Find evidence at this point in the story</button>
          </div>
          {answer && <div className="series-desk-answer" role="region" aria-label="Source-grounded timeline answer">
            <h3>Series research · Book {pointBook}</h3>
            <p>{answer.answer}</p>
            {answer.conflicts.length > 0 && <div className="series-desk-error">
              <strong>Author review needed: competing approved facts</strong>
              {answer.conflicts.map((item, i) => <p key={i}>{item.subject} · {item.predicate}</p>)}
            </div>}
            {answer.facts.map((fact, index) => <details key={fact.id}>
              <summary>[{index + 1}] {fact.subject_name} · {fact.predicate.replaceAll('_', ' ')}
                · Book {fact.reference.book}</summary>
              <blockquote>“{fact.reference.quote}”</blockquote>
              <small>{fact.reference.volume} · {fact.reference.source_path}
                · characters {fact.reference.start}–{fact.reference.end}</small>
            </details>)}
            <small>Evidence only: this is not a generative answer. Unapproved assertions, later books and other knowledge perspectives are excluded.</small>
          </div>}
        </div>
        <div className="series-desk-card">
          <h2>Approved world history</h2>
          <p className="series-desk-hint">Canon events are shown in book order. Changed truths have explicit start/end windows rather than overwriting previous history.</p>
          {timeline.map(event => <article className="series-desk-history" key={event.id}>
            <small>Book {event.start_book}{event.end_book ? `–${event.end_book}` : ' onward'} · {event.scope.replaceAll('_', ' ')}</small>
            <strong>{event.subject_name} — {event.predicate.replaceAll('_', ' ')} — {event.object_name || event.object_text}</strong>
            <blockquote>“{event.quote}”</blockquote>
            <small>From {event.reference.volume} · {event.reference.source_path}</small>
          </article>)}
          {!timeline.length && <div className="series-desk-empty">Nothing approved yet. Add a book, create an entity, and approve a supported fact in Canon Graph.</div>}
        </div>
      </div>}
    </>}
    {!series && <div className="series-desk-empty">
      <strong>Build a fictional universe that remembers itself.</strong>
      <p>Create your first Series Vault above, then attach existing manuscripts or import your own book files.</p>
    </div>}
  </section>
}
