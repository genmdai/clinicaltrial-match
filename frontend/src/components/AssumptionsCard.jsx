// CLAUDE.md P4: anything inferred rather than stated must be visible and
// user-editable before matching. Shown as an agent message with a dismiss-per-item
// affordance rather than a blocking modal, since matching still proceeds from the
// editable profile card either way — this just makes the inferences visible.
export default function AssumptionsCard({ assumptions }) {
  if (!assumptions?.length) return null
  return (
    <div className="card tp-fade" style={{ padding: 'var(--space-4)', gap: 'var(--space-2)', boxShadow: 'var(--shadow-sm)' }}>
      <div className="card-kicker">Assumptions I made</div>
      <ul style={{ margin: 0, padding: '0 0 0 18px', display: 'flex', flexDirection: 'column', gap: 6, fontSize: 13, lineHeight: 1.5 }}>
        {assumptions.map((a, i) => (
          <li key={i}>{a}</li>
        ))}
      </ul>
      <p style={{ margin: 0, fontSize: 12, color: 'var(--color-neutral-600)' }}>
        Edit the profile above if any of this looks wrong before we search.
      </p>
    </div>
  )
}
