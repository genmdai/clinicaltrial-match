const EXAMPLES = [
  { label: 'What studies are recruiting?', text: 'What studies are recruiting for EGFR exon 20 NSCLC?' },
  { label: 'EGFR exon 20 lung cancer', text: 'I have stage IV lung cancer with EGFR exon 20. Chemotherapy stopped working.' },
  {
    label: 'Referring a patient',
    text: "I'm an oncologist looking for a study for a 61-year-old with EGFR ex20ins NSCLC after platinum and amivantamab.",
  },
]

export default function StartScreen({ draft, onDraftChange, onSubmit }) {
  return (
    <div
      className="tp-scroll tp-cover"
      style={{
        flex: 1,
        minHeight: 0,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 'clamp(18px,3.4vh,34px)',
        padding: 'clamp(24px,6vh,72px) 24px clamp(24px,6vh,64px)',
        textAlign: 'center',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
        <svg width="52" height="46" viewBox="0 0 52 46" aria-hidden="true">
          <path d="M4 34 L24 25 L48 33 L28 42 Z" fill="#dfe1e4" />
          <path d="M4 24 L24 15 L48 23 L28 32 Z" fill="#a9adb3" />
          <path d="M4 14 L24 5 L48 13 L28 22 Z" fill="#17181a" />
        </svg>
        <span style={{ fontFamily: 'var(--font-heading)', fontWeight: 700, fontSize: 27, lineHeight: 1.05, letterSpacing: '-.02em', textAlign: 'left' }}>
          TrialPath
          <br />
          <span style={{ fontSize: 19, fontWeight: 500, color: 'var(--color-neutral-700)' }}>Clinical Trials</span>
        </span>
      </div>

      <h1 style={{ fontSize: 'clamp(34px,6.6vh,58px)', lineHeight: 1.06, margin: 0, letterSpacing: '-.03em', maxWidth: '19ch' }}>
        Find clinical trials that may fit you
      </h1>

      <p style={{ fontSize: 'clamp(15px,2.2vh,19px)', lineHeight: 1.5, margin: 0, maxWidth: '52ch', color: 'var(--color-neutral-700)' }}>
        Describe the diagnosis and treatments you have in mind. I'll find recruiting studies that may fit and guide you through
        getting access.
      </p>

      <div
        style={{
          width: '100%',
          maxWidth: 760,
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          background: '#ffffff',
          border: '1px solid var(--color-neutral-300)',
          borderRadius: 16,
          boxShadow: '0 1px 2px rgba(32,30,29,.05), 0 8px 24px rgba(32,30,29,.05)',
          padding: '12px 12px 12px 22px',
        }}
      >
        <input
          style={{
            flex: 1,
            minWidth: 0,
            border: 0,
            outline: 'none',
            background: 'transparent',
            fontFamily: 'var(--font-body)',
            fontSize: 19,
            color: 'var(--color-text)',
            padding: '12px 0',
          }}
          placeholder="e.g. Stage IV NSCLC with EGFR exon 20, after chemotherapy"
          value={draft}
          onChange={(e) => onDraftChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              onSubmit()
            }
          }}
        />
        <button
          onClick={onSubmit}
          title="Find potential trials"
          style={{
            flex: 'none',
            width: 54,
            height: 54,
            border: 0,
            borderRadius: 14,
            background: '#17181a',
            color: '#ffffff',
            fontSize: 21,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          ↑
        </button>
      </div>

      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', justifyContent: 'center' }}>
        {EXAMPLES.map((ex) => (
          <button
            key={ex.label}
            onClick={() => onDraftChange(ex.text)}
            style={{
              background: '#ffffff',
              border: '1px solid var(--color-neutral-300)',
              borderRadius: 999,
              padding: '11px 20px',
              fontFamily: 'var(--font-body)',
              fontSize: 15,
              color: 'var(--color-text)',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
            }}
          >
            {ex.label}
          </button>
        ))}
      </div>
    </div>
  )
}
