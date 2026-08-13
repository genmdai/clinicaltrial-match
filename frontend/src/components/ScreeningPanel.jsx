import { useMemo, useState } from 'react'
import TrialCard from './TrialCard.jsx'
import { isTrialClean, trialFailsField } from '../domain.js'

export default function ScreeningPanel({ entries, poolCount, resolvedFields, question, onSelect, onRemoveField }) {
  const [query, setQuery] = useState('')

  const clean = useMemo(() => entries.filter(isTrialClean), [entries])

  const funnel = useMemo(() => {
    let running = clean.slice()
    return resolvedFields.map((field) => {
      const before = running.length
      running = running.filter((e) => !trialFailsField(e, field))
      return { field, before, after: running.length, cut: before - running.length }
    })
  }, [clean, resolvedFields])

  const matches = useMemo(() => {
    const q = query.trim().toLowerCase()
    const list = q
      ? clean.filter((e) => (e.trial.title + ' ' + e.trial.nct_id).toLowerCase().includes(q))
      : clean
    return list
  }, [clean, query])

  const remainingBar = poolCount ? Math.round((clean.length / poolCount) * 100) + '%' : '0%'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 44 }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 18 }}>
          <span className="tp-count" style={{ fontSize: 72, lineHeight: 0.9, letterSpacing: '-.03em' }}>{clean.length}</span>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 3, paddingBottom: 6 }}>
            <span style={{ fontSize: 19, fontFamily: 'var(--font-heading)', fontWeight: 400 }}>
              {clean.length === 1 ? 'study still open' : 'studies still open'}
            </span>
            <span style={{ fontSize: 13, color: 'var(--color-neutral-700)' }}>narrowed from {poolCount} recruiting studies found</span>
          </div>
        </div>
        <div style={{ height: 3, background: 'var(--color-neutral-300)', maxWidth: 520 }}>
          <div style={{ height: 3, background: 'var(--color-text)', width: remainingBar, transition: 'width .45s ease' }} />
        </div>

        {funnel.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 9, paddingTop: 4 }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) 86px 70px', gap: 12, alignItems: 'baseline' }}>
              <div className="tp-uppercase-label">Restriction applied</div>
              <div style={{ fontSize: 11, letterSpacing: '.12em', textTransform: 'uppercase', color: 'var(--color-neutral-600)', textAlign: 'right' }}>Ruled out</div>
              <div style={{ fontSize: 11, letterSpacing: '.12em', textTransform: 'uppercase', color: 'var(--color-neutral-600)', textAlign: 'right' }}>Left</div>
            </div>
            {funnel.map((s) => (
              <div key={s.field} className="tp-fade" style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) 86px 70px', gap: 12, alignItems: 'baseline' }}>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 9, minWidth: 0 }}>
                  <span style={{ fontSize: 15, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{s.field}</span>
                </div>
                <span className="tp-count" style={{ fontSize: 19, color: s.cut === 0 ? 'var(--color-neutral-600)' : 'var(--color-accent-2-700)', textAlign: 'right' }}>
                  {s.cut === 0 ? '—' : '−' + s.cut}
                </span>
                <span className="tp-count" style={{ fontSize: 21, color: s.after ? 'var(--color-text)' : 'var(--color-accent-2-700)', textAlign: 'right' }}>
                  {s.after}
                </span>
              </div>
            ))}
          </div>
        )}

        {question ? (
          <div style={{ display: 'grid', gridTemplateColumns: '200px minmax(0,1fr)', gap: 14, alignItems: 'baseline' }}>
            <div className="tp-uppercase-label" style={{ color: 'var(--color-accent-700)' }}>Next question</div>
            <span style={{ fontSize: 13, color: 'var(--color-accent-700)' }}>
              {question.label} — decides {question.affects} of the {matches.length} studies below
            </span>
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: '200px minmax(0,1fr)', gap: 14, alignItems: 'baseline' }}>
            <div className="tp-uppercase-label">No further questions</div>
            <span style={{ fontSize: 13, color: 'var(--color-neutral-800)' }}>
              Nothing else we could ask would separate these studies — the remaining differences are for a study team to confirm.
            </span>
          </div>
        )}

        {resolvedFields.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, paddingTop: 6 }}>
            <div className="tp-uppercase-label">Applied — click to remove</div>
            <div style={{ display: 'flex', gap: 7, flexWrap: 'wrap' }}>
              {resolvedFields.map((f) => (
                <button key={f} className="tp-filter" onClick={() => onRemoveField(f)} title="Remove this filter">
                  {f}
                  <span style={{ color: 'var(--color-accent-700)' }}>×</span>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 16, flexWrap: 'wrap' }}>
          <h2 style={{ fontSize: 27, margin: 0 }}>
            {matches.length} {matches.length === 1 ? 'study may be relevant' : 'studies may be relevant'}
          </h2>
          <input
            className="input"
            style={{ fontSize: 13, padding: '8px 12px', maxWidth: 260, marginLeft: 'auto' }}
            placeholder="Refine — title, NCT"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>

        {matches.length === 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 18, maxWidth: '56ch' }}>
            <h4 style={{ fontSize: 27, margin: 0 }}>No strong recruiting match with these answers</h4>
            <p style={{ fontSize: 15, lineHeight: 1.5, margin: 0, color: 'var(--color-neutral-800)' }}>
              Nothing in the current set is consistent with every answer. Recruiting status and criteria change often.
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 15, color: 'var(--color-neutral-800)' }}>
              <div><span style={{ marginRight: 10 }}>·</span>remove a filter above to widen the set</div>
              <div><span style={{ marginRight: 10 }}>·</span>answer "not sure" where you'd need a record to confirm</div>
            </div>
          </div>
        )}

        {matches.map((entry) => (
          <TrialCard key={entry.trial.nct_id} entry={entry} onSelect={onSelect} />
        ))}
      </div>
    </div>
  )
}
