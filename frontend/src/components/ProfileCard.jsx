import { useState } from 'react'
import { PROFILE_FIELDS, profileSummaryRows, profileToFieldValues, applyFieldEdit } from '../domain.js'

export default function ProfileCard({ profile, onChange, unverified, isClinician, clinicianDetail }) {
  const [editing, setEditing] = useState(false)
  const values = profileToFieldValues(profile)
  const title = (profile.condition || profile.condition_raw || 'Profile in progress').trim()

  return (
    <div className="card" style={{ padding: 'var(--space-4)', gap: 'var(--space-3)', boxShadow: 'var(--shadow-sm)' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 16 }}>
        <div>
          <div className="card-kicker">Your clinical profile</div>
          <div style={{ fontSize: 21, fontFamily: 'var(--font-heading)', fontWeight: 600, lineHeight: 1.2, paddingTop: 3 }}>{title}</div>
        </div>
        <button className="btn btn-ghost" onClick={() => setEditing((e) => !e)} style={{ fontSize: 13, color: 'var(--color-accent-700)', marginLeft: 'auto' }}>
          {editing ? 'Done' : 'Edit'}
        </button>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {editing ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {PROFILE_FIELDS.map((f) => (
              <div key={f.key} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <label className="tp-uppercase-label" style={{ fontWeight: 400 }}>{f.label}</label>
                <input
                  className="input"
                  style={{ background: '#fff', padding: '9px 12px' }}
                  placeholder={f.eg}
                  value={values[f.key]}
                  onChange={(e) => onChange(applyFieldEdit(profile, f.key, e.target.value))}
                />
              </div>
            ))}
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
            {profileSummaryRows(profile).map((r) => (
              <div key={r.label} className="tp-fade tp-rail">
                <div className="tp-uppercase-label">{r.label}</div>
                <div style={{ fontSize: 15, lineHeight: 1.45, color: r.present ? 'var(--color-text)' : 'var(--color-neutral-600)' }}>{r.value}</div>
              </div>
            ))}
          </div>
        )}

        {unverified?.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, paddingTop: 2 }}>
            <div className="tp-uppercase-label">Still unverified</div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {unverified.map((u) => (
                <span key={u} className="tag tag-outline">{u}</span>
              ))}
            </div>
          </div>
        )}

        {isClinician && clinicianDetail && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 5, paddingTop: 2 }}>
            <div className="tp-uppercase-label">Clinician detail</div>
            <div style={{ fontSize: 13, lineHeight: 1.6, color: 'var(--color-neutral-800)' }}>{clinicianDetail}</div>
          </div>
        )}
      </div>
    </div>
  )
}
