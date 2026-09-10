import { useEffect, useMemo, useState } from 'react'

import './chemistry.css'

export type ChemistryMilestone = {
  label: string
  consequence: string
  source_path: string
  chapter_order: number
}

export type ChemistryProfile = {
  participants: string[]
  dynamic_summary: string
  attraction_language: string
  verbal_rhythm: string
  initiation_style: string
  response_style: string
  power_dynamic: string
  trust_state: string
  vulnerability_pressure: string
  established_patterns: string[]
  boundaries: string[]
  signature_elements: string[]
  lore_resonance: string[]
  aftermath_needs: string[]
  next_escalations: string[]
  avoidances: string[]
  milestones: ChemistryMilestone[]
  author_notes: string
  updated_at: string
}

export type AftermathRelationshipUpdate = {
  participants: string[]
  dynamic_summary: string
  trust_state: string
  vulnerability_pressure: string
  add_established_patterns: string[]
  add_signature_elements: string[]
  add_lore_resonance: string[]
  add_aftermath_needs: string[]
  next_escalations: string[]
  milestone_label: string
  milestone_consequence: string
}

export type AftermathProposal = {
  summary: string
  participants: string[]
  source_path: string
  chapter_order: number
  relationship_updates: AftermathRelationshipUpdate[]
  character_aftermath: string[]
  open_questions: string[]
}

type Props = {
  characterNames: string[]
  profiles: ChemistryProfile[]
  disabled: boolean
  canAnalyzeScene: boolean
  onInfer: (participants: string[], authorDirection: string) => Promise<ChemistryProfile | null>
  onSave: (profile: ChemistryProfile) => Promise<ChemistryProfile | null>
  onAnalyzeAftermath: (participants: string[]) => Promise<AftermathProposal | null>
  onApplyAftermath: (proposal: AftermathProposal) => Promise<boolean>
}

const fields: Array<[keyof ChemistryProfile, string]> = [
  ['dynamic_summary', 'Dynamic'],
  ['attraction_language', 'Attraction language'],
  ['verbal_rhythm', 'Verbal rhythm'],
  ['initiation_style', 'Initiation style'],
  ['response_style', 'Response style'],
  ['power_dynamic', 'Power dynamic'],
  ['trust_state', 'Trust state'],
  ['vulnerability_pressure', 'Vulnerability pressure'],
]

const listFields: Array<[keyof ChemistryProfile, string]> = [
  ['established_patterns', 'Established patterns'],
  ['boundaries', 'Author-controlled boundaries'],
  ['signature_elements', 'Signature elements'],
  ['lore_resonance', 'Lore / magic resonance'],
  ['aftermath_needs', 'Aftermath needs'],
  ['next_escalations', 'Next meaningful escalations'],
  ['avoidances', 'Avoid'],
]

function keyFor(names: string[]) {
  return [...names].map((name) => name.toLocaleLowerCase()).sort().join('|')
}

function emptyProfile(participants: string[]): ChemistryProfile {
  return {
    participants,
    dynamic_summary: '',
    attraction_language: '',
    verbal_rhythm: '',
    initiation_style: '',
    response_style: '',
    power_dynamic: '',
    trust_state: '',
    vulnerability_pressure: '',
    established_patterns: [],
    boundaries: [],
    signature_elements: [],
    lore_resonance: [],
    aftermath_needs: [],
    next_escalations: [],
    avoidances: [],
    milestones: [],
    author_notes: '',
    updated_at: '',
  }
}

export default function ChemistryPanel({
  characterNames,
  profiles,
  disabled,
  canAnalyzeScene,
  onInfer,
  onSave,
  onAnalyzeAftermath,
  onApplyAftermath,
}: Props) {
  const [selected, setSelected] = useState<string[]>([])
  const [draft, setDraft] = useState<ChemistryProfile | null>(null)
  const [direction, setDirection] = useState('')
  const [aftermath, setAftermath] = useState<AftermathProposal | null>(null)

  const selectedKey = keyFor(selected)
  const matching = useMemo(
    () => profiles.find((profile) => keyFor(profile.participants) === selectedKey) || null,
    [profiles, selectedKey],
  )

  useEffect(() => {
    if (selected.length < 2) {
      setDraft(null)
      setAftermath(null)
      return
    }
    setDraft(matching ? structuredClone(matching) : emptyProfile(selected))
    setAftermath(null)
  }, [matching, selectedKey])

  function toggleCharacter(name: string) {
    setSelected((current) => {
      if (current.includes(name)) return current.filter((item) => item !== name)
      if (current.length >= 6) return current
      return [...current, name]
    })
  }

  function patch(field: keyof ChemistryProfile, value: string | string[]) {
    if (!draft) return
    setDraft({ ...draft, [field]: value })
  }

  async function infer() {
    if (selected.length < 2) return
    const result = await onInfer(selected, direction.trim())
    if (result) setDraft(result)
  }

  async function save() {
    if (!draft) return
    const result = await onSave({ ...draft, participants: selected })
    if (result) setDraft(result)
  }

  async function analyze() {
    if (selected.length < 2) return
    setAftermath(await onAnalyzeAftermath(selected))
  }

  return (
    <details className="chemistry-panel">
      <summary>
        <span>Relationship Chemistry</span>
        <small>{profiles.length} profile{profiles.length === 1 ? '' : 's'}</small>
      </summary>

      <p className="chemistry-caption">
        Pairing-specific voice, trust, vulnerability, milestones, boundaries, and escalation. Boundaries are author-controlled; Aftermath never edits them.
      </p>

      <div className="chemistry-characters">
        {characterNames.map((name) => (
          <button
            type="button"
            key={name}
            className={selected.includes(name) ? 'active' : ''}
            onClick={() => toggleCharacter(name)}
          >
            {name}
          </button>
        ))}
      </div>

      {selected.length < 2 && <small className="chemistry-hint">Choose 2–6 characters to inspect a relationship or group dynamic.</small>}

      {draft && (
        <div className="chemistry-editor">
          <div className="chemistry-pair-title">
            <strong>{selected.join(' + ')}</strong>
            <span>{matching ? 'saved profile' : 'new profile'}</span>
          </div>

          <label>AI direction <small>optional; does not overwrite explicit boundaries unless you save edits</small></label>
          <textarea
            value={direction}
            onChange={(event) => setDirection(event.target.value)}
            placeholder="What matters about this pairing? What kind of chemistry should the book preserve?"
          />
          <button type="button" disabled={disabled} onClick={() => void infer()}>Infer from canon + manuscript</button>

          {fields.map(([field, label]) => (
            <label key={field}>
              {label}
              <textarea
                value={String(draft[field] || '')}
                onChange={(event) => patch(field, event.target.value)}
              />
            </label>
          ))}

          {listFields.map(([field, label]) => (
            <label key={field}>
              {label} <small>one per line</small>
              <textarea
                value={(draft[field] as string[]).join('\n')}
                onChange={(event) => patch(field, event.target.value.split('\n').map((item) => item.trim()).filter(Boolean))}
              />
            </label>
          ))}

          <label>
            Author notes
            <textarea value={draft.author_notes} onChange={(event) => patch('author_notes', event.target.value)} />
          </label>

          {draft.milestones.length > 0 && (
            <div className="chemistry-milestones">
              <strong>Milestones</strong>
              {draft.milestones.slice().reverse().slice(0, 8).map((item, index) => (
                <div key={`${item.label}-${index}`}>
                  <span>{item.label}</span>
                  <p>{item.consequence}</p>
                  {item.source_path && <small>{item.source_path}</small>}
                </div>
              ))}
            </div>
          )}

          <button type="button" className="quiet" disabled={disabled} onClick={() => void save()}>Save chemistry profile</button>

          <div className="aftermath-section">
            <strong>Aftermath</strong>
            <p>Analyze the current selection (or chapter) for relationship changes, then review the proposal before applying it.</p>
            <button type="button" disabled={disabled || !canAnalyzeScene} onClick={() => void analyze()}>Analyze current scene aftermath</button>
          </div>

          {aftermath && (
            <div className="aftermath-card">
              <strong>Proposed state changes</strong>
              <p>{aftermath.summary}</p>
              {aftermath.relationship_updates.map((update, index) => (
                <div className="aftermath-update" key={`${keyFor(update.participants)}-${index}`}>
                  <span>{update.participants.join(' + ')}</span>
                  {update.dynamic_summary && <p>{update.dynamic_summary}</p>}
                  {update.trust_state && <small>Trust: {update.trust_state}</small>}
                  {update.milestone_label && <small>Milestone: {update.milestone_label} — {update.milestone_consequence}</small>}
                </div>
              ))}
              {aftermath.character_aftermath.length > 0 && <small>Character aftermath: {aftermath.character_aftermath.join(' · ')}</small>}
              {aftermath.open_questions.length > 0 && <small>Still open: {aftermath.open_questions.join(' · ')}</small>}
              <button type="button" className="apply-aftermath" disabled={disabled} onClick={() => void onApplyAftermath(aftermath)}>
                Apply reviewed changes
              </button>
            </div>
          )}
        </div>
      )}
    </details>
  )
}
