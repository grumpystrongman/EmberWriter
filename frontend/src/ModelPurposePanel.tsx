import { MODEL_PURPOSES, installedModelForPurpose, type ModelPurposeKey } from './model-purpose'

type Props = {
  apiBase: string
  baseUrl: string
  models: string[]
  currentModel: string
  recommendedKey: ModelPurposeKey
  autoPick: boolean
  busy: boolean
  onAutoPickChange: (value: boolean) => void
  onChooseModel: (model: string) => void
  onModelsChanged: (models: string[]) => void
  onStatus: (message: string) => void
}

async function installModel(apiBase: string, baseUrl: string, model: string): Promise<string[]> {
  const response = await fetch(`${apiBase}/models/pull`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ base_url: baseUrl, model }),
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || `${response.status} ${response.statusText}`)
  }
  const body = await response.json() as { models?: string[] }
  return body.models || []
}

export default function ModelPurposePanel({
  apiBase,
  baseUrl,
  models,
  currentModel,
  recommendedKey,
  autoPick,
  busy,
  onAutoPickChange,
  onChooseModel,
  onModelsChanged,
  onStatus,
}: Props) {
  async function install(key: ModelPurposeKey) {
    const profile = MODEL_PURPOSES.find((item) => item.key === key)
    if (!profile) return
    const model = profile.candidates[0]
    onStatus(`Installing ${profile.title} model · ${model}…`)
    try {
      const next = await installModel(apiBase, baseUrl, model)
      onModelsChanged(next)
      onChooseModel(model)
      onStatus(`${profile.title} model installed and selected.`)
    } catch (error) {
      onStatus(`Model install failed: ${(error as Error).message}`)
    }
  }

  return (
    <div className="model-purpose-panel">
      <div className="model-purpose-heading">
        <div>
          <strong>Choose the model for the job</strong>
          <small>EmberWriter uses different models for prose, mature relationship fiction, and story-room reasoning.</small>
        </div>
        <label>
          <input type="checkbox" checked={autoPick} onChange={(event) => onAutoPickChange(event.target.checked)} />
          Auto-pick the best installed model
        </label>
      </div>

      <div className="model-purpose-grid">
        {MODEL_PURPOSES.map((profile) => {
          const installed = installedModelForPurpose(profile.key, models)
          const active = Boolean(installed && installed === currentModel)
          const recommended = profile.key === recommendedKey
          return (
            <article key={profile.key} className={`model-purpose-card${active ? ' active' : ''}${recommended ? ' recommended' : ''}`}>
              <div className="model-purpose-card-head">
                <strong>{profile.title}</strong>
                {recommended && <span>Recommended now</span>}
              </div>
              <small>{profile.short}</small>
              <p>{profile.why}</p>
              <dl>
                <div><dt>Best for</dt><dd>{profile.bestFor}</dd></div>
                <div><dt>Not ideal for</dt><dd>{profile.avoidFor}</dd></div>
              </dl>
              {installed ? (
                <button type="button" disabled={busy || active} onClick={() => onChooseModel(installed)}>
                  {active ? `Using ${installed}` : `Use ${installed}`}
                </button>
              ) : (
                <button type="button" disabled={busy} onClick={() => void install(profile.key)}>
                  Install recommended model
                </button>
              )}
            </article>
          )
        })}
      </div>
    </div>
  )
}
