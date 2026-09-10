import { useEffect, useMemo, useState } from 'react'

import './cover.css'

type CoverPlatform = 'kdp_paperback' | 'ingramspark' | 'custom_print' | 'kdp_ebook'
type PaperType = 'white_bw' | 'cream_bw' | 'premium_color' | 'standard_color'
type FontFamily = 'Helvetica' | 'Times' | 'Courier'
type TextAlign = 'left' | 'center' | 'right'
type BarcodeMode = 'platform' | 'custom' | 'none'
type ArtworkMode = 'front' | 'full_wrap'

type CoverProfile = {
  schema_version: number
  platform: CoverPlatform
  title: string
  subtitle: string
  author: string
  back_blurb: string
  imprint: string
  isbn: string
  trim_width: number
  trim_height: number
  page_count: number
  paper_type: PaperType
  manual_spine_width: number
  bleed: number
  safe_inset: number
  spine_safe_inset: number
  ebook_width_px: number
  ebook_height_px: number
  background_color: string
  front_overlay_color: string
  back_overlay_color: string
  spine_color: string
  title_color: string
  subtitle_color: string
  author_color: string
  body_color: string
  title_font: FontFamily
  body_font: FontFamily
  title_size: number
  subtitle_size: number
  author_size: number
  body_size: number
  spine_size: number
  title_align: TextAlign
  blurb_align: TextAlign
  artwork_path: string
  artwork_mode: ArtworkMode
  artwork_opacity: number
  spine_text: string
  barcode_mode: BarcodeMode
  barcode_path: string
  barcode_width: number
  barcode_height: number
  barcode_margin: number
}

type CoverGeometry = {
  platform: CoverPlatform
  trim_width: number
  trim_height: number
  page_count: number
  bleed: number
  spine_width: number
  cover_width: number
  cover_height: number
  back_x: number
  spine_x: number
  front_x: number
  safe_inset: number
  spine_safe_inset: number
  spine_text_allowed: boolean
  exact_platform_formula: boolean
  authority: string
  authority_url: string
  notes: string[]
}

type ValidationIssue = {
  level: 'error' | 'warning' | 'info'
  code: string
  message: string
}

type ValidationResult = {
  valid: boolean
  geometry: CoverGeometry
  issues: ValidationIssue[]
}

type CoverArtifact = {
  format: 'pdf' | 'jpg' | 'png'
  filename: string
  relative_path: string
  bytes: number
  width: number
  height: number
  units: 'in' | 'px'
}

type ExportResult = {
  export_id: string
  platform: CoverPlatform
  geometry: CoverGeometry
  validation: ValidationResult
  artifacts: CoverArtifact[]
}

type AssetResult = {
  relative_path: string
  filename: string
  width_px: number
  height_px: number
  format: string
  bytes: number
}

type Props = {
  apiBase: string
  slug: string
  projectName: string
  disabled: boolean
}

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

function platformLabel(platform: CoverPlatform) {
  return {
    kdp_paperback: 'KDP Paperback',
    ingramspark: 'IngramSpark / Template',
    custom_print: 'Custom Print',
    kdp_ebook: 'KDP eBook',
  }[platform]
}

function cssFont(font: FontFamily) {
  if (font === 'Helvetica') return 'Arial, Helvetica, sans-serif'
  if (font === 'Courier') return 'Courier New, monospace'
  return 'Georgia, Times New Roman, serif'
}

function humanBytes(value: number) {
  if (value < 1024 * 1024) return `${Math.max(1, Math.round(value / 1024)).toLocaleString()} KB`
  return `${(value / (1024 * 1024)).toFixed(1)} MB`
}

export default function CoverStudioPanel({ apiBase, slug, projectName, disabled }: Props) {
  const [profile, setProfile] = useState<CoverProfile | null>(null)
  const [geometry, setGeometry] = useState<CoverGeometry | null>(null)
  const [validation, setValidation] = useState<ValidationResult | null>(null)
  const [result, setResult] = useState<ExportResult | null>(null)
  const [artwork, setArtwork] = useState<AssetResult | null>(null)
  const [barcode, setBarcode] = useState<AssetResult | null>(null)
  const [showGuides, setShowGuides] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!slug) return
    setError('')
    void jsonRequest<CoverProfile>(`${apiBase}/projects/${slug}/cover/profile`)
      .then((loaded) => setProfile({ ...loaded, title: loaded.title === 'Untitled' ? projectName : loaded.title }))
      .catch((cause) => setError((cause as Error).message))
  }, [apiBase, slug, projectName])

  useEffect(() => {
    if (!profile || !slug) return
    const timer = window.setTimeout(() => {
      void Promise.all([
        jsonRequest<CoverGeometry>(`${apiBase}/projects/${slug}/cover/geometry`, {
          method: 'POST',
          body: JSON.stringify(profile),
        }),
        jsonRequest<ValidationResult>(`${apiBase}/projects/${slug}/cover/validate`, {
          method: 'POST',
          body: JSON.stringify(profile),
        }),
      ])
        .then(([nextGeometry, nextValidation]) => {
          setGeometry(nextGeometry)
          setValidation(nextValidation)
        })
        .catch((cause) => setError((cause as Error).message))
    }, 250)
    return () => window.clearTimeout(timer)
  }, [apiBase, slug, profile])

  const previewStyle = useMemo(() => {
    if (!profile || !geometry) return undefined
    if (profile.platform === 'kdp_ebook') {
      return { aspectRatio: `${profile.ebook_width_px} / ${profile.ebook_height_px}` }
    }
    return { aspectRatio: `${geometry.cover_width} / ${geometry.cover_height}` }
  }, [geometry, profile])

  const spinePercent = useMemo(() => {
    if (!geometry || profile?.platform === 'kdp_ebook') return 0
    return Math.max(0.8, (geometry.spine_width / geometry.cover_width) * 100)
  }, [geometry, profile?.platform])

  async function saveProfile() {
    if (!profile || busy) return
    setBusy(true)
    setError('')
    try {
      const saved = await jsonRequest<CoverProfile>(`${apiBase}/projects/${slug}/cover/profile`, {
        method: 'PUT',
        body: JSON.stringify(profile),
      })
      setProfile(saved)
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function uploadAsset(file: File, kind: 'artwork' | 'barcode') {
    setBusy(true)
    setError('')
    try {
      const form = new FormData()
      form.append('file', file)
      const response = await fetch(`${apiBase}/projects/${slug}/cover/assets`, { method: 'POST', body: form })
      if (!response.ok) {
        const body = await response.json().catch(() => ({}))
        throw new Error(body.detail || `${response.status} ${response.statusText}`)
      }
      const asset = (await response.json()) as AssetResult
      if (kind === 'artwork') {
        setArtwork(asset)
        setProfile((current) => current ? { ...current, artwork_path: asset.relative_path } : current)
      } else {
        setBarcode(asset)
        setProfile((current) => current ? { ...current, barcode_path: asset.relative_path, barcode_mode: 'custom' } : current)
      }
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function exportCover() {
    if (!profile || busy) return
    setBusy(true)
    setError('')
    try {
      const output = await jsonRequest<ExportResult>(`${apiBase}/projects/${slug}/cover/export`, {
        method: 'POST',
        body: JSON.stringify(profile),
      })
      setResult(output)
      setGeometry(output.geometry)
      setValidation(output.validation)
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  if (!profile) {
    return (
      <details className="authoring-panel cover-studio-panel" open>
        <summary>Cover Studio <small>Loading…</small></summary>
        <div className="authoring-panel-body">{error && <small className="panel-error">{error}</small>}</div>
      </details>
    )
  }

  const printMode = profile.platform !== 'kdp_ebook'
  const frontStyle = {
    backgroundColor: profile.front_overlay_color,
    color: profile.title_color,
    fontFamily: cssFont(profile.title_font),
  }
  const backStyle = {
    backgroundColor: profile.back_overlay_color,
    color: profile.body_color,
    fontFamily: cssFont(profile.body_font),
  }

  return (
    <details className="authoring-panel cover-studio-panel" open>
      <summary>
        Cover Studio <small>{platformLabel(profile.platform)}</small>
      </summary>
      <div className="authoring-panel-body cover-studio-body">
        <div className="cover-platform-row">
          <label>
            Output target
            <select value={profile.platform} onChange={(event) => setProfile({ ...profile, platform: event.target.value as CoverPlatform })} disabled={disabled || busy}>
              <option value="kdp_paperback">KDP Paperback</option>
              <option value="kdp_ebook">KDP eBook</option>
              <option value="ingramspark">IngramSpark / official template</option>
              <option value="custom_print">Custom print wrap</option>
            </select>
          </label>
          <label className="cover-guide-toggle">
            <input type="checkbox" checked={showGuides} onChange={(event) => setShowGuides(event.target.checked)} />
            Show guides
          </label>
        </div>

        <div className={`cover-preview-shell ${showGuides ? 'guides-on' : ''}`}>
          <div className={`cover-preview ${printMode ? 'cover-preview-print' : 'cover-preview-ebook'}`} style={{ ...previewStyle, backgroundColor: profile.background_color }}>
            {profile.artwork_path && (
              <div className={`cover-art-placeholder ${profile.artwork_mode === 'full_wrap' ? 'full-wrap-art' : 'front-art'}`}>
                <span>Artwork loaded</span>
                <small>{artwork ? `${artwork.width_px} × ${artwork.height_px}px` : profile.artwork_path.split('/').at(-1)}</small>
              </div>
            )}
            {printMode ? (
              <>
                <section className="cover-face cover-back" style={{ ...backStyle, width: `calc((100% - ${spinePercent}%) / 2)` }}>
                  <div className="cover-safe-box">
                    <p>{profile.back_blurb || 'Back-cover blurb'}</p>
                    {profile.imprint && <small>{profile.imprint}</small>}
                    {profile.barcode_mode !== 'none' && <span className="cover-barcode-box">{profile.barcode_mode === 'custom' ? 'BARCODE' : 'KDP BARCODE CLEARANCE'}</span>}
                  </div>
                </section>
                <section className="cover-spine" style={{ width: `${spinePercent}%`, backgroundColor: profile.spine_color }}>
                  {profile.spine_text && <span>{profile.spine_text}</span>}
                </section>
                <section className="cover-face cover-front" style={{ ...frontStyle, width: `calc((100% - ${spinePercent}%) / 2)` }}>
                  <div className="cover-safe-box" style={{ textAlign: profile.title_align }}>
                    <div>
                      <h3 style={{ color: profile.title_color }}>{profile.title}</h3>
                      {profile.subtitle && <p className="cover-subtitle" style={{ color: profile.subtitle_color }}>{profile.subtitle}</p>}
                    </div>
                    <strong style={{ color: profile.author_color }}>{profile.author || 'Author / pen name'}</strong>
                  </div>
                </section>
              </>
            ) : (
              <section className="cover-face cover-front ebook-face" style={frontStyle}>
                <div className="cover-safe-box" style={{ textAlign: profile.title_align }}>
                  <div>
                    <h3 style={{ color: profile.title_color }}>{profile.title}</h3>
                    {profile.subtitle && <p className="cover-subtitle" style={{ color: profile.subtitle_color }}>{profile.subtitle}</p>}
                  </div>
                  <strong style={{ color: profile.author_color }}>{profile.author || 'Author / pen name'}</strong>
                </div>
              </section>
            )}
          </div>
        </div>

        {geometry && (
          <div className="cover-geometry-strip">
            {printMode ? (
              <>
                <span><b>{geometry.cover_width.toFixed(3)} × {geometry.cover_height.toFixed(3)} in</b> full wrap</span>
                <span><b>{geometry.spine_width.toFixed(3)} in</b> spine</span>
                <span><b>{geometry.bleed.toFixed(3)} in</b> bleed</span>
              </>
            ) : (
              <>
                <span><b>{profile.ebook_width_px} × {profile.ebook_height_px}px</b> canvas</span>
                <span><b>{(profile.ebook_height_px / profile.ebook_width_px).toFixed(2)}:1</b> ratio</span>
              </>
            )}
          </div>
        )}

        <div className="cover-form-grid">
          <label>Title<input value={profile.title} onChange={(event) => setProfile({ ...profile, title: event.target.value })} disabled={disabled || busy} /></label>
          <label>Subtitle<input value={profile.subtitle} onChange={(event) => setProfile({ ...profile, subtitle: event.target.value })} disabled={disabled || busy} /></label>
          <label>Author / pen name<input value={profile.author} onChange={(event) => setProfile({ ...profile, author: event.target.value })} disabled={disabled || busy} /></label>
          <label>Imprint<input value={profile.imprint} onChange={(event) => setProfile({ ...profile, imprint: event.target.value })} disabled={disabled || busy} /></label>
          {printMode && <label className="cover-wide-field">Back-cover blurb<textarea rows={5} value={profile.back_blurb} onChange={(event) => setProfile({ ...profile, back_blurb: event.target.value })} disabled={disabled || busy} /></label>}
          {printMode && <label>Spine text<input value={profile.spine_text} onChange={(event) => setProfile({ ...profile, spine_text: event.target.value })} placeholder="Usually title · author" disabled={disabled || busy} /></label>}
          {printMode && <label>ISBN<input value={profile.isbn} onChange={(event) => setProfile({ ...profile, isbn: event.target.value })} disabled={disabled || busy} /></label>}
        </div>

        {printMode ? (
          <div className="cover-form-grid cover-spec-grid">
            <label>Trim width (in)<input type="number" min="4" max="8.5" step="0.125" value={profile.trim_width} onChange={(event) => setProfile({ ...profile, trim_width: Number(event.target.value) })} /></label>
            <label>Trim height (in)<input type="number" min="6" max="11.7" step="0.125" value={profile.trim_height} onChange={(event) => setProfile({ ...profile, trim_height: Number(event.target.value) })} /></label>
            <label>Final page count<input type="number" min="1" max="2000" value={profile.page_count} onChange={(event) => setProfile({ ...profile, page_count: Number(event.target.value) })} /></label>
            {profile.platform === 'kdp_paperback' ? (
              <label>Interior / paper<select value={profile.paper_type} onChange={(event) => setProfile({ ...profile, paper_type: event.target.value as PaperType })}>
                <option value="white_bw">Black &amp; white · white paper</option>
                <option value="cream_bw">Black &amp; white · cream paper</option>
                <option value="premium_color">Premium color</option>
                <option value="standard_color">Standard color</option>
              </select></label>
            ) : (
              <label>Template spine width (in)<input type="number" min="0" max="5" step="0.001" value={profile.manual_spine_width} onChange={(event) => setProfile({ ...profile, manual_spine_width: Number(event.target.value) })} /></label>
            )}
            {profile.platform === 'custom_print' && <label>Bleed (in)<input type="number" min="0" max="0.5" step="0.001" value={profile.bleed} onChange={(event) => setProfile({ ...profile, bleed: Number(event.target.value) })} /></label>}
            <label>Type-safe inset (in)<input type="number" min="0" max="1" step="0.025" value={profile.safe_inset} onChange={(event) => setProfile({ ...profile, safe_inset: Number(event.target.value) })} /></label>
          </div>
        ) : (
          <div className="cover-form-grid cover-spec-grid">
            <label>Width (px)<input type="number" min="625" max="10000" value={profile.ebook_width_px} onChange={(event) => setProfile({ ...profile, ebook_width_px: Number(event.target.value) })} /></label>
            <label>Height (px)<input type="number" min="1000" max="10000" value={profile.ebook_height_px} onChange={(event) => setProfile({ ...profile, ebook_height_px: Number(event.target.value) })} /></label>
          </div>
        )}

        <details className="cover-subpanel">
          <summary>Typography &amp; color</summary>
          <div className="cover-form-grid">
            <label>Title font<select value={profile.title_font} onChange={(event) => setProfile({ ...profile, title_font: event.target.value as FontFamily })}><option>Times</option><option>Helvetica</option><option>Courier</option></select></label>
            <label>Body font<select value={profile.body_font} onChange={(event) => setProfile({ ...profile, body_font: event.target.value as FontFamily })}><option>Times</option><option>Helvetica</option><option>Courier</option></select></label>
            <label>Title size<input type="number" min="7" max="120" value={profile.title_size} onChange={(event) => setProfile({ ...profile, title_size: Number(event.target.value) })} /></label>
            <label>Subtitle size<input type="number" min="7" max="72" value={profile.subtitle_size} onChange={(event) => setProfile({ ...profile, subtitle_size: Number(event.target.value) })} /></label>
            <label>Author size<input type="number" min="7" max="72" value={profile.author_size} onChange={(event) => setProfile({ ...profile, author_size: Number(event.target.value) })} /></label>
            <label>Blurb size<input type="number" min="7" max="30" step="0.5" value={profile.body_size} onChange={(event) => setProfile({ ...profile, body_size: Number(event.target.value) })} /></label>
            <label>Spine size<input type="number" min="7" max="30" step="0.5" value={profile.spine_size} onChange={(event) => setProfile({ ...profile, spine_size: Number(event.target.value) })} /></label>
            <label>Title alignment<select value={profile.title_align} onChange={(event) => setProfile({ ...profile, title_align: event.target.value as TextAlign })}><option value="left">Left</option><option value="center">Center</option><option value="right">Right</option></select></label>
            <label>Background<input type="color" value={profile.background_color} onChange={(event) => setProfile({ ...profile, background_color: event.target.value })} /></label>
            <label>Front panel<input type="color" value={profile.front_overlay_color} onChange={(event) => setProfile({ ...profile, front_overlay_color: event.target.value })} /></label>
            <label>Back panel<input type="color" value={profile.back_overlay_color} onChange={(event) => setProfile({ ...profile, back_overlay_color: event.target.value })} /></label>
            <label>Spine<input type="color" value={profile.spine_color} onChange={(event) => setProfile({ ...profile, spine_color: event.target.value })} /></label>
            <label>Title text<input type="color" value={profile.title_color} onChange={(event) => setProfile({ ...profile, title_color: event.target.value })} /></label>
            <label>Body text<input type="color" value={profile.body_color} onChange={(event) => setProfile({ ...profile, body_color: event.target.value })} /></label>
          </div>
        </details>

        <details className="cover-subpanel" open>
          <summary>Artwork &amp; barcode</summary>
          <div className="cover-asset-grid">
            <label className="cover-upload">Artwork<input type="file" accept="image/png,image/jpeg,image/tiff,image/webp" onChange={(event) => { const file = event.target.files?.[0]; if (file) void uploadAsset(file, 'artwork') }} disabled={disabled || busy} /></label>
            {printMode && <label>Artwork placement<select value={profile.artwork_mode} onChange={(event) => setProfile({ ...profile, artwork_mode: event.target.value as ArtworkMode })}><option value="front">Front cover only</option><option value="full_wrap">Full wrap</option></select></label>}
            {printMode && <label>Barcode<select value={profile.barcode_mode} onChange={(event) => setProfile({ ...profile, barcode_mode: event.target.value as BarcodeMode })}><option value="platform">Reserve for platform barcode</option><option value="custom">Use uploaded barcode</option><option value="none">No reserved box</option></select></label>}
            {printMode && profile.barcode_mode === 'custom' && <label className="cover-upload">Barcode image<input type="file" accept="image/png,image/jpeg,image/tiff,image/webp" onChange={(event) => { const file = event.target.files?.[0]; if (file) void uploadAsset(file, 'barcode') }} disabled={disabled || busy} /></label>}
          </div>
          {profile.artwork_path && <small className="panel-help">Artwork: {artwork?.filename || profile.artwork_path}</small>}
          {profile.barcode_path && profile.barcode_mode === 'custom' && <small className="panel-help">Barcode: {barcode?.filename || profile.barcode_path}</small>}
        </details>

        {validation && (
          <div className={`cover-validation ${validation.valid ? 'valid' : 'invalid'}`}>
            <strong>{validation.valid ? 'Preflight passes blocking checks' : 'Fix blocking cover issues before export'}</strong>
            {validation.issues.length === 0 && <small>No cover preflight issues found.</small>}
            {validation.issues.map((issue) => <small key={`${issue.code}-${issue.message}`} className={`cover-issue issue-${issue.level}`}><b>{issue.level.toUpperCase()}</b> {issue.message}</small>)}
          </div>
        )}

        {geometry && (
          <div className="cover-authority">
            <span>{geometry.exact_platform_formula ? 'Calculated from current platform rules' : 'Template/user measurement required'}</span>
            {geometry.authority_url ? <a href={geometry.authority_url} target="_blank" rel="noreferrer">{geometry.authority}</a> : <small>{geometry.authority}</small>}
          </div>
        )}

        <div className="cover-actions">
          <button type="button" onClick={() => void saveProfile()} disabled={disabled || busy}>{busy ? 'Working…' : 'Save cover project'}</button>
          <button type="button" className="primary" onClick={() => void exportCover()} disabled={disabled || busy || validation?.valid === false}>{busy ? 'Building…' : printMode ? 'Build print-ready cover PDF' : 'Build eBook cover'}</button>
        </div>

        {result && (
          <div className="publish-result cover-export-result">
            <strong>Cover export ready</strong>
            {result.artifacts.map((artifact) => {
              const downloadUrl = `${apiBase}/projects/${slug}/exports/download?path=${encodeURIComponent(artifact.relative_path)}`
              return <a key={artifact.relative_path} href={downloadUrl} download={artifact.filename}>Download {artifact.filename} <small>{humanBytes(artifact.bytes)} · {artifact.width}{artifact.units === 'in' ? ' × ' : '×'}{artifact.height} {artifact.units}</small></a>
            })}
          </div>
        )}

        {error && <small className="panel-error">{error}</small>}
      </div>
    </details>
  )
}
