const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8787'

async function post(path, body) {
  let res
  try {
    res = await fetch(BASE_URL + path, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    })
  } catch {
    return { error: `Could not reach the TrialPath API at ${BASE_URL}. Is the backend running?` }
  }
  try {
    return await res.json()
  } catch {
    return { error: `TrialPath API returned an unreadable response (HTTP ${res.status}).` }
  }
}

export function extractProfile(narrative) {
  return post('/api/profile', { narrative })
}

export function matchTrials(profile, opts = {}) {
  return post('/api/match', { profile, ...opts })
}

export function composePacket(profile, trial, verdicts) {
  return post('/api/packet', { profile, trial, verdicts })
}

export function enrichTrialAccess(trial, site, opts = {}) {
  return post('/api/enrich', { trial, site, ...opts })
}
