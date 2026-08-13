import { useState } from 'react'
import CriterionChecklist from './CriterionChecklist.jsx'

export default function TrialCard({ entry, onSelect }) {
  const [expanded, setExpanded] = useState(false)
  const { trial, verdicts = [], rollup } = entry

  const passCount = verdicts.filter((v) => v.verdict === 'PASS').length
  const unknownCount = verdicts.filter((v) => v.verdict === 'UNKNOWN').length
  const strong = passCount >= 3 && unknownCount === 0
  const strength = strong ? 'Strong potential match' : passCount >= 1 ? 'Potential match' : 'More information needed'

  const site = trial.nearest_site
  const siteLine = site?.facility
    ? `${site.facility} — ${site.distance_mi != null ? site.distance_mi + ' miles away' : ''}`
    : `${trial.site_count} site${trial.site_count === 1 ? '' : 's'} listed`

  return (
    <div className="card tp-fade" style={{ padding: 'var(--space-4)', gap: 'var(--space-2)', boxShadow: strong ? 'var(--shadow-sm)' : 'none' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
        <span style={{ fontSize: 11, letterSpacing: '.12em', textTransform: 'uppercase', color: strong ? 'var(--color-accent-700)' : 'var(--color-neutral-700)' }}>
          {strength}
        </span>
        <span style={{ fontSize: 11, letterSpacing: '.12em', textTransform: 'uppercase', color: 'var(--color-neutral-600)', marginLeft: 'auto' }}>
          {(trial.phase || []).join(', ') || 'Phase not listed'}
        </span>
      </div>
      <div style={{ fontSize: 21, fontFamily: 'var(--font-heading)', fontWeight: 600 }}>{trial.title}</div>
      <div style={{ fontSize: 13, color: 'var(--color-neutral-700)' }}>
        {trial.nct_id} · {trial.status}
      </div>
      <div style={{ fontSize: 15 }}>{siteLine}</div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 22, paddingTop: 6 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
          <div className="tp-uppercase-label">Confirmed from your information</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 5, fontSize: 13, lineHeight: 1.4 }}>
            {passCount === 0 && <div style={{ color: 'var(--color-neutral-600)' }}>Nothing confirmed yet — keep answering</div>}
            {verdicts
              .filter((v) => v.verdict === 'PASS')
              .map((v) => (
                <div key={v.rule_id} className="tp-fade">
                  <span style={{ color: 'var(--color-accent-700)', marginRight: 8 }}>✓</span>
                  {v.reason}
                </div>
              ))}
          </div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
            <div className="tp-uppercase-label">Needs verification</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 5, fontSize: 13, lineHeight: 1.4, color: 'var(--color-neutral-800)' }}>
              {unknownCount === 0 && <div style={{ color: 'var(--color-neutral-600)' }}>Nothing outstanding</div>}
              {verdicts
                .filter((v) => v.verdict === 'UNKNOWN')
                .slice(0, 4)
                .map((v) => (
                  <div key={v.rule_id}>
                    <span style={{ marginRight: 8 }}>?</span>
                    {v.follow_up_question || v.reason}
                  </div>
                ))}
            </div>
          </div>
        </div>
      </div>

      {expanded && (
        <div className="tp-fade" style={{ display: 'flex', flexDirection: 'column', gap: 10, paddingTop: 8 }}>
          <div className="tp-uppercase-label">Why TrialPath surfaced this study — {rollup}</div>
          <CriterionChecklist verdicts={verdicts} />
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
            <span style={{ fontSize: 11, letterSpacing: '.1em', textTransform: 'uppercase', color: 'var(--color-accent-700)' }}>
              Source: ClinicalTrials.gov
            </span>
          </div>
        </div>
      )}

      <div style={{ display: 'flex', gap: 9, paddingTop: 8, flexWrap: 'wrap' }}>
        <button className="btn btn-primary" onClick={() => onSelect(entry)}>View access steps</button>
        <button className="btn btn-secondary" onClick={() => setExpanded((e) => !e)}>
          {expanded ? 'Hide reasoning' : 'Why this trial?'}
        </button>
        <a className="btn btn-ghost" href={`https://clinicaltrials.gov/study/${trial.nct_id}`} target="_blank" rel="noreferrer">
          View study details
        </a>
      </div>
    </div>
  )
}
