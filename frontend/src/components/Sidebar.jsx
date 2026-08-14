import './Sidebar.css'

export default function Sidebar({ onNewSearch, showBackToMatches, onBackToMatches, offline }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-top">
        <span className="sidebar-wordmark">Pathway</span>
        {showBackToMatches && (
          <button type="button" className="sidebar-nav-item" onClick={onBackToMatches}>
            ← Back to matches
          </button>
        )}
      </div>

      <div className="sidebar-bottom">
        {offline && <span className="sidebar-offline-badge">Offline demo data</span>}
        <button type="button" className="sidebar-cta" onClick={onNewSearch}>
          New search
        </button>
      </div>
    </aside>
  )
}
