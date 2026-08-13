import SiteList from './SiteList.jsx'

function docGroups(profile, enrichment) {
  const available = []
  if (profile.condition || profile.condition_raw) available.push('Diagnosis details')
  if (profile.biomarkers?.length) available.push('Genomic / biomarker result')
  if (profile.prior_treatments?.length) available.push('Treatment history')

  const mentioned = enrichment?.documents_mentioned || []
  const obtain = ['Latest CBC / blood work', 'Latest imaging report', ...mentioned.filter((d) => !available.some((a) => a.toLowerCase().includes(d.toLowerCase())))]

  const confirm = []
  if (profile.ecog == null) confirm.push('ECOG performance status')
  confirm.push('Treatment washout dates')

  return [
    { label: 'Available', items: available.length ? available : ['Nothing on file yet'], glyph: available.length ? '✓' : '○', color: available.length ? 'var(--color-accent-700)' : 'var(--color-neutral-600)' },
    { label: 'You should obtain', items: obtain, glyph: '○', color: 'var(--color-neutral-800)' },
    { label: 'Your physician should confirm', items: confirm, glyph: '○', color: 'var(--color-neutral-800)' },
    { label: 'The study site will perform', items: ['Trial-specific laboratory tests', 'Formal eligibility assessment'], glyph: '○', color: 'var(--color-neutral-800)' },
  ]
}

export default function AccessPanel({ entry, profile, enrichment, enrichmentLoading, onBack, onReady }) {
  const { trial, verdicts = [] } = entry
  const site = trial.nearest_site

  return (
    <div className="tp-fade" style={{ display: 'flex', flexDirection: 'column', gap: 44 }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <button className="btn btn-ghost" onClick={onBack} style={{ alignSelf: 'flex-start', paddingLeft: 0, fontSize: 13 }}>
          ← Back to matches
        </button>
        <span style={{ fontSize: 11, letterSpacing: '.12em', textTransform: 'uppercase', color: 'var(--color-accent-2-700)' }}>
          Getting access to this study
        </span>
        <h3 style={{ fontSize: 27, margin: 0, lineHeight: 1.15 }}>{trial.title}</h3>
        <div style={{ fontSize: 15, color: 'var(--color-neutral-700)' }}>
          {(trial.phase || []).join(', ') || 'Phase not listed'} · {trial.nct_id}
          {site?.facility ? ` · ${site.facility}` : ''}
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <h4 style={{ fontSize: 19, margin: 0 }}>Documents and information</h4>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '26px 32px' }}>
          {docGroups(profile, enrichment).map((g) => (
            <div key={g.label} style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div className="tp-uppercase-label">{g.label}</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 15 }}>
                {g.items.map((item) => (
                  <div key={item} style={{ display: 'flex', gap: 9, alignItems: 'baseline', color: g.color }}>
                    <span>{g.glyph}</span>
                    <span>{item}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
          <h4 style={{ fontSize: 19, margin: 0 }}>Official trial information</h4>
          <span style={{ fontSize: 11, letterSpacing: '.1em', textTransform: 'uppercase', color: 'var(--color-accent-700)' }}>
            Source: ClinicalTrials.gov
          </span>
        </div>
        <SiteList locations={entry.locations} centralContacts={entry.central_contacts} nearestSite={site} />
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, flexWrap: 'wrap' }}>
          <h4 style={{ fontSize: 19, margin: 0, color: 'var(--color-neutral-800)' }}>Additional public access information</h4>
          <span style={{ fontSize: 11, letterSpacing: '.1em', textTransform: 'uppercase', color: 'var(--color-neutral-600)' }}>
            Not official registry information
          </span>
        </div>
        <p style={{ fontSize: 13, margin: 0, color: 'var(--color-neutral-700)', maxWidth: '66ch' }}>
          Collected from public hospital and sponsor pages via Bright Data. Useful for making contact; ClinicalTrials.gov remains
          authoritative for status, eligibility, location and contacts.
        </p>
        {enrichmentLoading && <p style={{ fontSize: 13, color: 'var(--color-neutral-600)' }}>Searching hospital and sponsor pages…</p>}
        {!enrichmentLoading && enrichment?.error && (
          <p style={{ fontSize: 13, color: 'var(--color-accent-2-700)' }}>Enrichment unavailable: {enrichment.error}</p>
        )}
        {!enrichmentLoading && enrichment && !enrichment.error && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 9, fontSize: 15, maxWidth: 640 }}>
            {enrichment.hospital_trial_page?.url && (
              <EnrichRow label={enrichment.hospital_trial_page.title || 'Hospital clinical trials page'} url={enrichment.hospital_trial_page.url} source="Bright Data" />
            )}
            {(enrichment.trial_office?.phone || enrichment.trial_office?.email || enrichment.trial_office?.contact_form) && (
              <EnrichRow
                label={`Trial office — ${[enrichment.trial_office.name, enrichment.trial_office.phone, enrichment.trial_office.email].filter(Boolean).join(' · ')}`}
                url={enrichment.trial_office.contact_form}
                source="Bright Data"
              />
            )}
            {enrichment.referral?.instructions && (
              <EnrichRow label={enrichment.referral.instructions} url={enrichment.referral.url} source="Bright Data" />
            )}
            {enrichment.sponsor_study_page && <EnrichRow label="Sponsor study page" url={enrichment.sponsor_study_page} source="Sponsor website" />}
            {enrichment.patient_resources?.map((url) => (
              <EnrichRow key={url} label="Patient resource" url={url} source="Bright Data" />
            ))}
            {!enrichment.hospital_trial_page?.url &&
              !enrichment.trial_office?.phone &&
              !enrichment.referral?.instructions &&
              !enrichment.sponsor_study_page &&
              !enrichment.patient_resources?.length && (
                <div style={{ color: 'var(--color-neutral-600)' }}>No additional public access information found for this site.</div>
              )}
          </div>
        )}
      </div>

      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        <button className="btn btn-primary" onClick={onReady} style={{ fontSize: 15, padding: '12px 20px' }}>
          Prepare access packet
        </button>
        <button className="btn btn-secondary" onClick={onBack}>Compare with other studies</button>
      </div>

      <details style={{ fontSize: 13, color: 'var(--color-neutral-600)' }}>
        <summary style={{ cursor: 'pointer' }}>Why this trial — full criteria detail</summary>
        <div style={{ paddingTop: 10 }}>
          {verdicts.map((v) => (
            <div key={v.rule_id} style={{ marginBottom: 6 }}>
              <strong style={{ color: v.verdict === 'FAIL' ? 'var(--color-accent-2-700)' : v.verdict === 'PASS' ? 'var(--color-accent-700)' : 'inherit' }}>
                {v.verdict}
              </strong>{' '}
              — {v.reason}
            </div>
          ))}
        </div>
      </details>
    </div>
  )
}

function EnrichRow({ label, url, source }) {
  return (
    <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
      <span style={{ flex: 1 }}>{url ? <a href={url} target="_blank" rel="noreferrer">{label}</a> : label}</span>
      <span style={{ fontSize: 11, letterSpacing: '.1em', textTransform: 'uppercase', color: 'var(--color-neutral-600)' }}>{source}</span>
    </div>
  )
}
