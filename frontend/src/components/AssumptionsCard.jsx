import { useEffect, useState } from 'react'
import './AssumptionsCard.css'

function fieldLabel(profile) {
  const who = profile.subject === 'relative' ? (profile.relation || 'family member') : 'you'
  return who
}

// No longer a confirm-before-search gate (P4 still requires inferred facts
// stay visible/editable — it just can't block the first search anymore).
// Editing age/condition/ZIP re-runs the whole match, since those change what
// the search itself finds, not just narrowing an existing candidate set.
export default function AssumptionsCard({ profile, onUpdate }) {
  const [draft, setDraft] = useState(profile)
  const [dismissed, setDismissed] = useState(() => new Set())

  useEffect(() => {
    setDraft(profile)
    setDismissed(new Set())
  }, [profile])

  const update = (field, value) => setDraft((d) => ({ ...d, [field]: value }))
  const visibleAssumptions = draft.assumptions.filter((_, i) => !dismissed.has(i))
  const dirty =
    draft.age !== profile.age ||
    (draft.condition ?? draft.condition_raw ?? '') !== (profile.condition ?? profile.condition_raw ?? '') ||
    (draft.location_zip ?? '') !== (profile.location_zip ?? '')

  return (
    <div className="assumptions-card">
      <h3>What I understood</h3>
      <p className="assumptions-subtitle">
        About {fieldLabel(draft)} — edit anything that's off, it'll re-run the search.
      </p>

      {visibleAssumptions.length > 0 && (
        <div className="assumption-chips">
          {draft.assumptions.map((text, i) =>
            dismissed.has(i) ? null : (
              <span className="chip" key={i}>
                {text}
                <button
                  className="chip-dismiss"
                  aria-label="Dismiss this assumption"
                  onClick={() => setDismissed((s) => new Set([...s, i]))}
                >
                  ×
                </button>
              </span>
            ),
          )}
        </div>
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
          Condition
          <input
            type="text"
            value={draft.condition ?? draft.condition_raw ?? ''}
            onChange={(e) => update('condition', e.target.value)}
          />
        </label>
        <label>
          ZIP code
          <input
            type="text"
            value={draft.location_zip ?? ''}
            onChange={(e) => update('location_zip', e.target.value)}
            placeholder="optional, for nearby sites"
          />
        </label>
      </div>

      {dirty && (
        <button className="btn-secondary" onClick={() => onUpdate({ ...draft, assumptions: visibleAssumptions })}>
          Update and re-search
        </button>
      )}
    </div>
  )
}
