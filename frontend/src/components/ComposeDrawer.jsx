import { useEffect, useState } from 'react'
import './ComposeDrawer.css'

export default function ComposeDrawer({ onCompose, onClose }) {
  const [tab, setTab] = useState('email')
  const [drafts, setDrafts] = useState({})
  const [loading, setLoading] = useState(false)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (drafts[tab]) return
    let cancelled = false
    setLoading(true)
    onCompose(tab).then((result) => {
      if (cancelled) return
      setDrafts((d) => ({ ...d, [tab]: result }))
      setLoading(false)
    })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab])

  const draft = drafts[tab]
  const bodyText = draft?.body ?? ''

  const copy = () => {
    navigator.clipboard.writeText(bodyText)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <div className="compose-drawer-backdrop" onClick={onClose}>
      <div className="compose-drawer" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <div className="compose-tabs">
          <button
            className={`compose-tab ${tab === 'email' ? 'compose-tab--active' : ''}`}
            onClick={() => setTab('email')}
          >
            Email trial team
          </button>
          <button
            className={`compose-tab ${tab === 'doctor_note' ? 'compose-tab--active' : ''}`}
            onClick={() => setTab('doctor_note')}
          >
            Note for your doctor
          </button>
          <button className="compose-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>

        <div className="compose-body">
          {loading && <p className="compose-loading">Drafting…</p>}
          {!loading && draft?.error && <p className="compose-error">{draft.error}</p>}
          {!loading && draft && !draft.error && (
            <>
              {draft.subject && <p className="compose-subject">Subject: {draft.subject}</p>}
              <pre className="compose-text">{draft.body}</pre>
            </>
          )}
        </div>

        <div className="compose-actions">
          <button className="btn-secondary" onClick={copy} disabled={!bodyText}>
            {copied ? 'Copied!' : 'Copy to clipboard'}
          </button>
          {tab === 'email' && draft?.mailto && (
            <a className="btn-secondary" href={draft.mailto}>
              Open in mail app
            </a>
          )}
        </div>
      </div>
    </div>
  )
}
