import './TopBar.css'

export default function TopBar({ onNewSearch, showBackToMatches, onBackToMatches, offline }) {
  return (
    <header className="top-bar">
      <div className="top-bar-left">
        <span className="top-bar-wordmark">Pathway</span>
        {showBackToMatches && (
          <button type="button" className="top-bar-nav-item" onClick={onBackToMatches}>
            ← Back to matches
          </button>
        )}
      </div>

      <div className="top-bar-right">
        {offline && <span className="top-bar-offline-badge">Offline demo data</span>}
        <button type="button" className="top-bar-new-search" onClick={onNewSearch} aria-label="New search" title="New search">
          +
        </button>
      </div>
    </header>
  )
}
