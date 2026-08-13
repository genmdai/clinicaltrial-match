// Loading-stage progress list. Driven by real pipeline progress (App.jsx advances
// `step` as each backend call actually resolves), not a fake timer.
export default function ProgressStream({ steps, activeIndex }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 26, paddingTop: 24 }}>
      {steps.map((label, i) => {
        const done = i < activeIndex
        const active = i === activeIndex
        const width = done ? '100%' : active ? '60%' : '0%'
        const color = i <= activeIndex ? 'var(--color-accent-700)' : 'var(--color-neutral-600)'
        return (
          <div
            key={label}
            style={{ display: 'flex', flexDirection: 'column', gap: 8, maxWidth: 520, opacity: i <= activeIndex ? 1 : 0.35 }}
          >
            <div style={{ fontSize: 19, fontFamily: 'var(--font-heading)', fontWeight: 600, color }}>{label}</div>
            <div style={{ height: 2, background: 'var(--color-divider)' }}>
              <div style={{ height: 2, background: 'var(--color-accent-700)', width, transition: 'width .5s ease' }} />
            </div>
          </div>
        )
      })}
    </div>
  )
}
