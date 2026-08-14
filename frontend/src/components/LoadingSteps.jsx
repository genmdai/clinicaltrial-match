import { MATCH_STAGES } from './matchStages'
import './LoadingSteps.css'

export default function LoadingSteps({ messages, active, liveProgress }) {
  const reachedCount = messages.filter((m) => MATCH_STAGES.includes(m)).length
  if (reachedCount === 0) return null

  return (
    <div className="loading-steps">
      {MATCH_STAGES.map((stage, i) => {
        const state = i < reachedCount - 1 || (i === reachedCount - 1 && !active) ? 'done' : i === reachedCount - 1 ? 'active' : 'pending'
        // Only the eligibility-parsing stage has a real completed/total count
        // (parse_progress from backend/main.py) — everything else keeps the
        // indeterminate pulse since there's nothing to measure it against.
        const showLiveCount = state === 'active' && liveProgress && liveProgress.total > 0
          && liveProgress.completed < liveProgress.total
        return (
          <div key={stage} className={`loading-step loading-step--${state}`}>
            <p className="loading-step-label">
              {stage}
              {showLiveCount && ` (${liveProgress.completed}/${liveProgress.total})`}
            </p>
            <div className="loading-step-track">
              <div
                className={`loading-step-fill${showLiveCount ? ' loading-step-fill--measured' : ''}`}
                style={showLiveCount ? { width: `${Math.round((liveProgress.completed / liveProgress.total) * 100)}%` } : undefined}
              />
            </div>
          </div>
        )
      })}
    </div>
  )
}
