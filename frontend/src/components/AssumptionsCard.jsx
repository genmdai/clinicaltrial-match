import { useEffect, useState } from 'react'
import GapInput from './GapInput'
import { ChevronIcon, CloseIcon, PencilIcon, PlusIcon, ReadIcon } from './icons'
import './AssumptionsCard.css'

const STATUS_WORDS = ['positive', 'negative', 'unknown']
const OUTCOME_OPTIONS = [
  { value: '', label: 'Unknown' },
  { value: 'ongoing', label: 'Ongoing' },
  { value: 'progression', label: 'Progression' },
  { value: 'toxicity', label: 'Toxicity / stopped' },
]
const ECOG_OPTIONS = [
  { value: '', label: 'Unknown' },
  { value: '0', label: '0 — Fully active' },
  { value: '1', label: '1 — Light activity only' },
  { value: '2', label: '2 — Self-care only' },
  { value: '3', label: '3 — Limited self-care' },
  { value: '4', label: '4 — Completely disabled' },
]
const ECOG_SHORT = ['Fully active', 'Light activity only', 'Self-care only', 'Limited self-care', 'Completely disabled']

function subjectWord(profile) {
  if (profile.subject !== 'relative') return 'you'
  return profile.relation ? `your ${profile.relation}` : 'your family member'
}

function parseBiomarker(entry) {
  const parts = entry.trim().split(/\s+/)
  const last = parts[parts.length - 1]?.toLowerCase()
  if (parts.length > 1 && STATUS_WORDS.includes(last)) {
    return { marker: parts.slice(0, -1).join(' '), status: last }
  }
  return { marker: entry.trim(), status: 'unknown' }
}

function formatBiomarker({ marker, status }) {
  return `${marker} ${status}`.trim()
}

function outcomeLabel(value) {
  return OUTCOME_OPTIONS.find((o) => o.value === (value ?? ''))?.label ?? 'Unknown'
}

// A `required` gap (currently only an unresolved/missing diagnosis) is the one
// thing that genuinely blocks searching — everything else is worth asking but
// never worth a gate (CLAUDE.md P2/P3: an unknown ECOG is an honest UNKNOWN
// verdict, not a reason to stall the whole search).
function hasRequiredGap(profile) {
  return (profile.gaps ?? []).some((g) => g.required)
}

// The intake surface has exactly three states, and only ever shows one of
// them, which is what keeps it from reading as the same form twice:
//
//   asking   — a required gap is open. ONE question, nothing else. No fields,
//              no summary, no assumptions — there is nothing yet to confirm.
//   readout  — the default once searchable. A read-only summary of what was
//              understood, with provenance (inferred flags, the reasoning
//              behind each inference) — the evidence that a model read the
//              narrative, not a form the user has to fill.
//   editing  — the same card flipped into the full structured editor, opened
//              deliberately from "Edit". Never shown alongside the readout.
//
// Previously all three were stacked at once: the blocking question sat on top
// of a full empty form, and answering it re-rendered that same form with a
// button — two consecutive screens of near-identical data entry.
export default function AssumptionsCard({ profile, onResolveGap, onConfirm, searched, matching }) {
  const [draft, setDraft] = useState(profile)
  const [editing, setEditing] = useState(false)
  const [reasoningOpen, setReasoningOpen] = useState(false)

  useEffect(() => {
    setDraft(profile)
  }, [profile])

  const update = (field, value) => setDraft((d) => ({ ...d, [field]: value }))

  const blocking = hasRequiredGap(profile)
  const conditionGap = (profile.gaps ?? []).find((g) => g.required)
  const optionalGaps = (profile.gaps ?? []).filter((g) => !g.required)

  const biomarkerRows = (draft.biomarkers ?? []).map(parseBiomarker)
  const setBiomarkerRows = (rows) => update('biomarkers', rows.map(formatBiomarker).filter((s) => s.trim()))
  const priorTreatments = draft.prior_treatments ?? []
  const setPriorTreatments = (rows) => update('prior_treatments', rows)

  // ---- asking: one question, alone -----------------------------------------
  if (blocking && conditionGap) {
    return (
      <section className="intake intake--asking">
        <div className="intake-head">
          <span className="intake-mark" aria-hidden="true">
            <ReadIcon />
          </span>
          <h3 className="intake-ask">{conditionGap.label}</h3>
        </div>
        {conditionGap.example_quote && (
          <p className="intake-cited">You said “{conditionGap.example_quote}”</p>
        )}
        <GapInput
          gap={conditionGap}
          onAnswer={(text) => onResolveGap(conditionGap.gap_id, conditionGap.field, text)}
        />
        <p className="intake-note">
          That is all I need to start. Age, location and treatment history sharpen the results —
          you can add them on the next step.
        </p>
      </section>
    )
  }

  // ---- readout / editing ----------------------------------------------------
  const condition = draft.condition || draft.condition_raw
  const dirty = JSON.stringify(draft) !== JSON.stringify(profile)
  const showAction = !searched || dirty
  const actionLabel = matching ? 'Searching…' : searched ? 'Update and re-search' : 'Search trials'

  // `missing` reads as a sentence ("Not provided: age, location, ECOG …"), so
  // each fact carries its own prose form — lowercasing `label` blindly turns
  // ECOG into "ecog".
  const facts = [
    { key: 'age', label: 'Age', prose: 'age', value: draft.age != null ? `${draft.age}` : null },
    {
      key: 'sex',
      label: 'Sex',
      prose: 'sex',
      value: draft.sex ? draft.sex[0].toUpperCase() + draft.sex.slice(1) : null,
    },
    { key: 'location', label: 'Location', prose: 'location', value: draft.location_zip || null },
    {
      key: 'ecog',
      label: 'ECOG',
      prose: 'ECOG status',
      value: draft.ecog != null ? `${draft.ecog} — ${ECOG_SHORT[draft.ecog] ?? ''}`.trim() : null,
    },
    {
      key: 'lines',
      label: 'Prior lines',
      prose: 'prior treatment lines',
      value: draft.treatment_line != null ? `${draft.treatment_line}` : null,
    },
  ]
  const known = facts.filter((f) => f.value)
  const missing = facts.filter((f) => !f.value)

  return (
    <section className="intake">
      <div className="intake-head">
        <span className="intake-mark" aria-hidden="true">
          <ReadIcon />
        </span>
        <h3 className="intake-title">
          {editing ? 'Correct anything I got wrong' : `Here is what I understood about ${subjectWord(draft)}`}
        </h3>
        <button type="button" className="intake-edit" onClick={() => setEditing((v) => !v)}>
          {editing ? <ChevronIcon className="intake-edit-icon intake-edit-icon--down" /> : <PencilIcon className="intake-edit-icon" />}
          {editing ? 'Done' : 'Edit'}
        </button>
      </div>

      {editing ? (
        <div className="intake-form">
          <div className="intake-field-row">
            <label className="intake-field">
              <span>Age</span>
              <input
                type="number"
                value={draft.age ?? ''}
                placeholder="Unknown"
                onChange={(e) => update('age', e.target.value === '' ? null : Number(e.target.value))}
              />
            </label>
            <label className="intake-field">
              <span>Sex</span>
              <select value={draft.sex ?? ''} onChange={(e) => update('sex', e.target.value || null)}>
                <option value="">Unknown</option>
                <option value="female">Female</option>
                <option value="male">Male</option>
                <option value="other">Other</option>
              </select>
            </label>
          </div>

          <label className="intake-field">
            <span>Condition</span>
            <input
              type="text"
              value={draft.condition ?? draft.condition_raw ?? ''}
              onChange={(e) => update('condition', e.target.value)}
            />
          </label>

          <label className="intake-field">
            <span>Location</span>
            <input
              type="text"
              value={draft.location_zip ?? ''}
              onChange={(e) => update('location_zip', e.target.value)}
              placeholder="ZIP code, or city and country"
            />
          </label>

          <div className="intake-field-row">
            <label className="intake-field">
              <span>ECOG status</span>
              <select
                value={draft.ecog ?? ''}
                onChange={(e) => update('ecog', e.target.value === '' ? null : Number(e.target.value))}
              >
                {ECOG_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </label>
            <label className="intake-field">
              <span>Prior treatment lines</span>
              <input
                type="number"
                min="0"
                value={draft.treatment_line ?? ''}
                onChange={(e) => update('treatment_line', e.target.value === '' ? null : Number(e.target.value))}
                placeholder="Unknown"
              />
            </label>
          </div>

          <fieldset className="intake-group">
            <legend>Prior treatments</legend>
            {priorTreatments.map((pt, i) => (
              <div className="intake-row" key={i}>
                <input
                  type="text"
                  className="intake-row-main"
                  value={pt.raw_mention ?? ''}
                  placeholder="Drug or treatment name"
                  onChange={(e) => {
                    const next = [...priorTreatments]
                    next[i] = { ...pt, raw_mention: e.target.value }
                    setPriorTreatments(next)
                  }}
                />
                <select
                  className="intake-row-aside"
                  value={pt.outcome ?? ''}
                  onChange={(e) => {
                    const next = [...priorTreatments]
                    next[i] = { ...pt, outcome: e.target.value || null }
                    setPriorTreatments(next)
                  }}
                >
                  {OUTCOME_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
                <button
                  type="button"
                  className="intake-row-remove"
                  aria-label={`Remove ${pt.raw_mention || 'treatment'}`}
                  onClick={() => setPriorTreatments(priorTreatments.filter((_, j) => j !== i))}
                >
                  <CloseIcon />
                </button>
              </div>
            ))}
            <button
              type="button"
              className="intake-add"
              onClick={() => setPriorTreatments([...priorTreatments, { raw_mention: '', outcome: null, inferred: false, confidence: 'low' }])}
            >
              <PlusIcon className="intake-add-icon" />
              Add treatment
            </button>
          </fieldset>

          <fieldset className="intake-group">
            <legend>Biomarkers</legend>
            {biomarkerRows.map((row, i) => (
              <div className="intake-row" key={i}>
                <input
                  type="text"
                  className="intake-row-main"
                  value={row.marker}
                  placeholder="e.g. EGFR"
                  onChange={(e) => {
                    const next = [...biomarkerRows]
                    next[i] = { ...row, marker: e.target.value }
                    setBiomarkerRows(next)
                  }}
                />
                <select
                  className="intake-row-aside"
                  value={row.status}
                  onChange={(e) => {
                    const next = [...biomarkerRows]
                    next[i] = { ...row, status: e.target.value }
                    setBiomarkerRows(next)
                  }}
                >
                  <option value="unknown">Unknown</option>
                  <option value="positive">Positive</option>
                  <option value="negative">Negative</option>
                </select>
                <button
                  type="button"
                  className="intake-row-remove"
                  aria-label={`Remove ${row.marker || 'biomarker'}`}
                  onClick={() => setBiomarkerRows(biomarkerRows.filter((_, j) => j !== i))}
                >
                  <CloseIcon />
                </button>
              </div>
            ))}
            <button type="button" className="intake-add" onClick={() => setBiomarkerRows([...biomarkerRows, { marker: '', status: 'unknown' }])}>
              <PlusIcon className="intake-add-icon" />
              Add biomarker
            </button>
          </fieldset>

          <fieldset className="intake-group">
            <legend>Other conditions</legend>
            {(draft.comorbidities ?? []).length > 0 && (
              <div className="intake-chips">
                {(draft.comorbidities ?? []).map((c, i) => (
                  <span className="intake-chip" key={i}>
                    {c}
                    <button
                      type="button"
                      className="intake-chip-remove"
                      aria-label={`Remove ${c}`}
                      onClick={() => update('comorbidities', draft.comorbidities.filter((_, j) => j !== i))}
                    >
                      <CloseIcon />
                    </button>
                  </span>
                ))}
              </div>
            )}
            <input
              type="text"
              className="intake-input"
              placeholder="Type a condition and press Enter"
              onKeyDown={(e) => {
                if (e.key === 'Enter' && e.target.value.trim()) {
                  e.preventDefault()
                  update('comorbidities', [...(draft.comorbidities ?? []), e.target.value.trim()])
                  e.target.value = ''
                }
              }}
            />
          </fieldset>
        </div>
      ) : (
        <div className="intake-readout">
          <p className="intake-condition">{condition || 'Condition not set'}</p>

          {known.length > 0 && (
            <dl className="intake-facts">
              {known.map((f) => (
                <div className="intake-fact" key={f.key}>
                  <dt>{f.label}</dt>
                  <dd>{f.value}</dd>
                </div>
              ))}
            </dl>
          )}

          {priorTreatments.length > 0 && (
            <div className="intake-list">
              <p className="intake-list-label">Prior treatments</p>
              <ul>
                {priorTreatments.map((pt, i) => (
                  <li key={i}>
                    <span className="intake-list-name">
                      {pt.drug_brand || pt.raw_mention || 'Unnamed treatment'}
                    </span>
                    {/* Flag sits next to the name, not after the meta text —
                        the meta line wraps, which was stranding the badge
                        alone on a third line. */}
                    {pt.inferred && (
                      <span className="intake-flag" title="Interpreted from your wording, not stated directly">
                        inferred
                      </span>
                    )}
                    <span className="intake-list-meta">
                      {pt.drug_class ? `${pt.drug_class} · ` : ''}
                      {outcomeLabel(pt.outcome)}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {biomarkerRows.length > 0 && (
            <div className="intake-list">
              <p className="intake-list-label">Biomarkers</p>
              <ul>
                {biomarkerRows.map((b, i) => (
                  <li key={i}>
                    <span className="intake-list-name">{b.marker}</span>
                    <span className="intake-list-meta">{b.status}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {(draft.comorbidities ?? []).length > 0 && (
            <div className="intake-list">
              <p className="intake-list-label">Other conditions</p>
              <ul>
                {draft.comorbidities.map((c, i) => (
                  <li key={i}>
                    <span className="intake-list-name">{c}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {missing.length > 0 && (
            <p className="intake-missing">
              Not provided: {missing.map((f) => f.prose).join(', ')}.{' '}
              <button type="button" className="intake-inline-link" onClick={() => setEditing(true)}>
                Add them
              </button>
            </p>
          )}
        </div>
      )}

      {draft.assumptions?.length > 0 && (
        <div className="intake-reasoning">
          <button
            type="button"
            className="intake-disclosure"
            aria-expanded={reasoningOpen}
            onClick={() => setReasoningOpen((v) => !v)}
          >
            <ChevronIcon className={`intake-disclosure-icon${reasoningOpen ? ' intake-disclosure-icon--open' : ''}`} />
            {draft.assumptions.length === 1 ? '1 thing I worked out' : `${draft.assumptions.length} things I worked out`}
          </button>
          {reasoningOpen && (
            <ul className="intake-reasoning-list">
              {draft.assumptions.map((text, i) => (
                <li key={i}>{text}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {optionalGaps.map((gap) => (
        <div className="intake-optional" key={gap.gap_id}>
          <p className="intake-optional-label">Answer this to narrow the results</p>
          <p className="intake-optional-question">{gap.label}</p>
          <GapInput gap={gap} onAnswer={(text) => onResolveGap(gap.gap_id, gap.field, text)} />
        </div>
      ))}

      {showAction && (
        <button className="btn-primary intake-action" disabled={matching} onClick={() => onConfirm(draft)}>
          {actionLabel}
        </button>
      )}
    </section>
  )
}
