import { useState } from 'react'
import { formatQuestionText } from '../questionText'
import './ScreeningQuestion.css'

// Buttons are chosen by `answer_mode`, computed server-side in next_question.py:
// - "choice": the synthetic travel-radius question's fixed option set.
// - "yes_no_notsure": biomarker/condition confirmations.
// - "no_or_specify": treatment_naive/prior_therapy_class — "Yes" can't resolve
//   anything on its own (it doesn't say *which* drug), so it opens a free-text
//   follow-up instead of a same-tier button.
// - "free_text": age/ecog — needs an actual number, never a button.
export default function ScreeningQuestion({ question, noFurtherQuestions, onAnswer }) {
  const [showWhy, setShowWhy] = useState(false)
  const [specifying, setSpecifying] = useState(false)

  if (!question) {
    if (!noFurtherQuestions) return null
    return (
      <div className="screening-question screening-question--done">
        Nothing else we could ask would separate these studies — the remaining differences are for a study team to
        confirm.
      </div>
    )
  }

  const isRadius = question.cluster_key === '__travel_radius__'
  const questionText = formatQuestionText(question)

  return (
    <div className="screening-question" key={question.cluster_key}>
      <p className="screening-question-text">{questionText}</p>

      {question.answer_mode === 'choice' && (
        <div className="screening-question-buttons">
          {question.choices.map((choice) => (
            <button key={choice} type="button" className="btn-secondary" onClick={() => onAnswer(choice)}>
              {choice}
            </button>
          ))}
        </div>
      )}

      {question.answer_mode === 'yes_no_notsure' && (
        <div className="screening-question-buttons">
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
      )}

      {question.answer_mode === 'no_or_specify' && !specifying && (
        <div className="screening-question-buttons">
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
      )}
      {question.answer_mode === 'no_or_specify' && specifying && (
        <p className="screening-question-hint">Type which drug or drug class in the message box below.</p>
      )}

      {question.answer_mode === 'free_text' && (
        <p className="screening-question-hint">Type your answer in the message box below.</p>
      )}

      {question.example_quote && !isRadius && (
        <button type="button" className="screening-question-why" onClick={() => setShowWhy((s) => !s)}>
          Why are you asking this?
        </button>
      )}
      {showWhy && question.example_quote && (
        <blockquote className="screening-question-quote">
          &ldquo;{question.example_quote}&rdquo; — {question.example_nct_id}
        </blockquote>
      )}
    </div>
  )
}
