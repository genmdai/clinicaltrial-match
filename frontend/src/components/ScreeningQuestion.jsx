import { useState } from 'react'
import { formatQuestionText } from '../questionText'
import GapInput from './GapInput'
import './ScreeningQuestion.css'

// Maps next_question.py's dict shape ({label, answer_mode, choices, ...}) to
// the ProfileGap-ish shape GapInput expects ({label, answer_mode, options,
// ...}) — a thin presentation-layer adapter, not a data-model merge. Keeps
// next_question.py's tested decides_count/tiebreak logic untouched.
function adaptQuestionToGap(question) {
  return {
    gap_id: question.gap_id ?? question.cluster_key,
    field: question.field,
    label: question.label,
    answer_mode: question.answer_mode,
    options: question.options ?? question.choices ?? [],
    required: true,
  }
}

export default function ScreeningQuestion({ question, noFurtherQuestions, onAnswer }) {
  const [showWhy, setShowWhy] = useState(false)

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

      <GapInput gap={adaptQuestionToGap(question)} onAnswer={onAnswer} inlineText={false} />

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
