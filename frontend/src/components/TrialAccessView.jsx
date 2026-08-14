import { useEffect, useState } from 'react'
import OutlookRing from './OutlookRing'
import SiteList from './SiteList'
import './TrialAccessView.css'

// Static, deliberately conservative: only maps a field to a document type
// when a document genuinely evidences that fact. Fields with no natural
// supporting document (age, ecog, unmapped "other") fall back to a generic
// "Medical records" label rather than fabricating a specific document type.
const DOCUMENT_BY_FIELD = {
  biomarker: 'Genomic testing report',
  prior_therapy_class: 'Treatment history',
  treatment_naive: 'Treatment history',
  condition: 'Pathology report',
}

const GENERIC_OBTAIN = ['Latest CBC / blood work', 'Latest imaging report']
const SITE_WILL_PERFORM = ['Trial-specific laboratory tests', 'Formal eligibility assessment']

export default function TrialAccessView({ trial, onOpenCompose, onFetchPublicAccessLinks }) {
  const [links, setLinks] = useState(null)
  const [linksLoading, setLinksLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLinksLoading(true)
    onFetchPublicAccessLinks()
      .then((result) => {
        if (!cancelled) setLinks(result)
      })
      .finally(() => {
        if (!cancelled) setLinksLoading(false)
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [trial.summary.nct_id])

  const { summary, study, rules, verdicts, contact, outlook, nearest_sites: nearestSites } = trial
  const ruleById = Object.fromEntries(rules.map((r) => [r.rule_id, r]))
  const statusModule = study?.protocolSection?.statusModule ?? {}

  const confirmed = verdicts.filter((v) => v.verdict === 'PASS')
  const unresolved = verdicts.filter((v) => v.verdict === 'UNKNOWN')

  const availableDocs = [
    ...new Set(confirmed.map((v) => DOCUMENT_BY_FIELD[ruleById[v.rule_id]?.field] || 'Medical records')),
  ]
  const physicianShouldConfirm = unresolved.map((v) => v.reason)

  return (
    <div className="trial-access-view">
      <p className="trial-access-eyebrow">Getting access to this study</p>
      <h2 className="trial-access-title">{summary.title}</h2>
      <p className="trial-access-subtitle">
        {(summary.phase || []).join(', ') || 'Phase n/a'} · {summary.nct_id}
        {summary.nearest_site?.facility ? ` · ${summary.nearest_site.facility}` : ''}
        {summary.nearest_site?.distance_mi != null ? `, ${summary.nearest_site.distance_mi} miles away` : ''}
      </p>

      {outlook?.components && <OutlookRing components={outlook.components} />}

      <h3 className="trial-access-section-heading">Documents and information</h3>
      <div className="trial-access-grid">
        <div>
          <h4>Available</h4>
          {availableDocs.length === 0 ? (
            <p className="trial-access-empty">None confirmed yet.</p>
          ) : (
            <ul className="trial-access-check-list">
              {availableDocs.map((d) => (
                <li key={d}>✓ {d}</li>
              ))}
            </ul>
          )}
        </div>
        <div>
          <h4>You should obtain</h4>
          <ul className="trial-access-circle-list">
            {GENERIC_OBTAIN.map((d) => (
              <li key={d}>○ {d}</li>
            ))}
          </ul>
        </div>
        <div>
          <h4>Your physician should confirm</h4>
          {physicianShouldConfirm.length === 0 ? (
            <p className="trial-access-empty">Nothing outstanding.</p>
          ) : (
            <ul className="trial-access-circle-list">
              {physicianShouldConfirm.map((r, i) => (
                <li key={i}>○ {r}</li>
              ))}
            </ul>
          )}
        </div>
        <div>
          <h4>The study site will perform</h4>
          <ul className="trial-access-circle-list">
            {SITE_WILL_PERFORM.map((d) => (
              <li key={d}>○ {d}</li>
            ))}
          </ul>
        </div>
      </div>

      <h3 className="trial-access-section-heading">Official trial information</h3>
      <p className="trial-access-source">Source: ClinicalTrials.gov</p>
      <div className="trial-access-grid trial-access-grid--three">
        <div>
          <h4>Recruiting site</h4>
          <p>{summary.nearest_site?.facility || 'Not listed'}</p>
        </div>
        <div>
          <h4>Study status</h4>
          <p>{statusModule.overallStatus || 'Unknown'}</p>
        </div>
        <div>
          <h4>Official contact</h4>
          <p>{contact?.name || 'Not listed'}</p>
          {contact?.phone && <p>{contact.phone}</p>}
          {contact?.email && <p>{contact.email}</p>}
        </div>
      </div>
      <a
        className="trial-access-registry-link"
        href={`https://clinicaltrials.gov/study/${summary.nct_id}`}
        target="_blank"
        rel="noreferrer"
      >
        View official ClinicalTrials.gov study
      </a>

      <h3 className="trial-access-section-heading">Nearby sites</h3>
      <SiteList sites={nearestSites} />

      <div className="trial-access-actions">
        <button type="button" className="btn-primary" onClick={onOpenCompose}>
          Prepare access packet
        </button>
        <button type="button" className="btn-secondary" onClick={onOpenCompose}>
          Contact study team
        </button>
      </div>

      <h3 className="trial-access-section-heading">Additional public access information</h3>
      <p className="trial-access-source">
        Not official registry information — collected from public hospital and sponsor pages. Useful for making
        contact; ClinicalTrials.gov remains authoritative for status, eligibility, location and contacts.
      </p>
      {linksLoading && <p className="trial-access-empty">Looking for public access information…</p>}
      {!linksLoading && links?.error === 'not_configured' && (
        <p className="trial-access-empty">Public access lookup isn't configured for this deployment.</p>
      )}
      {!linksLoading && links?.error && links.error !== 'not_configured' && (
        <p className="trial-access-empty">Couldn't look this up right now ({links.error}).</p>
      )}
      {!linksLoading && !links?.error && (!links?.results || links.results.length === 0) && (
        <p className="trial-access-empty">No additional public links found.</p>
      )}
      {!linksLoading && links?.results && links.results.length > 0 && (
        <ul className="trial-access-link-list">
          {links.results.map((r, i) => (
            <li key={i}>
              <a href={r.url} target="_blank" rel="noreferrer">
                {r.title}
              </a>
              <span className="trial-access-link-source">{r.source_tag}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
