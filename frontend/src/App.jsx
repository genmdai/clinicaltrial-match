import { useEffect, useMemo, useRef, useState } from 'react'
import { extractProfile, matchTrials, composePacket, enrichTrialAccess } from './api.js'
import { emptyProfile, profileSummaryRows, collectQuestions, applyAnswer } from './domain.js'
import StartScreen from './components/StartScreen.jsx'
import ProfileCard from './components/ProfileCard.jsx'
import AssumptionsCard from './components/AssumptionsCard.jsx'
import ChatPane from './components/ChatPane.jsx'
import ScreeningPanel from './components/ScreeningPanel.jsx'
import AccessPanel from './components/AccessPanel.jsx'
import ReadyPanel from './components/ReadyPanel.jsx'
import ProgressStream from './components/ProgressStream.jsx'

const LOADING_STEPS = ['Searching recruiting trials…', 'Comparing eligibility criteria…', 'Checking recruiting sites…', 'Finalizing your matches…']

function initialState() {
  return {
    stage: 'start',
    mode: 'Patient',
    draft: '',
    profile: emptyProfile(),
    log: [],
    loadingStep: 0,
    matchEntries: [],
    matchError: null,
    dismissedFields: new Set(),
    resolvedFields: [],
    rechecking: false,
    selectedEntry: null,
    enrichment: { loading: false, data: null, error: null },
    packet: { loading: false, data: null, error: null },
    typed: '',
  }
}

export default function App() {
  const [s, setS] = useState(initialState)
  const chatRef = useRef(null)
  const artRef = useRef(null)
  const patch = (p) => setS((prev) => ({ ...prev, ...(typeof p === 'function' ? p(prev) : p) }))

  useEffect(() => {
    const el = chatRef.current
    if (el) requestAnimationFrame(() => { el.scrollTop = el.scrollHeight })
  }, [s.log, s.stage])

  const runMatch = async (profile) => {
    const res = await matchTrials(profile)
    if (res.error) {
      patch({ matchError: res.error, matchEntries: [] })
      return []
    }
    patch({ matchError: null, matchEntries: res.results || [] })
    return res.results || []
  }

  const begin = async (rawText) => {
    const text = (rawText || s.draft || '').trim() || 'I have stage IV lung cancer with EGFR exon 20. Chemotherapy stopped working.'
    patch({
      stage: 'loading',
      loadingStep: 0,
      log: [{ role: 'You', text }, { role: 'TrialPath', text: "I'm pulling recruiting studies and checking them against your information now." }],
    })

    const profileRes = await extractProfile(text)
    let profile
    if (profileRes.error) {
      profile = {
        ...emptyProfile(),
        condition_raw: text,
        condition: text,
        assumptions: [`Automatic extraction is unavailable right now (${profileRes.error}). Using your message as the diagnosis text — edit the profile fields below to refine it.`],
      }
    } else {
      profile = profileRes.profile
    }
    patch({ profile, loadingStep: 1 })

    const results = await runMatch(profile)
    patch({ loadingStep: 2 })
    await new Promise((r) => setTimeout(r, 250))
    patch({ loadingStep: 3 })
    await new Promise((r) => setTimeout(r, 250))

    const clean = results.filter((e) => !e.error && !(e.verdicts || []).some((v) => v.verdict === 'FAIL'))
    patch((prev) => ({
      stage: 'screening',
      log: [
        ...prev.log,
        {
          role: 'TrialPath',
          text: results.length
            ? `I found ${results.length} candidate ${results.length === 1 ? 'study' : 'studies'}; ${clean.length} still look consistent with what you've told me. A few more details will narrow it further.`
            : profileRes.error
              ? `I couldn't fully process that (${profileRes.error}). You can still fill in the profile below and I'll search once there's a condition to search for.`
              : "I couldn't find any recruiting studies for that condition — try adjusting the profile below.",
        },
      ],
    }))
  }

  const onProfileChange = async (nextProfile) => {
    patch({ profile: nextProfile })
  }

  const recheck = async (profile) => {
    patch({ rechecking: true })
    await runMatch(profile)
    patch({ rechecking: false })
  }

  const question = useMemo(() => {
    const qs = collectQuestions(s.matchEntries, s.dismissedFields)
    return qs[0] || null
  }, [s.matchEntries, s.dismissedFields])

  const onAnswerQuestion = async (value) => {
    if (!question) return
    if (value === 'unsure') {
      patch((prev) => ({
        dismissedFields: new Set([...prev.dismissedFields, question.field]),
        log: [...prev.log, { role: 'You', text: "Not sure." }, { role: 'TrialPath', text: "That's fine — I'll leave it open and flag it as needing verification." }],
      }))
      return
    }
    const nextProfile = applyAnswer(s.profile, question, value)
    patch((prev) => ({
      profile: nextProfile,
      resolvedFields: prev.resolvedFields.includes(question.field) ? prev.resolvedFields : [...prev.resolvedFields, question.field],
      log: [...prev.log, { role: 'You', text: String(value) }, { role: 'TrialPath', text: 'Noted — rechecking your matches.' }],
    }))
    await recheck(nextProfile)
  }

  const onRemoveResolvedField = (field) => {
    patch((prev) => ({ resolvedFields: prev.resolvedFields.filter((f) => f !== field) }))
  }

  const onSendTyped = () => {
    const text = s.typed.trim()
    if (!text) return
    patch((prev) => ({
      typed: '',
      log: [...prev.log, { role: 'You', text }, { role: 'TrialPath', text: 'Noted — use the question prompt above or edit your profile directly for anything that should change your matches.' }],
    }))
  }

  const selectTrial = async (entry) => {
    patch((prev) => ({
      stage: 'access',
      selectedEntry: entry,
      enrichment: { loading: true, data: null, error: null },
      log: [...prev.log, { role: 'You', text: `Let's look at ${entry.trial.title}.` }, { role: 'TrialPath', text: "I'll help you prepare to be screened for this study." }],
    }))
    if (typeof artRef.current?.scrollTo === 'function') artRef.current.scrollTo({ top: 0 })

    const site = entry.trial.nearest_site
    if (!site?.facility) {
      patch({ enrichment: { loading: false, data: null, error: 'No recruiting site resolved for this trial (no patient location on file).' } })
      return
    }
    const res = await enrichTrialAccess(
      { nct_id: entry.trial.nct_id, title: entry.trial.title, sponsor: entry.trial.sponsor || null },
      { facility: site.facility, city: site.city || null, state: site.state || null },
    )
    if (res.error) patch({ enrichment: { loading: false, data: null, error: res.error } })
    else patch({ enrichment: { loading: false, data: res.enrichment, error: null } })
  }

  const goReady = async () => {
    patch((prev) => ({
      stage: 'ready',
      packet: { loading: true, data: null, error: null },
      log: [...prev.log, { role: 'TrialPath', text: "Your packet is ready. It summarises what you've told me, what this study requires, and what's still outstanding." }],
    }))
    const { selectedEntry, profile } = s
    const res = await composePacket(profile, selectedEntry.trial, selectedEntry.verdicts)
    if (res.error) patch({ packet: { loading: false, data: null, error: res.error } })
    else patch({ packet: { loading: false, data: res.packet, error: null } })
  }

  const restart = () => setS(initialState())

  const unverified = [
    ...profileSummaryRows(s.profile).filter((r) => !r.present).map((r) => r.label),
    ...[...s.dismissedFields],
  ]

  const clinicianDetail = s.mode === 'Clinician'
    ? [
        s.profile.biomarkers?.length ? `Biomarkers: ${s.profile.biomarkers.join(', ')}` : null,
        s.profile.prior_treatments?.length ? `Prior treatment: ${s.profile.prior_treatments.map((t) => t.raw_mention).join('; ')}` : null,
        s.profile.ecog != null ? `ECOG ${s.profile.ecog}` : null,
        s.profile.treatment_line != null ? `Treatment line ${s.profile.treatment_line}` : null,
      ].filter(Boolean).join(' · ')
    : ''

  const quickAsks = [
    {
      label: 'What is still unknown about me?',
      onClick: () =>
        patch((prev) => ({
          log: [
            ...prev.log,
            { role: 'You', text: 'What is still unknown about me?' },
            {
              role: 'TrialPath',
              text: unverified.length
                ? `Still open: ${unverified.slice(0, 5).join(', ')}.`
                : "Nothing outstanding right now — your profile covers everything I can check.",
            },
          ],
        })),
    },
    {
      label: 'Explain these studies in plain language',
      onClick: () =>
        patch((prev) => ({
          log: [
            ...prev.log,
            { role: 'You', text: 'Explain these studies in plain language.' },
            {
              role: 'TrialPath',
              text: 'Each study lists inclusion/exclusion criteria pulled straight from its ClinicalTrials.gov record. I check each one against your profile — green means confirmed, a question mark means I need more information, and a study drops out entirely the first time a criterion is clearly not met.',
            },
          ],
        })),
    },
  ]

  return (
    <div className="tp-app" style={{ height: '100vh', minHeight: 480, display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: s.stage === 'start' ? 'none' : 'flex', alignItems: 'center', gap: 16, padding: '16px 32px', flex: 'none' }}>
        <span style={{ fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 19 }}>TrialPath</span>
        <span style={{ fontSize: 11, letterSpacing: '.14em', textTransform: 'uppercase', color: 'var(--color-neutral-600)', marginRight: 'auto' }}>
          {{ start: 'Start', loading: 'Screening', screening: 'Adaptive screening', access: 'Trial access', ready: 'Ready for screening' }[s.stage]}
        </span>
        {s.stage !== 'start' && (
          <button className="btn btn-ghost" onClick={restart} style={{ fontSize: 13 }}>Start over</button>
        )}
        <span className="seg">
          <button
            className="seg-opt"
            onClick={() => patch({ mode: 'Patient' })}
            style={{ border: 0, background: s.mode === 'Clinician' ? 'transparent' : 'var(--color-accent)', color: s.mode === 'Clinician' ? 'var(--color-text)' : 'var(--color-bg)' }}
          >
            Patient
          </button>
          <button
            className="seg-opt"
            onClick={() => patch({ mode: 'Clinician' })}
            style={{ border: 0, borderLeft: '1px solid var(--color-divider)', background: s.mode === 'Clinician' ? 'var(--color-accent)' : 'transparent', color: s.mode === 'Clinician' ? 'var(--color-bg)' : 'var(--color-text)' }}
          >
            Clinician
          </button>
        </span>
      </div>

      {s.stage === 'start' && (
        <StartScreen draft={s.draft} onDraftChange={(draft) => patch({ draft })} onSubmit={() => begin(s.draft)} />
      )}

      {s.stage !== 'start' && (
        <div style={{ flex: 1, minHeight: 0, display: 'grid', gridTemplateColumns: 'minmax(420px,44%) minmax(0,56%)' }}>
          <ChatPane
            chatRef={chatRef}
            messages={s.log}
            isLoading={s.stage === 'loading' || s.rechecking}
            loadingMessage={s.rechecking ? 'Rechecking eligibility…' : LOADING_STEPS[s.loadingStep]}
            question={s.stage === 'screening' ? question : null}
            onAnswer={onAnswerQuestion}
            quickAsks={s.stage === 'screening' ? quickAsks : []}
            typed={s.typed}
            onTypedChange={(typed) => patch({ typed })}
            onSendTyped={onSendTyped}
            inputPlaceholder={s.stage === 'access' || s.stage === 'ready' ? 'Ask about this study or the site' : 'Type your answer, or ask a question'}
          >
            <ProfileCard
              profile={s.profile}
              onChange={onProfileChange}
              unverified={unverified}
              isClinician={s.mode === 'Clinician'}
              clinicianDetail={clinicianDetail}
            />
            <AssumptionsCard assumptions={s.profile.assumptions} />
          </ChatPane>

          <div
            ref={artRef}
            className="tp-scroll"
            id="tp-artifacts"
            style={{
              minHeight: 0,
              padding: '20px 32px 48px 40px',
              background: 'linear-gradient(90deg, var(--color-divider) 0 1px, transparent 1px 100%)',
              display: 'flex',
              flexDirection: 'column',
              gap: 44,
            }}
          >
            {s.stage === 'loading' && <ProgressStream steps={LOADING_STEPS} activeIndex={s.loadingStep} />}

            {s.stage === 'screening' && s.matchError && (
              <p style={{ fontSize: 13, color: 'var(--color-accent-2-700)' }}>Search failed: {s.matchError}</p>
            )}

            {s.stage === 'screening' && !s.matchError && (
              <ScreeningPanel
                entries={s.matchEntries.filter((e) => !e.error)}
                poolCount={s.matchEntries.length}
                resolvedFields={s.resolvedFields}
                question={question}
                onSelect={selectTrial}
                onRemoveField={onRemoveResolvedField}
              />
            )}

            {s.stage === 'access' && s.selectedEntry && (
              <AccessPanel
                entry={s.selectedEntry}
                profile={s.profile}
                enrichment={s.enrichment.error ? { error: s.enrichment.error } : s.enrichment.data}
                enrichmentLoading={s.enrichment.loading}
                onBack={() => patch({ stage: 'screening' })}
                onReady={goReady}
              />
            )}

            {s.stage === 'ready' && s.selectedEntry && (
              <ReadyPanel
                entry={s.selectedEntry}
                packet={s.packet.data}
                packetLoading={s.packet.loading}
                packetError={s.packet.error}
              />
            )}
          </div>
        </div>
      )}
    </div>
  )
}
