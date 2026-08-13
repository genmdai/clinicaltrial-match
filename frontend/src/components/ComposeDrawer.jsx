import { useState } from 'react'

// CLAUDE.md P6 — compose, never send: this renders a copy-ready packet from
// compose_packet.py output. No SMTP, no mailto auto-fire, no send API — the only
// action is copying text to the clipboard for the patient to paste/share themselves.
function packetText(packet) {
  if (!packet) return ''
  return [
    'TrialPath access packet',
    '',
    'Patient summary:',
    packet.patient_summary,
    '',
    'Trial:',
    packet.trial,
    '',
    'Criteria:',
    packet.criteria_summary,
    '',
    'Next steps:',
    ...packet.next_steps.map((s) => `- ${s}`),
    '',
    packet.caveat,
  ].join('\n')
}

export default function ComposeDrawer({ packet, loading, error }) {
  const [preview, setPreview] = useState(false)
  const [copied, setCopied] = useState(false)

  if (loading) return <p style={{ fontSize: 13, color: 'var(--color-neutral-600)' }}>Composing packet…</p>
  if (error) return <p style={{ fontSize: 13, color: 'var(--color-accent-2-700)' }}>Could not compose a packet: {error}</p>
  if (!packet) return null

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(packetText(packet))
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      setPreview(true)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        <button className="btn btn-secondary" onClick={() => setPreview((p) => !p)}>
          {preview ? 'Hide packet' : 'Preview packet'}
        </button>
        <button className="btn btn-secondary" onClick={copy}>
          {copied ? 'Copied' : 'Copy summary'}
        </button>
      </div>
      {preview && (
        <pre
          className="tp-fade"
          style={{
            margin: 0,
            whiteSpace: 'pre-wrap',
            fontFamily: 'var(--font-body)',
            fontSize: 13,
            lineHeight: 1.6,
            background: 'var(--color-surface)',
            border: '1px solid var(--color-divider)',
            borderRadius: 'var(--radius-2)',
            padding: 16,
            maxWidth: 640,
          }}
        >
          {packetText(packet)}
        </pre>
      )}
    </div>
  )
}
