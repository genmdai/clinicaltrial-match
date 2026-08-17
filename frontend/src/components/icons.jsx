// Authored, single-stroke icon set (2px round stroke, 16x16 grid) — used
// anywhere the UI needs a tier glyph or the wordmark's icon badge, instead of
// unicode/emoji standing in for an icon system.

const STROKE_PROPS = {
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
}

export function TierIcon({ tier, className }) {
  const props = { viewBox: '0 0 16 16', className, 'aria-hidden': true, ...STROKE_PROPS }
  switch (tier) {
    case 'High':
      return (
        <svg {...props}>
          <path d="M3.5 8.5L6.5 11.5L12.5 4.5" />
        </svg>
      )
    case 'Moderate':
      return (
        <svg {...props}>
          <path d="M2.5 9.5C4 7 5.5 11 7 8.5S10 6 11 8S13.5 9.5 13.5 9.5" />
        </svg>
      )
    case 'Low':
      return (
        <svg {...props}>
          <path d="M8 3.5V12M8 12L4.5 8.5M8 12L11.5 8.5" />
        </svg>
      )
    case 'Blocked':
      return (
        <svg {...props}>
          <circle cx="8" cy="8" r="5" />
          <path d="M4.5 4.5L11.5 11.5" />
        </svg>
      )
    case 'Unclear':
    default:
      return (
        <svg {...props}>
          <path d="M5.5 6C5.5 4.3 6.6 3.3 8 3.3S10.5 4.3 10.5 6C10.5 7.5 8 7.5 8 9.5" />
          <circle cx="8" cy="12.2" r="0.9" fill="currentColor" stroke="none" />
        </svg>
      )
  }
}

export function CompassIcon({ className }) {
  return (
    <svg viewBox="0 0 16 16" className={className} aria-hidden="true" {...STROKE_PROPS}>
      <circle cx="8" cy="8" r="5.5" />
      <path d="M9.8 6.2L8.7 9.2L5.7 10.3L6.8 7.3L9.8 6.2Z" strokeLinejoin="round" />
    </svg>
  )
}

export function FunnelIcon({ className }) {
  return (
    <svg viewBox="0 0 16 16" className={className} aria-hidden="true" {...STROKE_PROPS}>
      <path d="M3 3.5H13L9 8.3V12L7 13V8.3L3 3.5Z" strokeLinejoin="round" />
    </svg>
  )
}

// Intake card glyphs. The "read" mark stands for the agent having read the
// narrative — a document with a scan line across it, not a generic sparkle.
export function ReadIcon({ className }) {
  return (
    <svg viewBox="0 0 16 16" className={className} aria-hidden="true" {...STROKE_PROPS}>
      <path d="M4 2.5H9.5L12.5 5.5V13.5H4V2.5Z" />
      <path d="M9.3 2.6V5.7H12.4" />
      <path d="M6 9.2H10.5" />
    </svg>
  )
}

export function PencilIcon({ className }) {
  return (
    <svg viewBox="0 0 16 16" className={className} aria-hidden="true" {...STROKE_PROPS}>
      <path d="M11.2 2.9L13.1 4.8L5.6 12.3L3 13L3.7 10.4L11.2 2.9Z" />
    </svg>
  )
}

export function ChevronIcon({ className }) {
  return (
    <svg viewBox="0 0 16 16" className={className} aria-hidden="true" {...STROKE_PROPS}>
      <path d="M5.5 3.5L10.5 8L5.5 12.5" />
    </svg>
  )
}

export function PlusIcon({ className }) {
  return (
    <svg viewBox="0 0 16 16" className={className} aria-hidden="true" {...STROKE_PROPS}>
      <path d="M8 3.5V12.5M3.5 8H12.5" />
    </svg>
  )
}

export function CloseIcon({ className }) {
  return (
    <svg viewBox="0 0 16 16" className={className} aria-hidden="true" {...STROKE_PROPS}>
      <path d="M4.5 4.5L11.5 11.5M11.5 4.5L4.5 11.5" />
    </svg>
  )
}

// TopBar wordmark mark: an abstract "route" glyph — start point, a curved
// path, destination point — echoing the product name without borrowing a
// stock icon-font glyph.
export function PathwayMark({ className }) {
  return (
    <svg viewBox="0 0 16 16" className={className} aria-hidden="true" {...STROKE_PROPS}>
      <circle cx="3.6" cy="12" r="1.4" fill="currentColor" stroke="none" />
      <path d="M4.8 11C7 11 6 5.5 9.2 5S12.4 7.5 12.4 4" />
      <circle cx="12.4" cy="4" r="1.4" fill="currentColor" stroke="none" />
    </svg>
  )
}
