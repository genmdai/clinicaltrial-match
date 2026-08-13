import { useRef, useState } from 'react'
import { compose, extractProfile, matchTrials, recompute } from './api'
import AssumptionsCard from './components/AssumptionsCard'
import ComposeDrawer from './components/ComposeDrawer'
import ProgressStream from './components/ProgressStream'
import TrialCard from './components/TrialCard'
import './App.css'

let nextId = 0
const uid = () => `m${nextId++}`

export default function App() {
  const [chatLog, setChatLog] = useState([
    {
      id: uid(),
      role: 'bot',
      text: "Tell me about the patient's situation — condition, treatments tried, age, and a ZIP code if you'd like nearby sites.",
    },
  ])
  const [input, setInput] = useState('')
  const [profile, setProfile] = useState(null)
  const [confirmed, setConfirmed] = useState(false)
  const [progressMessages, setProgressMessages] = useState([])
  const [matching, setMatching] = useState(false)
  const [trials, setTrials] = useState(null)
  const [offlineMode, setOfflineMode] = useState(false)
  const [pendingAnswer, setPendingAnswer] = useState(null)
  const [composeTrialId, setComposeTrialId] = useState(null)
  const patientLocation = useRef({ lat: null, lon: null })

  const addMessage = (role, text) => setChatLog((log) => [...log, { id: uid(), role, text }])

  const runMatch = async (confirmedProfile) => {
    setMatching(true)
    setProgressMessages([])
    setTrials(null)
    await matchTrials(confirmedProfile, 50.0, (event) => {
      if (event.type === 'progress') {
        setProgressMessages((m) => [...m, event.message])
        if (typeof event.offline === 'boolean') setOfflineMode(event.offline)
      } else if (event.type === 'result') {
        patientLocation.current = { lat: event.patient_lat, lon: event.patient_lon }
        setOfflineMode(event.offline)
        setTrials(event.trials)
        setMatching(false)
        addMessage('bot', `Found ${event.trials.length} candidate trials, sorted by Access Outlook.`)
      } else if (event.type === 'error') {
        addMessage('bot', `I couldn't finish that search: ${event.message}`)
        setMatching(false)
      }
    })
  }

  const handleConfirmAssumptions = (editedProfile) => {
    setProfile(editedProfile)
    setConfirmed(true)
    runMatch(editedProfile)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    const text = input.trim()
    if (!text) return
    setInput('')
    addMessage('user', text)

    if (pendingAnswer) {
      const { nctId, ruleId } = pendingAnswer
      setPendingAnswer(null)
      const trial = trials.find((t) => t.summary.nct_id === nctId)
      const result = await recompute({
        profile,
        rules: trial.rules,
        nctId,
        study: trial.study,
        patientLat: patientLocation.current.lat,
        patientLon: patientLocation.current.lon,
        answer: { rule_id: ruleId, text },
      })
      if (result.error) {
        addMessage('bot', `Couldn't update that: ${result.error}`)
        return
      }
      setProfile(result.profile)
      setTrials((ts) =>
        ts.map((t) =>
          t.summary.nct_id === nctId
            ? { ...t, verdicts: result.verdicts, rollup: result.rollup, outlook: result.outlook }
            : t,
        ),
      )
      addMessage('bot', `Updated — that trial's Access Outlook is now ${result.outlook.tier}.`)
      return
    }

    if (!profile) {
      const result = await extractProfile(text)
      if (result.error) {
        addMessage('bot', `I had trouble reading that: ${result.error}`)
        return
      }
      setProfile(result.profile)
    }
  }

  const handleAnswerThis = (nctId, ruleId, question) => {
    setPendingAnswer({ nctId, ruleId, question })
    addMessage('bot', question)
  }

  const composeTrial = trials?.find((t) => t.summary.nct_id === composeTrialId)

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

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>ClinicalCohort</h1>
        {offlineMode && <span className="offline-badge">offline demo data</span>}
      </header>

      <div className="app-panes">
        <section className="chat-pane">
          <div className="chat-log">
            {chatLog.map((m) => (
              <div key={m.id} className={`chat-message chat-message--${m.role}`}>
                {m.text}
              </div>
            ))}

            {profile && !confirmed && (
              <AssumptionsCard profile={profile} onConfirm={handleConfirmAssumptions} />
            )}

            {(matching || progressMessages.length > 0) && (
              <ProgressStream messages={progressMessages} active={matching} />
            )}
          </div>

          <form className="chat-input-row" onSubmit={handleSubmit}>
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={pendingAnswer ? 'Type your answer…' : 'Describe the patient’s situation…'}
            />
            <button type="submit" className="btn-primary">
              Send
            </button>
          </form>
        </section>

        <section className="results-pane">
          {!trials && !matching && (
            <p className="results-empty">Trial matches will appear here once you confirm the assumptions.</p>
          )}
          {trials &&
            trials.map((trial) => (
              <TrialCard
                key={trial.summary.nct_id}
                trial={trial}
                onAnswerThis={handleAnswerThis}
                onOpenCompose={() => setComposeTrialId(trial.summary.nct_id)}
              />
            ))}
        </section>
      </div>

      <footer className="disclaimer-bar">
        Informational only — not medical advice. Eligibility is determined by the trial team. Confirm everything
        with your care team.
      </footer>

      {composeTrial && <ComposeDrawer onCompose={handleCompose} onClose={() => setComposeTrialId(null)} />}
    </div>
  )
}
