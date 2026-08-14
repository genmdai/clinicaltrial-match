import './ChatIntroCard.css'

export default function ChatIntroCard({ text }) {
  return (
    <div className="chat-intro-card">
      <div className="chat-intro-shape" aria-hidden="true" />
      <h2 className="chat-intro-heading">Let's find the right trial</h2>
      <p className="chat-intro-text">{text}</p>
    </div>
  )
}
