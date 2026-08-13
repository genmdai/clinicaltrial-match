import { useState } from 'react'
import { QUESTION_OPTIONS } from '../domain.js'

function QuestionPrompt({ question, onAnswer }) {
  const [whyOpen, setWhyOpen] = useState(false)
  const [text, setText] = useState('')
  const options = QUESTION_OPTIONS[question.field]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 11 }}>
      <p style={{ fontSize: 19, lineHeight: 1.35, margin: 0, maxWidth: '34ch' }}>{question.followUp}</p>
      {options ? (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {options.map((opt) => (
            <button key={opt.value} className="btn btn-secondary" onClick={() => onAnswer(opt.value)}>
              {opt.label}
            </button>
          ))}
        </div>
      ) : (
        <div style={{ display: 'flex', gap: 9 }}>
          <input
            className="input"
            style={{ fontSize: 15, padding: '10px 12px', maxWidth: 240 }}
            type={question.field === 'age' ? 'number' : 'text'}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && text.trim()) {
                e.preventDefault()
                onAnswer(text.trim())
                setText('')
              }
            }}
          />
          <button
            className="btn btn-primary"
            onClick={() => {
              if (text.trim()) {
                onAnswer(text.trim())
                setText('')
              }
            }}
          >
            Answer
          </button>
        </div>
      )}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <button className="btn btn-ghost" onClick={() => setWhyOpen((w) => !w)} style={{ alignSelf: 'flex-start', paddingLeft: 0, fontSize: 13, color: 'var(--color-accent-700)' }}>
          Why are you asking this?
        </button>
        {whyOpen && (
          <p className="tp-fade" style={{ fontSize: 13, lineHeight: 1.5, margin: 0, maxWidth: '46ch', fontStyle: 'italic', color: 'var(--color-neutral-800)' }}>
            This affects {question.affects} of the studies still in the set — that's why it's the next question.
          </p>
        )}
      </div>
    </div>
  )
}

export default function ChatPane({ chatRef, messages, isLoading, loadingMessage, question, onAnswer, quickAsks, typed, onTypedChange, onSendTyped, inputPlaceholder, children }) {
  return (
    <div style={{ minHeight: 0, display: 'flex', flexDirection: 'column' }}>
      <div className="tp-scroll" id="tp-chat" ref={chatRef} style={{ flex: '1 1 0', minHeight: 0, padding: '20px 36px 10px 32px', display: 'flex', flexDirection: 'column', gap: 24 }}>
        {children}

        {messages.map((m, i) => {
          const agent = m.role === 'TrialPath'
          return (
            <div key={i} className="tp-fade" style={{ display: 'flex', justifyContent: agent ? 'flex-start' : 'flex-end' }}>
              <div style={{ display: 'flex', gap: 11, maxWidth: '86%' }}>
                {agent && <span style={{ width: 9, height: 9, borderRadius: '50%', background: 'var(--color-accent)', flex: 'none', marginTop: 8 }} />}
                <p
                  style={{
                    fontSize: 15,
                    lineHeight: 1.55,
                    margin: 0,
                    padding: agent ? 0 : '10px 15px',
                    background: agent ? 'transparent' : 'var(--color-text)',
                    color: agent ? 'var(--color-text)' : 'var(--color-bg)',
                    borderRadius: agent ? 0 : 4,
                  }}
                >
                  {m.text}
                </p>
              </div>
            </div>
          )
        })}

        {isLoading && (
          <div style={{ display: 'flex', gap: 11, alignItems: 'flex-start' }}>
            <span style={{ width: 9, height: 9, borderRadius: '50%', background: 'var(--color-accent)', flex: 'none', marginTop: 8 }} />
            <p className="tp-pulse" style={{ fontSize: 15, lineHeight: 1.55, margin: 0, color: 'var(--color-accent-700)' }}>{loadingMessage}</p>
          </div>
        )}

        {quickAsks?.length > 0 && (
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', paddingLeft: 20 }}>
            {quickAsks.map((q) => (
              <button key={q.label} className="tp-chip" onClick={q.onClick} style={{ fontSize: 13 }}>
                {q.label}
              </button>
            ))}
          </div>
        )}
      </div>

      <div style={{ flex: '0 0 auto', padding: '12px 36px 20px 32px', display: 'flex', flexDirection: 'column', gap: 12 }}>
        {question && <QuestionPrompt question={question} onAnswer={onAnswer} />}
        <div style={{ display: 'flex', gap: 9, alignItems: 'stretch' }}>
          <input
            className="input"
            style={{ fontSize: 15, padding: '12px 14px' }}
            placeholder={inputPlaceholder}
            value={typed}
            onChange={(e) => onTypedChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault()
                onSendTyped()
              }
            }}
          />
          <button className="btn btn-primary" onClick={onSendTyped} style={{ padding: '0 18px', fontSize: 15 }} title="Send">
            Send
          </button>
        </div>
      </div>
    </div>
  )
}
