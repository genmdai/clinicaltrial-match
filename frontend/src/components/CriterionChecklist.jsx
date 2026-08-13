import { useState } from 'react'
import './CriterionChecklist.css'

const ICON = { PASS: '✅', FAIL: '❌', UNKNOWN: '❓' }

export default function CriterionChecklist({ verdicts, onAnswerThis }) {
  const [expanded, setExpanded] = useState(() => new Set())

  const toggle = (ruleId) =>
    setExpanded((s) => {
      const next = new Set(s)
      if (next.has(ruleId)) {
        next.delete(ruleId)
      } else {
        next.add(ruleId)
      }
      return next
    })

  return (
    <ul className="checklist">
      {verdicts.map((v) => {
        const isOpen = expanded.has(v.rule_id)
        return (
          <li key={v.rule_id} className={`checklist-row checklist-row--${v.verdict.toLowerCase()}`}>
            <button className="checklist-row-header" onClick={() => toggle(v.rule_id)}>
              <span className="checklist-icon">{ICON[v.verdict]}</span>
              <span className="checklist-reason">{v.reason}</span>
              <span className="checklist-caret">{isOpen ? '▾' : '▸'}</span>
            </button>
            {isOpen && (
              <div className="checklist-detail">
                <blockquote className="checklist-quote">"{v.source_quote}"</blockquote>
                {v.verdict === 'UNKNOWN' && v.follow_up_question && (
                  <button
                    className="btn-secondary"
                    onClick={() => onAnswerThis(v.rule_id, v.follow_up_question)}
                  >
                    Answer this
                  </button>
                )}
              </div>
            )}
          </li>
        )
      })}
    </ul>
  )
}
