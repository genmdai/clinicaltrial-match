import { useState } from 'react'
import './AssumptionsCard.css'

function fieldLabel(profile) {
  const who = profile.subject === 'relative' ? (profile.relation || 'family member') : 'you'
  return who
}

export default function AssumptionsCard({ profile, onConfirm }) {
  const [draft, setDraft] = useState(profile)
  const [dismissed, setDismissed] = useState(() => new Set())

  const update = (field, value) => setDraft((d) => ({ ...d, [field]: value }))
  const visibleAssumptions = draft.assumptions.filter((_, i) => !dismissed.has(i))

  return (
    <div className="assumptions-card">
      <h3>Assumptions I made</h3>
      <p className="assumptions-subtitle">
        About {fieldLabel(draft)} — check these over before I search for trials.
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

      <button className="btn-primary" onClick={() => onConfirm({ ...draft, assumptions: visibleAssumptions })}>
        Looks right — find trials
      </button>
    </div>
  )
}
