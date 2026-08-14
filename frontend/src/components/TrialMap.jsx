import { useEffect, useMemo } from 'react'
import { AttributionControl, MapContainer, Marker, Popup, TileLayer, ZoomControl, useMap } from 'react-leaflet'
import L from 'leaflet'
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

function siteIcon(tier, isFocused) {
  return L.divIcon({
    className: 'trial-marker-wrapper',
    html: `<span class="trial-marker trial-marker--${tier.toLowerCase()}${isFocused ? ' trial-marker--focused' : ''}"></span>`,
    iconSize: [22, 22],
    iconAnchor: [11, 22],
    popupAnchor: [0, -20],
  })
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
              icon={siteIcon(tier, isFocused)}
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
