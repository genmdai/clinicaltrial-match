import { useRef, useState } from 'react'
import { compose, extractProfile, matchTrials, publicAccessLinks, screen } from './api'
import AssumptionsCard from './components/AssumptionsCard'
import ChatIntroCard from './components/ChatIntroCard'
import ComposeDrawer from './components/ComposeDrawer'
import LoadingSteps from './components/LoadingSteps'
import ProgressStream from './components/ProgressStream'
import RestrictionLedger from './components/RestrictionLedger'
import ScreeningQuestion from './components/ScreeningQuestion'
import Sidebar from './components/Sidebar'
import StatCards from './components/StatCards'
import TierSummaryRow from './components/TierSummaryRow'
import TrialAccessView from './components/TrialAccessView'
import TrialCard from './components/TrialCard'
import './App.css'

const INITIAL_GREETING =
  "Tell me about the patient's situation — condition, treatments tried, age, and a " +
  "location (ZIP code, or city/country) if you'd like nearby sites."

let nextId = 0
const uid = () => `m${nextId++}`

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
  const [profile, setProfile] = useState(null)
  const [pendingNarrative, setPendingNarrative] = useState(null)
  const [progressMessages, setProgressMessages] = useState([])
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
    setCandidateTrials([])
    setTrialResults({})
    setTrialErrors({})
    setAnswers([])
    setScreenState(null)
    setSelectedTrialId(null)
    setTotalCount(null)
    setConditionSearched(null)

    let doneLat = null
    let doneLon = null

    await matchTrials(matchProfile, 50.0, (event) => {
      if (event.type === 'progress') {
        setProgressMessages((m) => [...m, event.message])
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
    setProfile(extracted)
    if (!extracted.condition && !extracted.condition_raw) {
      setPendingNarrative(text)
      addMessage('bot', 'I still need to know the diagnosis to search — what condition is this for?')
      return
    }
    if (extracted.condition_needs_clarification && extracted.condition_clarifying_question) {
      // Condition is only a broad category (e.g. "diabetes" with no type) — searching
      // now would return a meaningless mix of non-overlapping trials. Same
      // pendingNarrative pattern as the "no diagnosis at all" case above: the user's
      // next message gets appended to this one and re-extracted as a whole.
      setPendingNarrative(text)
      addMessage('bot', extracted.condition_clarifying_question)
      return
    }
    runMatch(extracted)
  }

  const handleUpdateProfile = (updated) => {
    setProfile(updated)
    runMatch(updated)
  }

  const handleAnswerQuestion = async (answerText) => {
    const nq = screenState?.next_question
    if (!nq) return
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

    if (pendingNarrative) {
      const combined = `${pendingNarrative} ${text}`
      setPendingNarrative(null)
      addMessage('user', text)
      await extractAndMatch(combined)
      return
    }

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
    setProfile(null)
    setPendingNarrative(null)
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
      <Sidebar
        onNewSearch={handleNewSearch}
        showBackToMatches={Boolean(selectedTrial)}
        onBackToMatches={() => setSelectedTrialId(null)}
        offline={offlineMode}
      />

      <div className="app-main">
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
                  <AssumptionsCard profile={profile} onUpdate={handleUpdateProfile} />
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

            <section className="results-pane">
              {!searched && <p className="results-empty">Trial matches will appear here once you describe the patient.</p>}

              {searched && candidateTrials.length === 0 && !matching && (
                <p className="results-empty">
                  No recruiting studies found{conditionSearched ? ` for ${conditionSearched}` : ''} — try broadening
                  the description.
                </p>
              )}

              {matching && <LoadingSteps messages={progressMessages} active={matching} />}

              {candidateTrials.length > 0 && (
                <StatCards
                  count={screenState ? openTrialIds.size : candidateTrials.length}
                  label={screenState ? 'studies still open' : 'studies found'}
                  screened={candidateTrials.length}
                  total={totalCount ?? candidateTrials.length}
                  condition={conditionSearched}
                />
              )}

              <TierSummaryRow counts={tierCounts} />

              {answers.length > 0 && (
                <RestrictionLedger answers={answers} ledger={screenState?.ledger ?? []} onRemove={handleRetractAnswer} />
              )}

              {visibleTrials.map((t) => {
                const view = getTrialView(t.nct_id)
                if (!view) {
                  return (
                    <div key={t.nct_id} className="trial-card trial-card--skeleton">
                      <h3 className="trial-title">{t.title}</h3>
                      <p className="trial-skeleton-note">Scoring this trial…</p>
                    </div>
                  )
                }
                return (
                  <TrialCard
                    key={t.nct_id}
                    trial={view}
                    onSelectTrial={() => setSelectedTrialId(t.nct_id)}
                    onOpenCompose={() => setComposeTrialId(t.nct_id)}
                  />
                )
              })}
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
