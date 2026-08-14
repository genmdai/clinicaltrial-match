import './StatCards.css'

export default function StatCards({ count, label, screened, total, condition }) {
  return (
    <div className="stat-cards">
      <div className="stat-card stat-card--primary">
        <span className="stat-card-number">{count}</span>
        <span className="stat-card-label">{label}</span>
      </div>
      <div className="stat-card">
        <span className="stat-card-number">
          {screened}
          <span className="stat-card-number-sub"> / {total}</span>
        </span>
        <span className="stat-card-label">screened{condition ? ` for ${condition}` : ''}</span>
      </div>
    </div>
  )
}
