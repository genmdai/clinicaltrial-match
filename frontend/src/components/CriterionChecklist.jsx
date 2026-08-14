import { useState } from 'react'
import './CriterionChecklist.css'

const ICON = { PASS: '✅', UNKNOWN_INCLUSION: '❓', UNKNOWN_EXCLUSION: '⚠️' }

// Split by EligibilityRule.kind, not re-implemented eligibility logic: an
// UNKNOWN inclusion criterion is "is this required thing true of you?" (Needs
// verification); an UNKNOWN exclusion criterion is "does this disqualifying
// thing NOT apply to you?" (Possible concern). Any FAIL verdict would already
// have made this trial "Blocked" (removed from the open set upstream), so a
// rendered card only ever has PASS/UNKNOWN verdicts to show.
export default function CriterionChecklist({ rules, verdicts }) {
  const [expanded, setExpanded] = useState(() => new Set())
  const ruleById = Object.fromEntries(rules.map((r) => [r.rule_id, r]))

  const toggle = (ruleId) =>
    setExpanded((s) => {
      const next = new Set(s)
      if (next.has(ruleId)) next.delete(ruleId)
      else next.add(ruleId)
      return next
    })

  const confirmed = verdicts.filter((v) => v.verdict === 'PASS')
  const needsVerification = verdicts.filter(
    (v) => v.verdict === 'UNKNOWN' && ruleById[v.rule_id]?.kind !== 'exclusion',
  )
  const possibleConcern = verdicts.filter(
    (v) => v.verdict === 'UNKNOWN' && ruleById[v.rule_id]?.kind === 'exclusion',
  )

  const renderRow = (v, icon) => {
    const isOpen = expanded.has(v.rule_id)
    return (
      <li key={v.rule_id} className="checklist-row">
        <button type="button" className="checklist-row-header" onClick={() => toggle(v.rule_id)}>
          <span className="checklist-icon">{icon}</span>
          <span className="checklist-reason">{v.reason}</span>
          <span className="checklist-caret">{isOpen ? '▾' : '▸'}</span>
        </button>
        {isOpen && <blockquote className="checklist-quote">&ldquo;{v.source_quote}&rdquo;</blockquote>}
      </li>
    )
  }

  return (
    <div className="checklist">
      <div className="checklist-section">
        <h5 className="checklist-section-heading">Confirmed from your information</h5>
        {confirmed.length === 0 ? (
          <p className="checklist-empty">Nothing confirmed yet — keep answering.</p>
        ) : (
          <ul>{confirmed.map((v) => renderRow(v, ICON.PASS))}</ul>
        )}
      </div>

      {needsVerification.length > 0 && (
        <div className="checklist-section">
          <h5 className="checklist-section-heading">Needs verification</h5>
          <ul>{needsVerification.map((v) => renderRow(v, ICON.UNKNOWN_INCLUSION))}</ul>
        </div>
      )}

      {possibleConcern.length > 0 && (
        <div className="checklist-section checklist-section--concern">
          <h5 className="checklist-section-heading">Possible concern</h5>
          <ul>{possibleConcern.map((v) => renderRow(v, ICON.UNKNOWN_EXCLUSION))}</ul>
        </div>
      )}
    </div>
  )
}
