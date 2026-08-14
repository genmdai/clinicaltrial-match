import { useEffect, useMemo } from 'react'
import { AttributionControl, MapContainer, Marker, Polyline, Popup, TileLayer, ZoomControl, useMap } from 'react-leaflet'
import L from 'leaflet'
import { TIER_ICON_HTML } from './tierIconPaths'
import './TrialMap.css'

// Matches TIER_ORDER in TierSummaryRow.jsx — best outcome first, used to pick
// a single representative color when a site hosts several trials.
const TIER_PRIORITY = ['High', 'Moderate', 'Low', 'Unclear', 'Blocked']

function bestTier(trials) {
  for (const tier of TIER_PRIORITY) {
    if (trials.some((t) => t.tier === tier)) return tier
  }
  return 'Unclear'
}

// Mirrors backend/tools/geo.py's haversine_miles — only used for the popup's
// distance label, since the map already has real lat/lon for both points.
function haversineMiles(lat1, lon1, lat2, lon2) {
  const R = 3958.8
  const toRad = (d) => (d * Math.PI) / 180
  const dLat = toRad(lat2 - lat1)
  const dLon = toRad(lon2 - lon1)
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2
  return 2 * R * Math.asin(Math.sqrt(a))
}

function siteIcon(tier, count, isFocused) {
  const glyph = TIER_ICON_HTML[tier] || TIER_ICON_HTML.Unclear
  const countBadge = count > 1 ? `<span class="trial-marker-count">${count}</span>` : ''
  return L.divIcon({
    className: 'trial-marker-wrapper',
    html:
      `<span class="trial-marker trial-marker--${tier.toLowerCase()}${isFocused ? ' trial-marker--focused' : ''}">` +
      `<svg class="trial-marker-glyph" viewBox="0 0 16 16" fill="none" stroke="currentColor" ` +
      `stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${glyph}</svg></span>${countBadge}`,
    iconSize: [30, 34],
    iconAnchor: [15, 34],
    popupAnchor: [0, -30],
  })
}

// Renders the patient→site connector as a shallow quadratic-bezier arc
// (perpendicular offset from the midpoint, scaled to the leg's own length)
// instead of a straight line — the visual language the reference map uses
// for hub-to-destination routes. Lat/lon treated as flat Euclidean, which is
// fine at the ~50mi search radius this map ever actually draws across.
function arcPoints(from, to, segments = 24) {
  const [lat1, lon1] = from
  const [lat2, lon2] = to
  const midLat = (lat1 + lat2) / 2
  const midLon = (lon1 + lon2) / 2
  const dLat = lat2 - lat1
  const dLon = lon2 - lon1
  const offsetScale = 0.15
  // Perpendicular to (dLat, dLon) is (-dLon, dLat); scaling that directly by
  // offsetScale (rather than normalizing then re-multiplying by the leg's
  // own length) gives the same result with less arithmetic.
  const controlLat = midLat - dLon * offsetScale
  const controlLon = midLon + dLat * offsetScale

  const points = []
  for (let i = 0; i <= segments; i++) {
    const t = i / segments
    const lat = (1 - t) ** 2 * lat1 + 2 * (1 - t) * t * controlLat + t ** 2 * lat2
    const lon = (1 - t) ** 2 * lon1 + 2 * (1 - t) * t * controlLon + t ** 2 * lon2
    points.push([lat, lon])
  }
  return points
}

// Resolves a tier's live CSS custom property (light/dark aware) to a
// concrete color string — Leaflet's SVG renderer sets stroke via
// setAttribute, which doesn't reliably resolve var() the way a stylesheet
// rule does, so the color has to be read out and passed in as a literal.
function tierStrokeColor(tier) {
  if (typeof window === 'undefined') return '#8891e0'
  const value = getComputedStyle(document.documentElement).getPropertyValue(`--tier-${tier.toLowerCase()}`)
  return value.trim() || '#8891e0'
}

const PATIENT_ICON = L.divIcon({
  className: 'trial-marker-wrapper',
  html: '<span class="patient-marker-ring"></span><span class="patient-marker"></span>',
  iconSize: [18, 18],
  iconAnchor: [9, 9],
})

// Leaflet measures its container once at mount and caches that size/pixel
// origin — it won't notice later layout shifts (e.g. the results pane
// settling its final flex height once StatCards/TierSummaryRow mount, or the
// mobile chat pane collapsing to its max-height). invalidateSize() alone can
// leave stale tiles from the old (wrong) size behind, so every resize AND
// every points change re-applies the view afterward — re-centering forces
// Leaflet to fully reset its tile grid against the current, correct size.
function MapController({ points }) {
  const map = useMap()
  const signature = points.map((p) => `${p[0].toFixed(3)},${p[1].toFixed(3)}`).sort().join('|')

  const applyView = () => {
    map.invalidateSize()
    if (points.length === 0) return
    if (points.length === 1) {
      map.setView(points[0], 11)
      return
    }
    // Asymmetric, not uniform, padding — the floating toolbar (top) and trial
    // detail card (bottom-right) sit on top of the map now, so a symmetric
    // fitBounds pad can still tuck a pin directly underneath one of them.
    map.fitBounds(L.latLngBounds(points), {
      paddingTopLeft: [40, 210],
      paddingBottomRight: [40, 140],
      maxZoom: 12,
    })
  }

  useEffect(() => {
    applyView()
    const container = map.getContainer()
    const observer = new ResizeObserver(() => applyView())
    observer.observe(container)
    return () => observer.disconnect()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signature])

  return null
}

export default function TrialMap({ sitePins, patientLocation, focusedTrialId, onSelectTrial }) {
  const points = useMemo(() => {
    const pts = sitePins.map((s) => [s.lat, s.lon])
    if (patientLocation) pts.push([patientLocation.lat, patientLocation.lon])
    return pts
  }, [sitePins, patientLocation])

  const defaultCenter = patientLocation ? [patientLocation.lat, patientLocation.lon] : [39.8283, -98.5795]

  return (
    <div className="trial-map">
      <MapContainer
        center={defaultCenter}
        zoom={patientLocation ? 9 : 4}
        scrollWheelZoom
        zoomControl={false}
        attributionControl={false}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <ZoomControl position="bottomleft" />
        <AttributionControl position="bottomleft" prefix={false} />
        <MapController points={points} />

        {patientLocation &&
          sitePins.map((site) => {
            const tier = bestTier(site.trials)
            const isFocused = site.trials.some((t) => t.nctId === focusedTrialId)
            return (
              <Polyline
                key={`arc-${site.key}`}
                positions={arcPoints([patientLocation.lat, patientLocation.lon], [site.lat, site.lon])}
                pathOptions={{
                  color: tierStrokeColor(tier),
                  weight: isFocused ? 2.5 : 1.5,
                  opacity: isFocused ? 0.75 : 0.3,
                }}
                interactive={false}
              />
            )
          })}

        {patientLocation && (
          <Marker position={[patientLocation.lat, patientLocation.lon]} icon={PATIENT_ICON}>
            <Popup>Patient location</Popup>
          </Marker>
        )}

        {sitePins.map((site) => {
          const tier = bestTier(site.trials)
          const isFocused = site.trials.some((t) => t.nctId === focusedTrialId)
          const distance = patientLocation
            ? haversineMiles(patientLocation.lat, patientLocation.lon, site.lat, site.lon)
            : null

          return (
            <Marker
              key={site.key}
              position={[site.lat, site.lon]}
              icon={siteIcon(tier, site.trials.length, isFocused)}
              eventHandlers={
                site.trials.length === 1 ? { click: () => onSelectTrial(site.trials[0].nctId) } : undefined
              }
            >
              {site.trials.length > 1 && (
                <Popup>
                  <div className="trial-map-popup">
                    <p className="trial-map-popup-facility">
                      {site.facility}
                      {distance != null && <span> · {distance.toFixed(1)} mi</span>}
                    </p>
                    {site.trials.map((t) => (
                      <button
                        key={t.nctId}
                        type="button"
                        className={`trial-map-popup-trial trial-map-popup-trial--${t.tier.toLowerCase()}`}
                        onClick={() => onSelectTrial(t.nctId)}
                      >
                        {t.title}
                      </button>
                    ))}
                  </div>
                </Popup>
              )}
            </Marker>
          )
        })}
      </MapContainer>
    </div>
  )
}
