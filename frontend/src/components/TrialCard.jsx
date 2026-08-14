import { useState } from 'react'
import CriterionChecklist from './CriterionChecklist'
import './TrialCard.css'

const STATUS_LABEL = {
  High: 'Strong potential match',
  Moderate: 'Potential match',
  Low: 'Potential match',
  Unclear: 'More information needed',
}

const COMPONENT_LABELS = {
  eligibility_fit: 'Eligibility',
  recruitment_momentum: 'Momentum',
  geographic_access: 'Distance',
  contactability: 'Contact',
}

// Fixed fill steps per qualitative band, not derived from the raw score —
// P9: never show a percentage, the bar communicates the band, not a number.
const BAND_FILL = { strong: '90%', fair: '55%', weak: '20%' }
const BAND_LABEL = { strong: 'Strong', fair: 'Fair', weak: 'Weak' }

export default function TrialCard({ trial, onSelectTrial, onOpenCompose }) {
  const [activeComponent, setActiveComponent] = useState(null)
  const { summary, outlook, verdicts, rules } = trial
  const tier = outlook.tier
  const blockingVerdict = outlook.blocking_rule_id
    ? verdicts.find((v) => v.rule_id === outlook.blocking_rule_id)
    : null
  const nearest = summary.nearest_site
  const statusLabel = STATUS_LABEL[tier] || tier
  const activeEvidence = activeComponent
    ? outlook.components.find((c) => c.name === activeComponent)?.evidence
    : null

  return (
    <div className={`trial-card trial-card--${tier.toLowerCase()}`}>
      <div className="trial-card-top">
        <span className={`status-label status-label--${tier.toLowerCase()}`}>{statusLabel}</span>
        <span className="phase-badge">{(summary.phase || []).join(', ') || 'Phase n/a'}</span>
      </div>

      {/* All four Access Outlook components, always visible — P9: never a
          percentage, always the tier + the registry evidence behind it. */}
      <div className="component-rows">
        {outlook.components.map((c) => (
          <button
            key={c.name}
            type="button"
            className={`component-row component-row--${c.band} ${
              activeComponent === c.name ? 'component-row--active' : ''
            }`}
            onClick={() => setActiveComponent(activeComponent === c.name ? null : c.name)}
          >
            <span className="component-row-label">{COMPONENT_LABELS[c.name] || c.name}</span>
            <span className="component-row-track">
              <span className="component-row-fill" style={{ width: BAND_FILL[c.band] }} />
            </span>
            <span className="component-row-band">{BAND_LABEL[c.band] || c.band}</span>
          </button>
        ))}
      </div>
      {activeEvidence && (
        <ul className="component-evidence">
          {activeEvidence.map((line, i) => (
            <li key={i}>{line}</li>
          ))}
        </ul>
      )}

      <h3 className="trial-title">{summary.title}</h3>
      <div className="trial-meta">
        <span>{summary.nct_id}</span>
        {nearest && (
          <span>
            {nearest.facility}
            {[nearest.city, nearest.country].filter(Boolean).length > 0 &&
              ` (${[nearest.city, nearest.country].filter(Boolean).join(', ')})`}
            {nearest.distance_mi != null ? ` · ${nearest.distance_mi} mi` : ' · add a location for distance'}
          </span>
        )}
      </div>

      {tier === 'Blocked' && blockingVerdict && (
        <div className="trial-blocked-quote">
          <strong>Why this is blocked:</strong> &ldquo;{blockingVerdict.source_quote}&rdquo;
        </div>
      )}

      {tier !== 'Blocked' && <CriterionChecklist rules={rules} verdicts={verdicts} />}

      <p className="trial-caveat">{outlook.caveat}</p>

      <div className="trial-actions">
        <button type="button" className="btn-secondary" onClick={onSelectTrial}>
          Look at this trial
        </button>
        <button type="button" className="btn-secondary" onClick={onOpenCompose}>
          Draft outreach
        </button>
      </div>
    </div>
  )
}
