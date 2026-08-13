// Per-criterion verdict list — PASS / FAIL / UNKNOWN, each row citing the verbatim
// quoted substring of the trial's eligibility text it derives from (CLAUDE.md P1:
// "no verdict without evidence").
const GLYPH = { PASS: '✓', FAIL: '✕', UNKNOWN: '?' }
const COLOR = {
  PASS: 'var(--color-accent-700)',
  FAIL: 'var(--color-accent-2-700)',
  UNKNOWN: 'var(--color-neutral-700)',
}

export default function CriterionChecklist({ verdicts }) {
  if (!verdicts?.length) {
    return <div style={{ fontSize: 13, color: 'var(--color-neutral-600)' }}>No parsed criteria to show.</div>
  }
  return (
    <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 10, maxWidth: '64ch' }}>
      {verdicts.map((v) => (
        <li key={v.rule_id} style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'baseline', fontSize: 13, lineHeight: 1.5 }}>
            <span style={{ color: COLOR[v.verdict], flex: 'none' }}>{GLYPH[v.verdict]}</span>
            <span>{v.reason}</span>
          </div>
          {v.source_quote && (
            <p style={{ margin: '0 0 0 21px', fontSize: 12, fontStyle: 'italic', color: 'var(--color-neutral-700)', lineHeight: 1.5 }}>
              “{v.source_quote}”
            </p>
          )}
        </li>
      ))}
    </ul>
  )
}
