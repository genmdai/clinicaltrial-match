import ComposeDrawer from './ComposeDrawer.jsx'

export default function ReadyPanel({ entry, packet, packetLoading, packetError }) {
  const { trial, verdicts = [] } = entry
  const confirmedCount = verdicts.filter((v) => v.verdict === 'PASS').length
  const unknownCount = verdicts.filter((v) => v.verdict === 'UNKNOWN').length
  const site = trial.nearest_site

  const tracker = [
    { glyph: '✓', label: 'Trial identified', color: 'var(--color-accent-700)', weight: 400 },
    { glyph: '✓', label: 'Gather information', color: 'var(--color-accent-700)', weight: 400 },
    { glyph: '✓', label: 'Prepare access packet', color: 'var(--color-accent-700)', weight: 400 },
    { glyph: '●', label: 'Contact study team', color: 'var(--color-accent-700)', weight: 600 },
    { glyph: '○', label: 'Formal screening', color: 'var(--color-neutral-600)', weight: 400 },
  ]

  return (
    <div className="tp-fade" style={{ display: 'flex', flexDirection: 'column', gap: 46 }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        <div className="tp-uppercase-label">Where you are</div>
        {tracker.map((t) => (
          <div key={t.label} style={{ display: 'flex', gap: 13, alignItems: 'baseline', color: t.color }}>
            <span style={{ width: 14, display: 'inline-block' }}>{t.glyph}</span>
            <span style={{ fontSize: 15, fontWeight: t.weight }}>{t.label}</span>
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
        <h3 style={{ fontSize: 21, margin: 0 }}>Trial access packet</h3>
        <ComposeDrawer packet={packet} loading={packetLoading} error={packetError} />
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 18, maxWidth: 760 }}>
        <h3 style={{ fontSize: 32, margin: 0, lineHeight: 1.15 }}>Ready for the next step</h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 7, fontSize: 15 }}>
          <div><span style={{ color: 'var(--color-accent-700)', marginRight: 10 }}>✓</span>identified a potential trial</div>
          <div><span style={{ color: 'var(--color-accent-700)', marginRight: 10 }}>✓</span>confirmed {confirmedCount} eligibility criteria from your information</div>
          <div><span style={{ color: 'var(--color-accent-700)', marginRight: 10 }}>✓</span>identified {unknownCount} item{unknownCount === 1 ? '' : 's'} requiring verification</div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2, paddingTop: 2 }}>
          <div className="tp-uppercase-label">Recruiting site</div>
          <div style={{ fontSize: 19 }}>{site?.facility || 'Not resolved'}</div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap', paddingTop: 6 }}>
          <a
            className="btn btn-primary"
            style={{ fontSize: 15, padding: '13px 24px' }}
            href={`https://clinicaltrials.gov/study/${trial.nct_id}`}
            target="_blank"
            rel="noreferrer"
          >
            View official ClinicalTrials.gov study
          </a>
        </div>
        <p style={{ fontSize: 13, lineHeight: 1.5, margin: 0, color: 'var(--color-neutral-700)', maxWidth: '60ch' }}>
          These criteria appear consistent with the information you've provided. The study team must confirm final eligibility.
          Informational only — not medical advice.
        </p>
      </div>
    </div>
  )
}
