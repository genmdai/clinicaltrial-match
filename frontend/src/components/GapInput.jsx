import { useState } from 'react'
import './GapInput.css'

// The one dynamic answer renderer shared by AssumptionsCard (pre-search
// ProfileGaps) and ScreeningQuestion (post-search cross-trial questions) —
// keyed purely by answer_mode, never a hardcoded per-field option table.
// `gap` shape: { gap_id, field, label, answer_mode, options, required }.
//
// `inlineText`: when true (AssumptionsCard's structured form), free-text/
// "specify" answers get their own text input + submit button right here.
// When false (ScreeningQuestion), only a hint is shown and the caller's own
// shared chat input collects the free-text answer — preserves that
// component's existing, already-tested behavior untouched.
export default function GapInput({ gap, onAnswer, inlineText = true }) {
  const [specifying, setSpecifying] = useState(false)
  const [text, setText] = useState('')

  const submitText = () => {
    const trimmed = text.trim()
    if (!trimmed) return
    setText('')
    setSpecifying(false)
    onAnswer(trimmed)
  }

  const textRow = (placeholder) => (
    <div className="gap-input-text-row">
      <input
        type="text"
        value={text}
        placeholder={placeholder}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            e.preventDefault()
            submitText()
          }
        }}
      />
      <button type="button" className="btn-secondary" onClick={submitText}>
        Submit
      </button>
    </div>
  )

  if (gap.answer_mode === 'choice') {
    return (
      <div className="gap-input-buttons">
        {(gap.options ?? []).map((choice) => (
          <button key={choice} type="button" className="btn-secondary" onClick={() => onAnswer(choice)}>
            {choice}
          </button>
        ))}
      </div>
    )
  }

  if (gap.answer_mode === 'yes_no_notsure') {
    return (
      <div className="gap-input-buttons">
        <button type="button" className="btn-secondary" onClick={() => onAnswer('Yes, confirmed')}>
          Yes, confirmed
        </button>
        <button type="button" className="btn-secondary" onClick={() => onAnswer('No')}>
          No
        </button>
        <button type="button" className="btn-secondary" onClick={() => onAnswer('Not sure')}>
          Not sure
        </button>
      </div>
    )
  }

  if (gap.answer_mode === 'no_or_specify') {
    if (specifying) {
      return inlineText ? (
        textRow('Which drug or drug class?')
      ) : (
        <p className="gap-input-hint">Type which drug or drug class in the message box below.</p>
      )
    }
    return (
      <div className="gap-input-buttons">
        <button type="button" className="btn-secondary" onClick={() => onAnswer('No, never treated')}>
          No, never treated
        </button>
        <button type="button" className="btn-secondary" onClick={() => setSpecifying(true)}>
          Yes — which drug/class?
        </button>
        <button type="button" className="btn-secondary" onClick={() => onAnswer('Not sure')}>
          Not sure
        </button>
      </div>
    )
  }

  // free_text
  return inlineText ? (
    textRow('Type your answer…')
  ) : (
    <p className="gap-input-hint">Type your answer in the message box below.</p>
  )
}
