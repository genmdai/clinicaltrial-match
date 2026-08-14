const BASE_URL = ''

export async function extractProfile(narrative) {
  const res = await fetch(`${BASE_URL}/extract`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ narrative }),
  })
  return res.json()
}

// Streams /match's SSE response, calling onEvent for each parsed JSON event.
export async function matchTrials(profile, radiusMi, onEvent) {
  const res = await fetch(`${BASE_URL}/match`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ profile, radius_mi: radiusMi ?? 50.0 }),
  })
  if (!res.ok || !res.body) {
    onEvent({ type: 'error', message: `Server error (${res.status})` })
    return
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    let sepIndex
    while ((sepIndex = buffer.indexOf('\n\n')) !== -1) {
      const rawEvent = buffer.slice(0, sepIndex)
      buffer = buffer.slice(sepIndex + 2)
      const line = rawEvent.split('\n').find((l) => l.startsWith('data: '))
      if (!line) continue
      try {
        onEvent(JSON.parse(line.slice(6)))
      } catch {
        // ignore malformed chunk
      }
    }
  }
}

// Stateless adaptive-narrowing step: resend the FULL ordered answer list every
// time (never a delta) so retracting an earlier answer is just "call with one
// fewer entry" — the backend replays from baseProfile, never patches forward.
export async function screen({ baseProfile, answers, trials, patientLat, patientLon }) {
  const res = await fetch(`${BASE_URL}/screen`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      base_profile: baseProfile,
      answers,
      trials,
      patient_lat: patientLat ?? null,
      patient_lon: patientLon ?? null,
    }),
  })
  return res.json()
}

export async function publicAccessLinks({ nctId, facilityName, sponsorName }) {
  const res = await fetch(`${BASE_URL}/trial-access-links`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ nct_id: nctId, facility_name: facilityName ?? null, sponsor_name: sponsorName ?? null }),
  })
  return res.json()
}

export async function compose({ variant, profile, nctId, verdicts, contact, trialTitle, study, nearestSite }) {
  const res = await fetch(`${BASE_URL}/compose`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      variant, profile, nct_id: nctId, verdicts, contact,
      trial_title: trialTitle ?? null, study: study ?? null, nearest_site: nearestSite ?? null,
    }),
  })
  return res.json()
}
