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

export async function recompute({ profile, rules, nctId, study, patientLat, patientLon, answer }) {
  const res = await fetch(`${BASE_URL}/recompute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      profile, rules, nct_id: nctId, study,
      patient_lat: patientLat ?? null, patient_lon: patientLon ?? null,
      answer: answer ?? null,
    }),
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
