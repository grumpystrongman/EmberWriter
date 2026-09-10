import { useEffect, useMemo, useState } from 'react'

import './distribution.css'

type Retailer = 'kdp' | 'ingramspark' | 'apple_books' | 'kobo' | 'direct'
type EditionFormat = 'ebook' | 'paperback' | 'hardcover'
type IdentifierMode = 'own' | 'retailer_assigned' | 'none'
type RightsScope = 'worldwide' | 'territories'
type ContributorRole = 'author' | 'editor' | 'illustrator' | 'translator' | 'other'

type Contributor = {
  name: string
  role: ContributorRole
}

type ReleaseEdition = {
  id: string
  format: EditionFormat
  enabled: boolean
  retailers: Retailer[]
  identifier_mode: IdentifierMode
  isbn: string
  price: number
  currency: string
  interior_path: string
  cover_path: string
  trim_width: number
  trim_height: number
  page_count: number
  drm: boolean
  expanded_distribution: boolean
}

type ReleaseProfile = {
  schema_version: number
  title: string
  subtitle: string
  series_name: string
  series_number: string
  author: string
  contributors: Contributor[]
  publisher: string
  imprint: string
  description: string
  short_description: string
  author_bio: string
  language: string
  publication_date: string
  release_date: string
  original_publication_date: string
  explicit_content: boolean
  public_domain: boolean
  reading_age_min: number | null
  reading_age_max: number | null
  rights_scope: RightsScope
  territories: string[]
  keywords: string[]
  kdp_categories: string[]
  bisac_codes: string[]
  thema_codes: string[]
  apple_categories: string[]
  kobo_categories: string[]
  editions: ReleaseEdition[]
}

type ReleaseArtifact = {
  relative_path: string
  filename: string
  suffix: string
  bytes: number
  sha256: string
  role: 'ebook_interior' | 'print_interior' | 'cover' | 'editorial' | 'unknown'
  modified_at: string
}

type ValidationIssue = {
  level: 'error' | 'warning' | 'info'
  code: string
  message: string
  retailer: Retailer | null
  edition_id: string | null
  authority: string
  authority_url: string
}

type Validation = {
  valid: boolean
  issues: ValidationIssue[]
  enabled_editions: number
  selected_retailers: Retailer[]
}

type PackageArtifact = {
  format: 'zip' | 'json' | 'csv'
  filename: string
  relative_path: string
  bytes: number
}

type BuildResult = {
  release_id: string
  validation: Validation
  artifacts: PackageArtifact[]
}

type Props = {
  apiBase: string
  slug: string
  projectName: string
  disabled: boolean
}

const RETAILERS: { id: Retailer; label: string }[] = [
  { id: 'kdp', label: 'Amazon KDP' },
  { id: 'ingramspark', label: 'IngramSpark' },
  { id: 'apple_books', label: 'Apple Books' },
  { id: 'kobo', label: 'Kobo' },
  { id: 'direct', label: 'Direct / other' },
]

const CONTRIBUTOR_ROLES: { id: ContributorRole; label: string }[] = [
  { id: 'author', label: 'Author' },
  { id: 'editor', label: 'Editor' },
  { id: 'illustrator', label: 'Illustrator' },
  { id: 'translator', label: 'Translator' },
  { id: 'other', label: 'Other' },
]

async function jsonRequest<T>(url: string, init?: RequestInit): Promise<T> {
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

function lines(value: string) {
  return value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean)
}

function commas(value: string) {
  return value.split(',').map((item) => item.trim()).filter(Boolean)
}

function humanBytes(value: number) {
  if (value < 1024 * 1024) return `${Math.max(1, Math.round(value / 1024)).toLocaleString()} KB`
  return `${(value / (1024 * 1024)).toFixed(1)} MB`
}

function retailerLabel(value: Retailer) {
  return RETAILERS.find((item) => item.id === value)?.label || value
}

export default function DistributionPanel({ apiBase, slug, projectName, disabled }: Props) {
  const [profile, setProfile] = useState<ReleaseProfile | null>(null)
  const [artifacts, setArtifacts] = useState<ReleaseArtifact[]>([])
  const [validation, setValidation] = useState<Validation | null>(null)
  const [result, setResult] = useState<BuildResult | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function refreshArtifacts() {
    const next = await jsonRequest<ReleaseArtifact[]>(`${apiBase}/projects/${slug}/distribution/artifacts`)
    setArtifacts(next)
  }

  useEffect(() => {
    if (!slug) return
    setError('')
    setResult(null)
    void Promise.all([
      jsonRequest<ReleaseProfile>(`${apiBase}/projects/${slug}/distribution/profile`),
      jsonRequest<ReleaseArtifact[]>(`${apiBase}/projects/${slug}/distribution/artifacts`),
    ])
      .then(([nextProfile, nextArtifacts]) => {
        setProfile({
          ...nextProfile,
          title: nextProfile.title === 'Untitled' ? projectName : nextProfile.title,
        })
        setArtifacts(nextArtifacts)
      })
      .catch((cause) => setError((cause as Error).message))
  }, [apiBase, slug, projectName])

  useEffect(() => {
    if (!profile || !slug) return
    const timer = window.setTimeout(() => {
      void jsonRequest<Validation>(`${apiBase}/projects/${slug}/distribution/validate`, {
        method: 'POST',
        body: JSON.stringify(profile),
      })
        .then(setValidation)
        .catch((cause) => setError((cause as Error).message))
    }, 300)
    return () => window.clearTimeout(timer)
  }, [apiBase, slug, profile])

  const selectedFileCount = useMemo(
    () => profile?.editions.filter((edition) => edition.enabled).reduce(
      (count, edition) =>
        count + Number(Boolean(edition.interior_path)) + Number(Boolean(edition.cover_path)),
      0,
    ) || 0,
    [profile],
  )

  function setEdition(index: number, patch: Partial<ReleaseEdition>) {
    if (!profile) return
    const editions = profile.editions.map((edition, currentIndex) =>
      currentIndex === index ? { ...edition, ...patch } : edition,
    )
    setProfile({ ...profile, editions })
    setResult(null)
  }

  function setContributor(index: number, patch: Partial<Contributor>) {
    if (!profile) return
    const contributors = profile.contributors.map((contributor, currentIndex) =>
      currentIndex === index ? { ...contributor, ...patch } : contributor,
    )
    setProfile({ ...profile, contributors })
    setResult(null)
  }

  function addContributor() {
    if (!profile) return
    setProfile({ ...profile, contributors: [...profile.contributors, { name: '', role: 'other' }] })
    setResult(null)
  }

  function removeContributor(index: number) {
    if (!profile) return
    setProfile({
      ...profile,
      contributors: profile.contributors.filter((_, currentIndex) => currentIndex !== index),
    })
    setResult(null)
  }

  function toggleRetailer(index: number, retailer: Retailer, checked: boolean) {
    if (!profile) return
    const current = profile.editions[index]
    const retailers = checked
      ? [...new Set([...current.retailers, retailer])]
      : current.retailers.filter((item) => item !== retailer)
    setEdition(index, { retailers })
  }

  function artifactOptions(edition: ReleaseEdition, role: 'interior' | 'cover') {
    return artifacts.filter((artifact) => {
      if (edition.format === 'ebook') {
        return role === 'interior'
          ? artifact.role === 'ebook_interior' && artifact.suffix === '.epub'
          : artifact.role === 'cover' &&
              ['.jpg', '.jpeg', '.png', '.tif', '.tiff'].includes(artifact.suffix)
      }
      return role === 'interior'
        ? artifact.role === 'print_interior' && artifact.suffix === '.pdf'
        : artifact.role === 'cover' && artifact.suffix === '.pdf'
    })
  }

  async function saveProfile() {
    if (!profile || busy) return
    setBusy(true)
    setError('')
    try {
      const saved = await jsonRequest<ReleaseProfile>(
        `${apiBase}/projects/${slug}/distribution/profile`,
        {
          method: 'PUT',
          body: JSON.stringify(profile),
        },
      )
      setProfile(saved)
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function buildRelease() {
    if (!profile || busy) return
    setBusy(true)
    setError('')
    try {
      const built = await jsonRequest<BuildResult>(
        `${apiBase}/projects/${slug}/distribution/build`,
        {
          method: 'POST',
          body: JSON.stringify(profile),
        },
      )
      setResult(built)
      setValidation(built.validation)
      await refreshArtifacts()
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  if (!profile) {
    return (
      <details className="authoring-panel distribution-panel">
        <summary>Release &amp; Distribution <small>Loading…</small></summary>
        <div className="authoring-panel-body">
          {error && <small className="panel-error">{error}</small>}
        </div>
      </details>
    )
  }

  const controlsDisabled = disabled || busy

  return (
    <details className="authoring-panel distribution-panel" open>
      <summary>
        Release &amp; Distribution <small>metadata · editions · handoff package</small>
      </summary>
      <div className="authoring-panel-body distribution-body">
        <div className="distribution-status-strip">
          <span><b>{profile.editions.filter((edition) => edition.enabled).length}</b> editions</span>
          <span><b>{validation?.selected_retailers.length || 0}</b> retailers</span>
          <span><b>{selectedFileCount}</b> selected files</span>
          <button type="button" onClick={() => void refreshArtifacts()} disabled={controlsDisabled}>
            Refresh exports
          </button>
        </div>

        <div className="distribution-grid">
          <label>Title<input value={profile.title} onChange={(event) => setProfile({ ...profile, title: event.target.value })} disabled={controlsDisabled} /></label>
          <label>Subtitle<input value={profile.subtitle} onChange={(event) => setProfile({ ...profile, subtitle: event.target.value })} disabled={controlsDisabled} /></label>
          <label>Primary author / pen name<input value={profile.author} onChange={(event) => setProfile({ ...profile, author: event.target.value })} disabled={controlsDisabled} /></label>
          <label>Publisher<input value={profile.publisher} onChange={(event) => setProfile({ ...profile, publisher: event.target.value })} disabled={controlsDisabled} /></label>
          <label>Imprint<input value={profile.imprint} onChange={(event) => setProfile({ ...profile, imprint: event.target.value })} disabled={controlsDisabled} /></label>
          <label>Language<input value={profile.language} onChange={(event) => setProfile({ ...profile, language: event.target.value })} disabled={controlsDisabled} /></label>
          <label>Series name<input value={profile.series_name} onChange={(event) => setProfile({ ...profile, series_name: event.target.value })} disabled={controlsDisabled} /></label>
          <label>Series number<input value={profile.series_number} onChange={(event) => setProfile({ ...profile, series_number: event.target.value })} disabled={controlsDisabled} /></label>
          <label className="distribution-wide">Store description<textarea rows={7} value={profile.description} onChange={(event) => setProfile({ ...profile, description: event.target.value })} disabled={controlsDisabled} /></label>
        </div>

        <details className="distribution-subpanel">
          <summary>Contributors <small>{profile.contributors.length || 'none'}</small></summary>
          <div className="contributor-stack">
            {profile.contributors.map((contributor, index) => (
              <div className="contributor-row" key={`${index}-${contributor.role}`}>
                <input
                  aria-label={`Contributor ${index + 1} name`}
                  value={contributor.name}
                  onChange={(event) => setContributor(index, { name: event.target.value })}
                  placeholder="Contributor name"
                  disabled={controlsDisabled}
                />
                <select
                  aria-label={`Contributor ${index + 1} role`}
                  value={contributor.role}
                  onChange={(event) =>
                    setContributor(index, { role: event.target.value as ContributorRole })
                  }
                  disabled={controlsDisabled}
                >
                  {CONTRIBUTOR_ROLES.map((role) => (
                    <option key={role.id} value={role.id}>{role.label}</option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={() => removeContributor(index)}
                  disabled={controlsDisabled}
                >
                  Remove
                </button>
              </div>
            ))}
            <button type="button" onClick={addContributor} disabled={controlsDisabled}>
              Add contributor
            </button>
          </div>
        </details>

        <details className="distribution-subpanel" open>
          <summary>Discoverability &amp; storefront metadata</summary>
          <div className="distribution-grid">
            <label className="distribution-wide">Keywords / phrases <small>KDP currently accepts up to seven.</small><input value={profile.keywords.join(', ')} onChange={(event) => setProfile({ ...profile, keywords: commas(event.target.value) })} placeholder="dark fantasy, found family, gothic mystery" disabled={controlsDisabled} /></label>
            <label>KDP categories <small>One per line; maximum three.</small><textarea rows={4} value={profile.kdp_categories.join('\n')} onChange={(event) => setProfile({ ...profile, kdp_categories: lines(event.target.value) })} disabled={controlsDisabled} /></label>
            <label>Apple Books categories <small>At least one for Apple handoff.</small><textarea rows={4} value={profile.apple_categories.join('\n')} onChange={(event) => setProfile({ ...profile, apple_categories: lines(event.target.value) })} disabled={controlsDisabled} /></label>
            <label>Kobo categories<textarea rows={4} value={profile.kobo_categories.join('\n')} onChange={(event) => setProfile({ ...profile, kobo_categories: lines(event.target.value) })} disabled={controlsDisabled} /></label>
            <label>BISAC codes<textarea rows={4} value={profile.bisac_codes.join('\n')} onChange={(event) => setProfile({ ...profile, bisac_codes: lines(event.target.value) })} placeholder="FIC009000" disabled={controlsDisabled} /></label>
            <label>Thema codes<textarea rows={4} value={profile.thema_codes.join('\n')} onChange={(event) => setProfile({ ...profile, thema_codes: lines(event.target.value) })} disabled={controlsDisabled} /></label>
            <label className="distribution-wide">Short description<textarea rows={3} value={profile.short_description} onChange={(event) => setProfile({ ...profile, short_description: event.target.value })} disabled={controlsDisabled} /></label>
            <label className="distribution-wide">Author bio<textarea rows={3} value={profile.author_bio} onChange={(event) => setProfile({ ...profile, author_bio: event.target.value })} disabled={controlsDisabled} /></label>
          </div>
        </details>

        <details className="distribution-subpanel">
          <summary>Rights, dates &amp; audience</summary>
          <div className="distribution-grid">
            <label>Publication date<input type="date" value={profile.publication_date} onChange={(event) => setProfile({ ...profile, publication_date: event.target.value })} disabled={controlsDisabled} /></label>
            <label>Release date<input type="date" value={profile.release_date} onChange={(event) => setProfile({ ...profile, release_date: event.target.value })} disabled={controlsDisabled} /></label>
            <label>Original publication date<input type="date" value={profile.original_publication_date} onChange={(event) => setProfile({ ...profile, original_publication_date: event.target.value })} disabled={controlsDisabled} /></label>
            <label>Rights<select value={profile.rights_scope} onChange={(event) => setProfile({ ...profile, rights_scope: event.target.value as RightsScope })} disabled={controlsDisabled}><option value="worldwide">Worldwide rights</option><option value="territories">Selected territories</option></select></label>
            {profile.rights_scope === 'territories' && <label className="distribution-wide">Territories <small>One country/territory per line.</small><textarea rows={4} value={profile.territories.join('\n')} onChange={(event) => setProfile({ ...profile, territories: lines(event.target.value) })} disabled={controlsDisabled} /></label>}
            <label>Minimum reading age<input type="number" min="0" max="120" value={profile.reading_age_min ?? ''} onChange={(event) => setProfile({ ...profile, reading_age_min: event.target.value ? Number(event.target.value) : null })} disabled={controlsDisabled} /></label>
            <label>Maximum reading age<input type="number" min="0" max="120" value={profile.reading_age_max ?? ''} onChange={(event) => setProfile({ ...profile, reading_age_max: event.target.value ? Number(event.target.value) : null })} disabled={controlsDisabled} /></label>
            <label className="distribution-check"><input type="checkbox" checked={profile.explicit_content} onChange={(event) => setProfile({ ...profile, explicit_content: event.target.checked })} disabled={controlsDisabled} /> Explicit-content flag</label>
            <label className="distribution-check"><input type="checkbox" checked={profile.public_domain} onChange={(event) => setProfile({ ...profile, public_domain: event.target.checked })} disabled={controlsDisabled} /> Public-domain work</label>
          </div>
        </details>

        <div className="edition-stack">
          {profile.editions.map((edition, index) => {
            const interiorOptions = artifactOptions(edition, 'interior')
            const coverOptions = artifactOptions(edition, 'cover')
            return (
              <section className={`edition-card ${edition.enabled ? 'enabled' : ''}`} key={`${edition.id}-${index}`}>
                <header>
                  <label className="distribution-check"><input type="checkbox" checked={edition.enabled} onChange={(event) => setEdition(index, { enabled: event.target.checked })} disabled={controlsDisabled} /> Enable</label>
                  <strong>{edition.format.toUpperCase()}</strong>
                  <small>{edition.id}</small>
                </header>
                {edition.enabled && (
                  <>
                    <div className="retailer-pills">
                      {RETAILERS.map((retailer) => (
                        <label key={retailer.id} className={edition.retailers.includes(retailer.id) ? 'selected' : ''}>
                          <input type="checkbox" checked={edition.retailers.includes(retailer.id)} onChange={(event) => toggleRetailer(index, retailer.id, event.target.checked)} disabled={controlsDisabled} />
                          {retailer.label}
                        </label>
                      ))}
                    </div>
                    <div className="distribution-grid edition-grid">
                      <label>Interior file<select value={edition.interior_path} onChange={(event) => setEdition(index, { interior_path: event.target.value })} disabled={controlsDisabled}><option value="">Choose generated file…</option>{interiorOptions.map((artifact) => <option key={artifact.relative_path} value={artifact.relative_path}>{artifact.filename}</option>)}</select></label>
                      <label>Cover file<select value={edition.cover_path} onChange={(event) => setEdition(index, { cover_path: event.target.value })} disabled={controlsDisabled}><option value="">Choose generated file…</option>{coverOptions.map((artifact) => <option key={artifact.relative_path} value={artifact.relative_path}>{artifact.filename}</option>)}</select></label>
                      <label>Identifier<select value={edition.identifier_mode} onChange={(event) => setEdition(index, { identifier_mode: event.target.value as IdentifierMode })} disabled={controlsDisabled}><option value="own">Owned ISBN</option><option value="retailer_assigned">Retailer-assigned ISBN / ID</option><option value="none">No ISBN</option></select></label>
                      {edition.identifier_mode === 'own' && <label>ISBN-13<input value={edition.isbn} onChange={(event) => setEdition(index, { isbn: event.target.value })} placeholder="978…" disabled={controlsDisabled} /></label>}
                      <label>List price<input type="number" min="0" max="10000" step="0.01" value={edition.price} onChange={(event) => setEdition(index, { price: Number(event.target.value) })} disabled={controlsDisabled} /></label>
                      <label>Currency<input maxLength={3} value={edition.currency} onChange={(event) => setEdition(index, { currency: event.target.value.toUpperCase() })} disabled={controlsDisabled} /></label>
                      {edition.format !== 'ebook' && <label>Final page count<input type="number" min="1" max="5000" value={edition.page_count} onChange={(event) => setEdition(index, { page_count: Number(event.target.value) })} disabled={controlsDisabled} /></label>}
                      {edition.format !== 'ebook' && <label>Trim size<div className="distribution-inline"><input type="number" min="4" max="8.5" step="0.125" value={edition.trim_width} onChange={(event) => setEdition(index, { trim_width: Number(event.target.value) })} disabled={controlsDisabled} /><span>×</span><input type="number" min="6" max="11.7" step="0.125" value={edition.trim_height} onChange={(event) => setEdition(index, { trim_height: Number(event.target.value) })} disabled={controlsDisabled} /></div></label>}
                      {edition.format === 'ebook' && <label className="distribution-check"><input type="checkbox" checked={edition.drm} onChange={(event) => setEdition(index, { drm: event.target.checked })} disabled={controlsDisabled} /> Request DRM where supported</label>}
                      {edition.format === 'paperback' && edition.retailers.includes('kdp') && <label className="distribution-check"><input type="checkbox" checked={edition.expanded_distribution} onChange={(event) => setEdition(index, { expanded_distribution: event.target.checked })} disabled={controlsDisabled} /> KDP Expanded Distribution</label>}
                    </div>
                  </>
                )}
              </section>
            )
          })}
        </div>

        {validation && (
          <div className={`distribution-validation ${validation.valid ? 'valid' : 'invalid'}`}>
            <strong>{validation.valid ? 'Release package passes Ember blocking checks' : 'Release package has blocking issues'}</strong>
            {validation.issues.length === 0 && <small>No release preflight issues found.</small>}
            {validation.issues.map((issue, index) => (
              <small key={`${issue.code}-${index}`} className={`distribution-issue issue-${issue.level}`}>
                <b>{issue.level.toUpperCase()}</b>
                {issue.retailer && <span className="retailer-badge">{retailerLabel(issue.retailer)}</span>}
                {issue.edition_id && <span className="edition-badge">{issue.edition_id}</span>}
                {issue.message}
                {issue.authority_url && <a href={issue.authority_url} target="_blank" rel="noreferrer">source</a>}
              </small>
            ))}
          </div>
        )}

        <div className="distribution-actions">
          <button type="button" onClick={() => void saveProfile()} disabled={controlsDisabled}>{busy ? 'Working…' : 'Save release metadata'}</button>
          <button type="button" className="primary" onClick={() => void buildRelease()} disabled={controlsDisabled || validation?.valid === false}>{busy ? 'Building…' : 'Build release handoff package'}</button>
        </div>

        <small className="panel-help">
          Ember builds a reproducible handoff package; it does not auto-submit a book or claim retailer approval. Use each retailer's current portal and preview/preflight before publishing.
        </small>

        {result && (
          <div className="publish-result distribution-result">
            <strong>Release {result.release_id} ready</strong>
            {result.artifacts.map((artifact) => {
              const downloadUrl = `${apiBase}/projects/${slug}/exports/download?path=${encodeURIComponent(artifact.relative_path)}`
              return <a key={artifact.relative_path} href={downloadUrl} download={artifact.filename}>Download {artifact.filename} <small>{humanBytes(artifact.bytes)}</small></a>
            })}
          </div>
        )}

        {error && <small className="panel-error">{error}</small>}
      </div>
    </details>
  )
}
