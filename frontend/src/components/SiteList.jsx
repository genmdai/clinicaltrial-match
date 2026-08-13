import './SiteList.css'

export default function SiteList({ sites }) {
  if (!sites || sites.length === 0) {
    return <p className="site-list-empty">No nearby site data — add a ZIP code to see distances.</p>
  }

  return (
    <ul className="site-list">
      {sites.map((site, i) => {
        const contact = (site.contacts || [])[0]
        return (
          <li className="site-row" key={i}>
            <div className="site-main">
              <span className="site-facility">{site.facility || 'Site name not listed'}</span>
              <span className="site-distance">{site.distance_mi != null ? `${site.distance_mi} mi` : ''}</span>
            </div>
            <div className="site-meta">
              {[site.city, site.state].filter(Boolean).join(', ')}
              {site.status ? ` · ${site.status}` : ''}
            </div>
            {contact && (contact.phone || contact.email) && (
              <div className="site-contact">
                {contact.phone && <span>{contact.phone}</span>}
                {contact.email && <span>{contact.email}</span>}
              </div>
            )}
          </li>
        )
      })}
    </ul>
  )
}
