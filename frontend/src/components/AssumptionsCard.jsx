import { useEffect, useState } from 'react'
import GapInput from './GapInput'
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

function fieldLabel(profile) {
  return profile.subject === 'relative' ? profile.relation || 'family member' : 'you'
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

// The "Assumptions I made" card, now a real structured intake/confirmation
// form: every field relevant to matching gets its own control (not a
// cosmetic dismissible chip), inferred/low-confidence values are visibly
// flagged, and any open `gaps` render inline via the shared GapInput
// component as required inputs — the same dynamic renderer ScreeningQuestion
// uses post-search, so pre-search and post-search clarification finally look
// and behave like one pattern.
//
// Gating rule: this only blocks /match while profile.gaps.length > 0 (an
// LLM-flagged ambiguity or missing material field). A clean extraction with
// no gaps never shows a blocking gate — matching has already started eagerly
// by the time this renders, and the form is just available for correction,
// exactly like before.
function hasRequiredGap(profile) {
  return (profile.gaps ?? []).some((g) => g.required)
}

export default function AssumptionsCard({ profile, onResolveGap, onConfirm }) {
  const [draft, setDraft] = useState(profile)
  const [everBlocked] = useState(() => hasRequiredGap(profile))

  useEffect(() => {
    setDraft(profile)
  }, [profile])

  const update = (field, value) => setDraft((d) => ({ ...d, [field]: value }))

  // Only a `required` gap (an unresolved/missing condition) blocks the
  // search — an optional gap (e.g. missing biomarker status) is shown below
  // as a worth-answering extra, but never disables "Search trials".
  const blocking = hasRequiredGap(profile)
  const dirty = JSON.stringify(draft) !== JSON.stringify(profile)
  const showButton = blocking || everBlocked || dirty
  const buttonLabel = blocking
    ? 'Answer the question(s) above to continue'
    : everBlocked
      ? 'Search trials'
      : 'Update and re-search'

  const conditionGap = (profile.gaps ?? []).find((g) => g.field === 'condition')
  const otherGaps = (profile.gaps ?? []).filter((g) => g.field !== 'condition')

  const biomarkerRows = (draft.biomarkers ?? []).map(parseBiomarker)
  const setBiomarkerRows = (rows) => update('biomarkers', rows.map(formatBiomarker).filter((s) => s.trim()))

  const priorTreatments = draft.prior_treatments ?? []
  const setPriorTreatments = (rows) => update('prior_treatments', rows)

  return (
    <div className="assumptions-card">
      <h3>What I understood</h3>
      <p className="assumptions-subtitle">
        About {fieldLabel(draft)} — review and fix anything that's off before we search.
      </p>

      {draft.assumptions?.length > 0 && (
        <ul className="assumption-list">
          {draft.assumptions.map((text, i) => (
            <li key={i}>{text}</li>
          ))}
        </ul>
      )}

      <div className="assumption-fields">
        <label>
          Age
          <input
            type="number"
            value={draft.age ?? ''}
            onChange={(e) => update('age', e.target.value === '' ? null : Number(e.target.value))}
          />
        </label>
        <label>
          Sex
          <select value={draft.sex ?? ''} onChange={(e) => update('sex', e.target.value || null)}>
            <option value="">Unknown</option>
            <option value="female">Female</option>
            <option value="male">Male</option>
            <option value="other">Other</option>
          </select>
        </label>
        <label>
          Location
          <input
            type="text"
            value={draft.location_zip ?? ''}
            onChange={(e) => update('location_zip', e.target.value)}
            placeholder="ZIP code, or city/country — optional"
          />
        </label>
      </div>

      <div className="assumption-section">
        <label className="assumption-section-label">
          Condition
          <input
            type="text"
            value={draft.condition ?? draft.condition_raw ?? ''}
            onChange={(e) => update('condition', e.target.value)}
          />
        </label>
        {conditionGap && (
          <div className="gap-block">
            <span className="gap-badge">Needs your input</span>
            <p className="gap-question">{conditionGap.label}</p>
            <GapInput
              gap={conditionGap}
              onAnswer={(text) => onResolveGap(conditionGap.gap_id, conditionGap.field, text)}
            />
          </div>
        )}
      </div>

      <div className="assumption-section">
        <span className="assumption-section-label">Biomarkers</span>
        {biomarkerRows.map((row, i) => (
          <div className="repeatable-row" key={i}>
            <input
              type="text"
              value={row.marker}
              placeholder="e.g. EGFR"
              onChange={(e) => {
                const next = [...biomarkerRows]
                next[i] = { ...row, marker: e.target.value }
                setBiomarkerRows(next)
              }}
            />
            <select
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
              className="row-remove"
              aria-label="Remove biomarker"
              onClick={() => setBiomarkerRows(biomarkerRows.filter((_, j) => j !== i))}
            >
              ×
            </button>
          </div>
        ))}
        <button type="button" className="btn-link" onClick={() => setBiomarkerRows([...biomarkerRows, { marker: '', status: 'unknown' }])}>
          + Add biomarker
        </button>
      </div>

      <div className="assumption-section">
        <span className="assumption-section-label">Prior treatments</span>
        {priorTreatments.map((pt, i) => (
          <div className="repeatable-row" key={i}>
            <input
              type="text"
              value={pt.raw_mention ?? ''}
              placeholder="Drug or treatment name"
              onChange={(e) => {
                const next = [...priorTreatments]
                next[i] = { ...pt, raw_mention: e.target.value }
                setPriorTreatments(next)
              }}
            />
            <select
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
            {pt.inferred && <span className="inferred-badge" title="Inferred, not directly stated">inferred</span>}
            <button
              type="button"
              className="row-remove"
              aria-label="Remove treatment"
              onClick={() => setPriorTreatments(priorTreatments.filter((_, j) => j !== i))}
            >
              ×
            </button>
          </div>
        ))}
        <button
          type="button"
          className="btn-link"
          onClick={() => setPriorTreatments([...priorTreatments, { raw_mention: '', outcome: null, inferred: false, confidence: 'low' }])}
        >
          + Add treatment
        </button>
      </div>

      <div className="assumption-fields">
        <label>
          ECOG status
          <select
            value={draft.ecog ?? ''}
            onChange={(e) => update('ecog', e.target.value === '' ? null : Number(e.target.value))}
          >
            {ECOG_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </label>
        <label>
          Prior treatment lines
          <input
            type="number"
            min="0"
            value={draft.treatment_line ?? ''}
            onChange={(e) => update('treatment_line', e.target.value === '' ? null : Number(e.target.value))}
            placeholder="Unknown"
          />
        </label>
      </div>

      <div className="assumption-section">
        <span className="assumption-section-label">Comorbidities</span>
        <div className="tag-row">
          {(draft.comorbidities ?? []).map((c, i) => (
            <span className="chip" key={i}>
              {c}
              <button
                type="button"
                className="chip-dismiss"
                aria-label="Remove"
                onClick={() => update('comorbidities', draft.comorbidities.filter((_, j) => j !== i))}
              >
                ×
              </button>
            </span>
          ))}
        </div>
        <input
          type="text"
          className="tag-add-input"
          placeholder="Type a condition and press Enter"
          onKeyDown={(e) => {
            if (e.key === 'Enter' && e.target.value.trim()) {
              e.preventDefault()
              update('comorbidities', [...(draft.comorbidities ?? []), e.target.value.trim()])
              e.target.value = ''
            }
          }}
        />
      </div>

      {otherGaps.map((gap) => (
        <div className="assumption-section gap-block" key={gap.gap_id}>
          <span className={`gap-badge ${gap.required ? '' : 'gap-badge--optional'}`}>
            {gap.required ? 'Needs your input' : 'Worth answering — narrows results'}
          </span>
          <p className="gap-question">{gap.label}</p>
          <GapInput gap={gap} onAnswer={(text) => onResolveGap(gap.gap_id, gap.field, text)} />
        </div>
      ))}

      {showButton && (
        <button className="btn-primary" disabled={blocking} onClick={() => onConfirm(draft)}>
          {buttonLabel}
        </button>
      )}
    </div>
  )
}
