import './ProgressStream.css'

export default function ProgressStream({ messages, active }) {
  if (!messages.length) return null

  return (
    <div className="progress-stream">
      {messages.map((message, i) => {
        const isLast = i === messages.length - 1
        return (
          <div className="progress-row" key={i}>
            <span className={`progress-dot ${isLast && active ? 'progress-dot--pulse' : ''}`} />
            <span className="progress-text">{message}</span>
          </div>
        )
      })}
    </div>
  )
}
