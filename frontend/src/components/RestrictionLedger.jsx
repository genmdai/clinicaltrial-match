import './RestrictionLedger.css'

// `ledger[i]` corresponds to `answers[i]` — next_question.fold_ledger builds
// ledger entries in the same order the answers were applied.
export default function RestrictionLedger({ answers, ledger, onRemove }) {
  return (
    <div className="restriction-ledger">
      <div className="restriction-ledger-header">
        <span>Restriction applied</span>
        <span>Ruled out</span>
        <span>Left</span>
      </div>
      {answers.map((answer, i) => {
        const effect = ledger[i]
        return (
          <div className="restriction-row" key={`${answer.cluster_key}-${i}`}>
            <span className="restriction-chip">
              {answer.ledger_label}: {answer.text}
              <button
                type="button"
                className="restriction-remove"
                aria-label={`Remove ${answer.ledger_label} restriction`}
                onClick={() => onRemove(i)}
              >
                ×
              </button>
            </span>
            {effect ? (
              <>
                <span className="restriction-ruled-out">
                  {effect.ruled_out_count > 0 ? `-${effect.ruled_out_count}` : '—'}
                </span>
                <span className="restriction-remaining">{effect.remaining_count}</span>
              </>
            ) : (
              <span className="restriction-pending">…</span>
            )}
          </div>
        )
      })}
    </div>
  )
}
