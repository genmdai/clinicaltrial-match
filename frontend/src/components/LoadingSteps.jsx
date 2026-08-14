import { MATCH_STAGES } from './matchStages'
import './LoadingSteps.css'

export default function LoadingSteps({ messages, active }) {
  const reachedCount = messages.filter((m) => MATCH_STAGES.includes(m)).length
  if (reachedCount === 0) return null

  return (
    <div className="loading-steps">
      {MATCH_STAGES.map((stage, i) => {
        const state = i < reachedCount - 1 || (i === reachedCount - 1 && !active) ? 'done' : i === reachedCount - 1 ? 'active' : 'pending'
        return (
          <div key={stage} className={`loading-step loading-step--${state}`}>
            <p className="loading-step-label">{stage}</p>
            <div className="loading-step-track">
              <div className="loading-step-fill" />
            </div>
          </div>
        )
      })}
    </div>
  )
}
