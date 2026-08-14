// Shared with ScreeningQuestion.jsx (live question card) and App.jsx (chat
// history) so a question reads identically whether it's the one currently
// being asked or one being archived into the transcript after being answered.
export function formatQuestionText(question) {
  if (question.cluster_key === '__travel_radius__') return question.label
  return `${question.label} — decides ${question.decides_count} of the ${question.total_open} studies below`
}
