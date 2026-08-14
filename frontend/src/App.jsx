import { useEffect, useReducer, useRef, useState } from 'react'
import { compose, extractProfile, matchTrials, patchProfile, publicAccessLinks, screen } from './api'
import AssumptionsCard from './components/AssumptionsCard'
import { conversationReducer, initialConversationState } from './conversationReducer'
import ChatIntroCard from './components/ChatIntroCard'
import ComposeDrawer from './components/ComposeDrawer'
import LoadingSteps from './components/LoadingSteps'
import ProgressStream from './components/ProgressStream'
import RestrictionLedger from './components/RestrictionLedger'
import ScreeningQuestion from './components/ScreeningQuestion'
import StatCards from './components/StatCards'
import TierSummaryRow from './components/TierSummaryRow'
import TopBar from './components/TopBar'
import TrialAccessView from './components/TrialAccessView'
import TrialCard from './components/TrialCard'
import TrialMap from './components/TrialMap'
import { formatQuestionText } from './questionText'
import './App.css'

const INITIAL_GREETING =
  "Tell me about the patient's situation — condition, treatments tried, age, and a " +
  "location (ZIP code, or city/country) if you'd like nearby sites."

let nextId = 0
const uid = () => `m${nextId++}`

// Max recruiting sites plotted per trial on the map — mirrors geo.py's
// nearest_sites(n=3) convention (same cap TrialCard already used for its
// single "nearest site" line). Without this, a single large multi-country
// trial can list 1000+ recruiting sites and bury the map in pins.
const MAX_SITES_PER_TRIAL = 3

// Mirrors backend/tools/geo.py's haversine_miles — used to pick each trial's
// nearest sites for the map when a patient location is known.
function haversineMiles(lat1, lon1, lat2, lon2) {
  const R = 3958.8
  const toRad = (d) => (d * Math.PI) / 180
  const dLat = toRad(lat2 - lat1)
  const dLon = toRad(lon2 - lon1)
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2
  return 2 * R * Math.asin(Math.sqrt(a))
}

function clusterLabel(question) {
  if (!question) return ''
  if (question.cluster_key === '__travel_radius__') return 'Travel radius'
  const marker = question.cluster_key.startsWith('biomarker:') ? question.cluster_key.slice('biomarker:'.length) : null
  if (marker) return `${marker} status`
  const byField = {
    age: 'Age', ecog: 'ECOG status', treatment_naive: 'Prior treatment',
    prior_therapy_class: 'Prior therapy class', condition: 'Diagnosis',
  }
  return byField[question.field] || question.field
}

export default function App() {
  const [chatLog, setChatLog] = useState([{ id: uid(), role: 'bot', text: INITIAL_GREETING }])
  const [input, setInput] = useState('')
  const [conv, dispatch] = useReducer(conversationReducer, initialConversationState)
  const profile = conv.profile
  const [progressMessages, setProgressMessages] = useState([])
  const [parseProgress, setParseProgress] = useState(null)
  const [matching, setMatching] = useState(false)
  const [searched, setSearched] = useState(false)
  const [totalCount, setTotalCount] = useState(null)
  const [conditionSearched, setConditionSearched] = useState(null)
  const [candidateTrials, setCandidateTrials] = useState([])
  const [trialResults, setTrialResults] = useState({})
  const [trialErrors, setTrialErrors] = useState({})
  const [answers, setAnswers] = useState([])
  const [screenState, setScreenState] = useState(null)
  const [offlineMode, setOfflineMode] = useState(false)
  const [selectedTrialId, setSelectedTrialId] = useState(null)
  const [composeTrialId, setComposeTrialId] = useState(null)
  const [focusedTrialId, setFocusedTrialId] = useState(null)

  const trialResultsRef = useRef({})
  const baseProfileRef = useRef(null)
  const patientLocation = useRef({ lat: null, lon: null })

  const addMessage = (role, text) => setChatLog((log) => [...log, { id: uid(), role, text }])

  const buildTrialsPayload = (snapshot) =>
    Object.values(snapshot).map((t) => ({
      nct_id: t.nct_id,
      rules: t.rules,
      status_module: t.status_module,
      locations: t.locations,
      contact: t.contact,
      nearest_recruiting_distance_mi: t.summary?.nearest_recruiting_distance_mi ?? null,
    }))

  const runScreen = async (nextAnswers, opts = {}) => {
    const snapshot = opts.trialsSnapshot ?? trialResultsRef.current
    const baseProfile = opts.baseProfile ?? baseProfileRef.current
    const location = opts.location ?? patientLocation.current
    const trialsPayload = buildTrialsPayload(snapshot)
    if (trialsPayload.length === 0) return

    const result = await screen({
      baseProfile, answers: nextAnswers, trials: trialsPayload,
      patientLat: location.lat, patientLon: location.lon,
    })
    if (result.error) {
      addMessage('bot', `Couldn't update the screening: ${result.error}`)
      return
    }
    setAnswers(nextAnswers)
    setScreenState(result)
    if (nextAnswers.length === 0) {
      addMessage('bot', `${result.open_trial_ids.length} of ${snapshot ? Object.keys(snapshot).length : 0} studies still open.`)
    }
  }

  const runMatch = async (matchProfile) => {
    baseProfileRef.current = matchProfile
    trialResultsRef.current = {}
    setMatching(true)
    setSearched(true)
    setProgressMessages([])
    setParseProgress(null)
    setCandidateTrials([])
    setTrialResults({})
    setTrialErrors({})
    setAnswers([])
    setScreenState(null)
    setSelectedTrialId(null)
    setFocusedTrialId(null)
    setTotalCount(null)
    setConditionSearched(null)

    let doneLat = null
    let doneLon = null

    await matchTrials(matchProfile, 50.0, (event) => {
      if (event.type === 'progress') {
        setProgressMessages((m) => [...m, event.message])
      } else if (event.type === 'parse_progress') {
        setParseProgress({ completed: event.completed, total: event.total })
      } else if (event.type === 'candidates') {
        setOfflineMode(event.offline)
        setTotalCount(event.total_count)
        setConditionSearched(event.condition)
        setCandidateTrials(event.trials)
      } else if (event.type === 'trial_ready') {
        trialResultsRef.current = { ...trialResultsRef.current, [event.nct_id]: event }
        setTrialResults((r) => ({ ...r, [event.nct_id]: event }))
      } else if (event.type === 'trial_error') {
        setTrialErrors((e) => ({ ...e, [event.nct_id]: event.message }))
      } else if (event.type === 'done') {
        doneLat = event.patient_lat
        doneLon = event.patient_lon
        patientLocation.current = { lat: doneLat, lon: doneLon }
        setOfflineMode(event.offline)
        setMatching(false)
      } else if (event.type === 'error') {
        addMessage('bot', `I couldn't finish that search: ${event.message}`)
        setMatching(false)
      }
    })

    if (Object.keys(trialResultsRef.current).length > 0) {
      await runScreen([], {
        trialsSnapshot: trialResultsRef.current,
        baseProfile: matchProfile,
        location: { lat: doneLat, lon: doneLon },
      })
    }
  }

  const extractAndMatch = async (text) => {
    const result = await extractProfile(text)
    if (result.error) {
      addMessage('bot', `I had trouble reading that: ${result.error}`)
      return
    }
    const extracted = result.profile
    dispatch({ type: 'EXTRACTION_RESOLVED', profile: extracted })
    if ((extracted.gaps ?? []).some((g) => g.required)) {
      // The structured intake form below now gates the search — no more
      // concatenating the next chat message onto this narrative and
      // re-running full extraction on the combined blob. Optional gaps
      // (e.g. missing biomarker status) don't reach this branch — they're
      // shown in the form too, but never block a clean narrative from
      // searching immediately.
      addMessage('bot', "I need a bit more information before I can search — see the form below.")
      return
    }
    runMatch(extracted)
  }

  // A gap answer patches just that field via /patch-profile — never a full
  // narrative re-extraction. Once no gaps remain, the form's own submit
  // button (not this handler) advances to /match.
  const handleResolveGap = async (gapId, field, text) => {
    const result = await patchProfile(profile, [{ gap_id: gapId, field, text }])
    if (result.error) {
      addMessage('bot', `Couldn't save that answer: ${result.error}`)
      return
    }
    dispatch({ type: 'PROFILE_PATCHED', profile: result.profile })
  }

  // AssumptionsCard's submit button: "Search trials" the first time (gaps
  // just cleared) or "Update and re-search" on any later manual edit.
  const handleConfirmProfile = (edited) => {
    dispatch({ type: 'PROFILE_EDITED', profile: edited })
    runMatch(edited)
  }

  const handleAnswerQuestion = async (answerText) => {
    const nq = screenState?.next_question
    if (!nq) return
    // ScreeningQuestion only ever shows the CURRENT question live — without
    // archiving it here, the transcript ends up as a wall of undifferentiated
    // answer pills once several questions have been answered in a row, with
    // no record of what each one was answering.
    addMessage('bot', formatQuestionText(nq))
    addMessage('user', answerText)
    const entry = {
      cluster_key: nq.cluster_key,
      field: nq.field,
      rule_id: nq.rule_id ?? null,
      text: answerText,
      ledger_label: clusterLabel(nq),
    }
    await runScreen([...answers, entry])
  }

  const handleRetractAnswer = async (index) => {
    await runScreen(answers.filter((_, i) => i !== index))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    const text = input.trim()
    if (!text) return
    setInput('')

    const nq = screenState?.next_question
    if (nq && nq.answer_mode !== 'choice') {
      await handleAnswerQuestion(text)
      return
    }

    addMessage('user', text)
    await extractAndMatch(text)
  }

  const openTrialIds = new Set(screenState?.open_trial_ids ?? [])

  const getTrialView = (nctId) => {
    const base = trialResults[nctId]
    if (!base) return null
    const scored = screenState?.trials?.[nctId]
    return {
      summary: base.summary,
      study: { protocolSection: { statusModule: base.status_module, contactsLocationsModule: { locations: base.locations } } },
      rules: base.rules,
      verdicts: scored ? scored.verdicts : base.verdicts,
      rollup: scored ? scored.rollup : base.rollup,
      outlook: scored ? scored.outlook : base.outlook,
      nearest_sites: base.nearest_sites,
      contact: base.contact,
    }
  }

  const visibleTrials = candidateTrials.filter((t) => {
    if (trialErrors[t.nct_id]) return false
    if (!screenState) return true // still scoring — show as skeleton
    return openTrialIds.has(t.nct_id)
  })

  const tierCounts = visibleTrials.reduce((acc, t) => {
    const view = getTrialView(t.nct_id)
    if (view) acc[view.outlook.tier] = (acc[view.outlook.tier] || 0) + 1
    return acc
  }, {})

  const composeTrial = composeTrialId ? getTrialView(composeTrialId) : null
  const selectedTrial = selectedTrialId ? getTrialView(selectedTrialId) : null
  const focusedTrial = focusedTrialId ? getTrialView(focusedTrialId) : null

  // Map pins: each visible trial contributes at most its MAX_SITES_PER_TRIAL
  // nearest RECRUITING, geo-located sites (nearest to the patient when a
  // location is known, otherwise just the first few) — a single large
  // multi-country trial can otherwise list 1000+ recruiting sites and bury
  // the map in pins for everyone else. Sites shared by more than one trial
  // (common — same hospital, several studies) collapse into a single pin
  // listing every trial there.
  const patientLatLon = patientLocation.current.lat != null ? patientLocation.current : null
  const sitesByKey = new Map()
  visibleTrials.forEach((t) => {
    const view = getTrialView(t.nct_id)
    if (!view) return
    const locations = view.study.protocolSection.contactsLocationsModule.locations ?? []
    const recruiting = locations.filter((loc) => loc.geoPoint && loc.status === 'RECRUITING')
    if (patientLatLon) {
      recruiting.sort(
        (a, b) =>
          haversineMiles(patientLatLon.lat, patientLatLon.lon, a.geoPoint.lat, a.geoPoint.lon) -
          haversineMiles(patientLatLon.lat, patientLatLon.lon, b.geoPoint.lat, b.geoPoint.lon),
      )
    }
    recruiting.slice(0, MAX_SITES_PER_TRIAL).forEach((loc) => {
      const key = `${loc.geoPoint.lat.toFixed(4)},${loc.geoPoint.lon.toFixed(4)}`
      let site = sitesByKey.get(key)
      if (!site) {
        site = { key, lat: loc.geoPoint.lat, lon: loc.geoPoint.lon, facility: loc.facility, trials: [] }
        sitesByKey.set(key, site)
      }
      site.trials.push({ nctId: t.nct_id, title: view.summary.title, tier: view.outlook.tier })
    })
  })
  const sitePins = Array.from(sitesByKey.values())

  // If narrowing the scope drops the focused trial out of openTrialIds, its
  // pin no longer exists — don't leave a stale trial card in the panel.
  useEffect(() => {
    if (focusedTrialId && screenState && !openTrialIds.has(focusedTrialId)) {
      setFocusedTrialId(null)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [screenState])

  const handleCompose = async (variant) => {
    if (!composeTrial) return { error: 'No trial selected.' }
    return compose({
      variant,
      profile,
      nctId: composeTrial.summary.nct_id,
      verdicts: composeTrial.verdicts,
      contact: composeTrial.contact,
      trialTitle: composeTrial.summary.title,
      study: composeTrial.study,
      nearestSite: composeTrial.nearest_sites?.[0] ?? null,
    })
  }

  const handleNewSearch = () => {
    trialResultsRef.current = {}
    baseProfileRef.current = null
    patientLocation.current = { lat: null, lon: null }
    setChatLog([{ id: uid(), role: 'bot', text: INITIAL_GREETING }])
    setInput('')
    dispatch({ type: 'RESET' })
    setProgressMessages([])
    setMatching(false)
    setSearched(false)
    setTotalCount(null)
    setConditionSearched(null)
    setCandidateTrials([])
    setTrialResults({})
    setTrialErrors({})
    setAnswers([])
    setScreenState(null)
    setOfflineMode(false)
    setSelectedTrialId(null)
    setComposeTrialId(null)
    setFocusedTrialId(null)
  }

  const handleFetchPublicAccessLinks = () => {
    if (!selectedTrial) return Promise.resolve({ results: [], error: 'no_trial_selected' })
    return publicAccessLinks({
      nctId: selectedTrial.summary.nct_id,
      facilityName: selectedTrial.contact?.facility || selectedTrial.nearest_sites?.[0]?.facility || null,
      sponsorName: selectedTrial.contact?.contact_source === 'sponsor_only' ? selectedTrial.contact?.name : null,
    })
  }

  return (
    <div className="app-shell">
      <div className="app-main">
        <TopBar
          onNewSearch={handleNewSearch}
          showBackToMatches={Boolean(selectedTrial)}
          onBackToMatches={() => setSelectedTrialId(null)}
          offline={offlineMode}
        />

        {selectedTrial ? (
          <TrialAccessView
            trial={selectedTrial}
            onOpenCompose={() => setComposeTrialId(selectedTrial.summary.nct_id)}
            onFetchPublicAccessLinks={handleFetchPublicAccessLinks}
          />
        ) : (
          <div className="app-panes">
            <section className="chat-pane">
              <div className="chat-log">
                {chatLog.length === 1 ? (
                  <ChatIntroCard text={chatLog[0].text} />
                ) : (
                  chatLog.map((m) => (
                    <div key={m.id} className={`chat-message chat-message--${m.role}`}>
                      {m.text}
                    </div>
                  ))
                )}

                {profile && (
                  <AssumptionsCard profile={profile} onResolveGap={handleResolveGap} onConfirm={handleConfirmProfile} />
                )}

                {(matching || progressMessages.length > 0) && (
                  <ProgressStream messages={progressMessages} active={matching} />
                )}

                {screenState && (
                  <ScreeningQuestion
                    key={screenState.next_question?.cluster_key ?? 'none'}
                    question={screenState.next_question}
                    noFurtherQuestions={screenState.no_further_questions}
                    onAnswer={handleAnswerQuestion}
                  />
                )}
              </div>

              <form className="chat-input-row" onSubmit={handleSubmit}>
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder={
                    screenState?.next_question && screenState.next_question.answer_mode !== 'choice'
                      ? 'Type your answer…'
                      : "Describe the patient's situation…"
                  }
                />
                <button type="submit" className="btn-primary">
                  Send
                </button>
              </form>
            </section>

            <section className={`results-pane ${candidateTrials.length > 0 ? 'results-pane--map' : ''}`}>
              {!searched && <p className="results-empty">Trial matches will appear here once you describe the patient.</p>}

              {searched && candidateTrials.length === 0 && !matching && (
                <p className="results-empty">
                  No recruiting studies found{conditionSearched ? ` for ${conditionSearched}` : ''} — try broadening
                  the description.
                </p>
              )}

              {matching && <LoadingSteps messages={progressMessages} active={matching} liveProgress={parseProgress} />}

              {candidateTrials.length > 0 && (
                <div className="map-stage">
                  <TrialMap
                    sitePins={sitePins}
                    patientLocation={patientLatLon}
                    focusedTrialId={focusedTrialId}
                    onSelectTrial={setFocusedTrialId}
                  />

                  <div className="map-toolbar">
                    <StatCards
                      count={screenState ? openTrialIds.size : candidateTrials.length}
                      label={screenState ? 'studies still open' : 'studies found'}
                      screened={candidateTrials.length}
                      total={totalCount ?? candidateTrials.length}
                      condition={conditionSearched}
                    />
                    <TierSummaryRow counts={tierCounts} />
                    {answers.length > 0 && (
                      <RestrictionLedger
                        answers={answers}
                        ledger={screenState?.ledger ?? []}
                        onRemove={handleRetractAnswer}
                      />
                    )}
                  </div>

                  {focusedTrial ? (
                    <div className="map-detail">
                      <button
                        type="button"
                        className="map-detail-close"
                        onClick={() => setFocusedTrialId(null)}
                        aria-label="Close trial details"
                      >
                        ×
                      </button>
                      <div className="map-detail-panel">
                        <TrialCard
                          trial={focusedTrial}
                          onSelectTrial={() => setSelectedTrialId(focusedTrialId)}
                          onOpenCompose={() => setComposeTrialId(focusedTrialId)}
                        />
                      </div>
                    </div>
                  ) : (
                    <p className="map-hint">
                      {screenState ? 'Click a pin on the map to view trial details.' : 'Scoring trials…'}
                    </p>
                  )}
                </div>
              )}
            </section>
          </div>
        )}

        <footer className="disclaimer-bar">
          Informational only — not medical advice. Eligibility is determined by the trial team. Confirm everything
          with your care team.
        </footer>

        {composeTrial && <ComposeDrawer onCompose={handleCompose} onClose={() => setComposeTrialId(null)} />}
      </div>
    </div>
  )
}
