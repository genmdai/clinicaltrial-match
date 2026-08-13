import { useState } from 'react'
import CriterionChecklist from './CriterionChecklist'
import SiteList from './SiteList'
import './TrialCard.css'

const COMPONENT_LABELS = {
  eligibility_fit: 'Eligibility',
  recruitment_momentum: 'Momentum',
  geographic_access: 'Distance',
  contactability: 'Contact',
}

export default function TrialCard({ trial, onAnswerThis, onOpenCompose }) {
  const [expanded, setExpanded] = useState(false)
  const [activeComponent, setActiveComponent] = useState(null)

  const { summary, outlook, verdicts, nearest_sites: nearestSites } = trial
  const tier = outlook.tier
  const blockingVerdict = outlook.blocking_rule_id
    ? verdicts.find((v) => v.rule_id === outlook.blocking_rule_id)
    : null
  const nearest = summary.nearest_site
  const activeEvidence = activeComponent
    ? outlook.components.find((c) => c.name === activeComponent)?.evidence
    : null

  return (
    <div className={`trial-card trial-card--${tier.toLowerCase()}`}>
      <div className="trial-card-top">
        <span className={`tier-pill tier-pill--${tier.toLowerCase()}`}>{tier}</span>
        <div className="component-bars">
          {outlook.components.map((c) => (
            <button
              key={c.name}
              type="button"
              className={`component-bar component-bar--${c.band} ${
                activeComponent === c.name ? 'component-bar--active' : ''
              }`}
              onClick={() => setActiveComponent(activeComponent === c.name ? null : c.name)}
            >
              {COMPONENT_LABELS[c.name] || c.name}
            </button>
          ))}
        </div>
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
        <span className="phase-badge">{(summary.phase || []).join(', ') || 'Phase n/a'}</span>
        <span>{summary.nct_id}</span>
        {nearest && (
          <span>
            {nearest.facility}
            {[nearest.city, nearest.country].filter(Boolean).length > 0 &&
              ` (${[nearest.city, nearest.country].filter(Boolean).join(', ')})`}
            {nearest.distance_mi != null ? ` · ${nearest.distance_mi} mi` : ' · add ZIP for distance'}
          </span>
        )}
      </div>

      {tier === 'Blocked' && blockingVerdict && (
        <div className="trial-blocked-quote">
          <strong>Why this is blocked:</strong> &ldquo;{blockingVerdict.source_quote}&rdquo;
        </div>
      )}

      {tier === 'Unclear' && (
        <button className="btn-secondary trial-unclear-cta" onClick={() => setExpanded(true)}>
          {outlook.open_questions} question{outlook.open_questions !== 1 ? 's' : ''} stand between you and an answer
        </button>
      )}

      <p className="trial-caveat">{outlook.caveat}</p>

      <div className="trial-actions">
        <button className="btn-secondary" onClick={() => setExpanded((e) => !e)}>
          {expanded ? 'Hide details' : 'Show eligibility checklist'}
        </button>
        <button className="btn-secondary" onClick={onOpenCompose}>
          Draft outreach
        </button>
      </div>

      {expanded && (
        <div className="trial-expanded">
          <CriterionChecklist
            verdicts={verdicts}
            onAnswerThis={(ruleId, question) => onAnswerThis(summary.nct_id, ruleId, question)}
          />
          {nearestSites && nearestSites.length > 0 && (
            <>
              <h4 className="trial-section-heading">Nearest sites</h4>
              <SiteList sites={nearestSites} />
            </>
          )}
        </div>
      )}
    </div>
  )
}
