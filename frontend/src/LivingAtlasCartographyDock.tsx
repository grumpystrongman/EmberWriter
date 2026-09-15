import { useState } from 'react'

import type { AtlasCartographicFeature } from './story-atlas-types'

type Props = {
  features: AtlasCartographicFeature[]
  selectedFeature: AtlasCartographicFeature | null
  busy: boolean
  showCartography: boolean
  editCartography: boolean
  onShowCartography: (value: boolean) => void
  onEditCartography: (value: boolean) => void
  onSelectFeature: (id: string) => void
  onUpdateFeature: (id: string, patch: Partial<AtlasCartographicFeature>) => void
  onDeleteFeature: (id: string) => void
  onSuggest: (prompt: string) => void
  onImport: (geojson: string, sourceName: string) => void
  onGenerate: (seed: number, continents: number, detail: number) => void
  onAssembleHistorical: (query: string) => void
}

export default function LivingAtlasCartographyDock(props: Props) {
  const [open, setOpen] = useState(false)
  const [historicalQuery, setHistoricalQuery] = useState('New Harmony, Indiana, 1820')
  const [prompt, setPrompt] = useState('Read the manuscript and suggest coastlines, rivers, roads, forests, walls, districts and structures that are spatially supported by the text.')
  const [geojson, setGeojson] = useState('')
  const [sourceName, setSourceName] = useState('Real-world GeoJSON')
  const [seed, setSeed] = useState(42)
  const [continents, setContinents] = useState(1)
  const [detail, setDetail] = useState(3)

  if (!open) return <button type="button" className="atlas-iii-launch" onClick={() => setOpen(true)}>✦ Cartography</button>

  return <section className="atlas-iii-dock">
    <header><div><b>Living Atlas III</b><span>Persisted, editable cartography</span></div><button type="button" onClick={() => setOpen(false)}>×</button></header>
    <div className="atlas-iii-scroll">
      <div className="atlas-iii-toggle-row">
        <label><input type="checkbox" checked={props.showCartography} onChange={(event) => props.onShowCartography(event.target.checked)} /> Show features</label>
        <label><input type="checkbox" checked={props.editCartography} onChange={(event) => props.onEditCartography(event.target.checked)} /> Edit vertices</label>
      </div>

      <article className="atlas-iii-card atlas-historical-assembler">
        <b>Build a real place in a historical year</b>
        <p>Type a place and year. Ember resolves the location, imports present-day GIS as a clearly marked reference layer, and searches historical map catalogs around that era. Historical sources are saved with the project for provenance.</p>
        <input
          value={historicalQuery}
          onChange={(event) => setHistoricalQuery(event.target.value)}
          placeholder="New Harmony, Indiana, 1820"
          onKeyDown={(event) => {
            if (event.key === 'Enter' && historicalQuery.trim() && !props.busy) props.onAssembleHistorical(historicalQuery)
          }}
        />
        <button type="button" disabled={props.busy || !historicalQuery.trim()} onClick={() => props.onAssembleHistorical(historicalQuery)}>Assemble historical atlas</button>
        <small>Sources currently include OpenStreetMap/Nominatim, Library of Congress map records, and USGS historical topographic products where the requested year is covered.</small>
      </article>

      <article className="atlas-iii-card">
        <b>Read manuscript → suggest geography</b>
        <p>Ember reads project text and proposes geometry as <em>suggested</em> cartography. Nothing becomes canon automatically.</p>
        <textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} rows={4} />
        <button type="button" disabled={props.busy} onClick={() => props.onSuggest(prompt)}>Analyze manuscript geography</button>
      </article>

      <article className="atlas-iii-card">
        <b>Generate classic fantasy continent</b>
        <p>Seeded procedural landmasses, mountain spines, rivers, forests and roads. The result is original editable geometry rather than a copy of an existing published map.</p>
        <div className="atlas-iii-grid">
          <label>Seed<input type="number" value={seed} min={0} max={2147483647} onChange={(event) => setSeed(Number(event.target.value))} /></label>
          <label>Continents<input type="number" value={continents} min={1} max={5} onChange={(event) => setContinents(Number(event.target.value))} /></label>
          <label>Detail<input type="range" value={detail} min={1} max={5} onChange={(event) => setDetail(Number(event.target.value))} /></label>
        </div>
        <button type="button" disabled={props.busy} onClick={() => props.onGenerate(seed, continents, detail)}>Generate geography</button>
      </article>

      <article className="atlas-iii-card">
        <b>Ingest real geography</b>
        <p>Paste GeoJSON from GIS/OpenStreetMap/export tools. Longitude/latitude is projected into the current story-map scope and retained as inferred source geometry.</p>
        <input value={sourceName} onChange={(event) => setSourceName(event.target.value)} placeholder="Source / dataset name" />
        <textarea value={geojson} onChange={(event) => setGeojson(event.target.value)} rows={5} placeholder='{"type":"FeatureCollection","features":[...]}' />
        <button type="button" disabled={props.busy || !geojson.trim()} onClick={() => props.onImport(geojson, sourceName)}>Import GeoJSON</button>
      </article>

      <article className="atlas-iii-card atlas-iii-features">
        <b>Features at this map level <span>{props.features.length}</span></b>
        <div className="atlas-iii-feature-list">
          {props.features.map((feature) => <button type="button" key={feature.id} className={props.selectedFeature?.id === feature.id ? 'active' : ''} onClick={() => props.onSelectFeature(feature.id)}>
            <i className={feature.canon_status} />
            <span><strong>{feature.name || feature.kind}</strong><small>{feature.kind} · {feature.geometry_type} · {feature.source}</small></span>
          </button>)}
          {!props.features.length && <p>No persisted cartographic features at this level yet.</p>}
        </div>
        {props.selectedFeature && <div className="atlas-iii-selected">
          <input value={props.selectedFeature.name} onChange={(event) => props.onUpdateFeature(props.selectedFeature!.id, { name: event.target.value })} />
          <div className="atlas-iii-selected-actions">
            <select value={props.selectedFeature.canon_status} onChange={(event) => props.onUpdateFeature(props.selectedFeature!.id, { canon_status: event.target.value as AtlasCartographicFeature['canon_status'] })}>
              <option value="suggested">Suggested</option><option value="inferred">Inferred</option><option value="canon">Canon</option>
            </select>
            <button type="button" onClick={() => props.onDeleteFeature(props.selectedFeature!.id)}>Delete</button>
          </div>
          <p>{props.editCartography ? 'Drag the orange vertex handles directly on the map to reshape this feature.' : 'Turn on Edit vertices to reshape this feature directly on the map.'}</p>
        </div>}
      </article>
    </div>
  </section>
}
