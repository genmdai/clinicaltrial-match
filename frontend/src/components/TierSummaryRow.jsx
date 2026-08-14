import './TierSummaryRow.css'

const TIER_ORDER = ['High', 'Moderate', 'Low', 'Unclear', 'Blocked']

export default function TierSummaryRow({ counts }) {
  const entries = TIER_ORDER.filter((tier) => counts[tier] > 0)
  if (entries.length === 0) return null

  return (
    <div className="tier-summary-row">
      {entries.map((tier) => (
        <span key={tier} className={`tier-pill tier-pill--${tier.toLowerCase()}`}>
          {tier}
          <strong>{counts[tier]}</strong>
        </span>
      ))}
    </div>
  )
}
