// Raw SVG inner-markup mirrors of icons.jsx's <TierIcon> cases, for the
// Leaflet map marker — L.divIcon takes an HTML string, not a React node, so
// the glyph has to be duplicated as markup rather than rendered from
// TierIcon. Kept in its own module (not icons.jsx) so that file only exports
// components, which is what React Fast Refresh requires.
export const TIER_ICON_HTML = {
  High: '<path d="M3.5 8.5L6.5 11.5L12.5 4.5"/>',
  Moderate: '<path d="M2.5 9.5C4 7 5.5 11 7 8.5S10 6 11 8S13.5 9.5 13.5 9.5"/>',
  Low: '<path d="M8 3.5V12M8 12L4.5 8.5M8 12L11.5 8.5"/>',
  Blocked: '<circle cx="8" cy="8" r="5"/><path d="M4.5 4.5L11.5 11.5"/>',
  Unclear:
    '<path d="M5.5 6C5.5 4.3 6.6 3.3 8 3.3S10.5 4.3 10.5 6C10.5 7.5 8 7.5 8 9.5"/>' +
    '<circle cx="8" cy="12.2" r="0.9" fill="currentColor" stroke="none"/>',
}
