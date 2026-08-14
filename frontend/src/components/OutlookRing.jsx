import './OutlookRing.css'

const BAND_COLOR_VAR = {
  strong: 'var(--tier-high)',
  fair: 'var(--tier-moderate)',
  weak: 'var(--tier-blocked)',
}
const BAND_LABEL = { strong: 'Strong', fair: 'Fair', weak: 'Weak' }
const COMPONENT_LABELS = {
  eligibility_fit: 'Eligibility',
  recruitment_momentum: 'Momentum',
  geographic_access: 'Distance',
  contactability: 'Contact',
}

const SIZE = 120
const STROKE = 14
const RADIUS = (SIZE - STROKE) / 2
const CIRCUMFERENCE = 2 * Math.PI * RADIUS
const GAP = 3

// Four equal wedges, one per Access Outlook component, colored by its
// qualitative band. Segments are deliberately equal-sized rather than scaled
// by the underlying score — the backend documents score as internal-only, so
// this stays a categorical summary, never implying decimal precision.
export default function OutlookRing({ components }) {
  const segmentLength = CIRCUMFERENCE / components.length

  return (
    <div className="outlook-ring">
      <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`}>
        <g transform={`rotate(-90 ${SIZE / 2} ${SIZE / 2})`}>
          {components.map((c, i) => (
            <circle
              key={c.name}
              cx={SIZE / 2}
              cy={SIZE / 2}
              r={RADIUS}
              fill="none"
              stroke={BAND_COLOR_VAR[c.band] || 'var(--tier-unclear)'}
              strokeWidth={STROKE}
              strokeDasharray={`${segmentLength - GAP} ${CIRCUMFERENCE - segmentLength + GAP}`}
              strokeDashoffset={-i * segmentLength}
              strokeLinecap="round"
            />
          ))}
        </g>
      </svg>
      <ul className="outlook-ring-legend">
        {components.map((c) => (
          <li key={c.name}>
            <span className="outlook-ring-dot" style={{ background: BAND_COLOR_VAR[c.band] }} />
            <span className="outlook-ring-legend-label">{COMPONENT_LABELS[c.name] || c.name}</span>
            <span className="outlook-ring-legend-band">{BAND_LABEL[c.band] || c.band}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
