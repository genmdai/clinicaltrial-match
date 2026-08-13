// Official recruiting sites + central contacts, straight from the CT.gov record
// (contactsLocationsModule) — this is the source-of-truth contact info; Bright Data
// enrichment (AccessPanel) only adds what the registry doesn't carry.
export default function SiteList({ locations, centralContacts, nearestSite }) {
  const recruiting = (locations || []).filter((l) => (l.status || '').toUpperCase() === 'RECRUITING')
  const shown = recruiting.length ? recruiting : locations || []

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,minmax(0,1fr))', gap: '22px 28px' }}>
        <div>
          <div className="tp-uppercase-label" style={{ marginBottom: 4 }}>Nearest recruiting site</div>
          <div style={{ fontSize: 15 }}>
            {nearestSite?.facility
              ? `${nearestSite.facility}${nearestSite.city ? ', ' + nearestSite.city : ''}${nearestSite.state ? ', ' + nearestSite.state : ''}${nearestSite.distance_mi != null ? ` (${nearestSite.distance_mi} mi)` : ''}`
              : 'Not resolved — no patient location on file'}
          </div>
        </div>
        <div>
          <div className="tp-uppercase-label" style={{ marginBottom: 4 }}>Study status</div>
          <div style={{ fontSize: 15 }}>Recruiting</div>
        </div>
        <div>
          <div className="tp-uppercase-label" style={{ marginBottom: 4 }}>Official contact</div>
          {centralContacts?.length ? (
            <div style={{ fontSize: 15, lineHeight: 1.45 }}>
              {centralContacts[0].name}
              <br />
              <span style={{ fontSize: 13, color: 'var(--color-neutral-800)' }}>
                {[centralContacts[0].phone, centralContacts[0].email].filter(Boolean).join(' · ') || 'No direct contact listed'}
              </span>
            </div>
          ) : (
            <div style={{ fontSize: 15, color: 'var(--color-neutral-600)' }}>Not listed in registry</div>
          )}
        </div>
      </div>

      {shown.length > 1 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div className="tp-uppercase-label">All recruiting sites ({shown.length})</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 13, maxHeight: 160, overflowY: 'auto' }}>
            {shown.map((l, i) => (
              <div key={i}>
                {l.facility || 'Unnamed site'}
                {l.city ? `, ${l.city}` : ''}
                {l.state ? `, ${l.state}` : ''}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
