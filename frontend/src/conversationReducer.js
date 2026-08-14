// Owns just the profile-building stage — replaces the old implicit routing
// (a `pendingNarrative` string that was truthy mid-clarification, concatenated
// with the next message and re-extracted from scratch). Stage is now derived
// directly from `profile.gaps`: any open gap means the structured intake form
// blocks /match; zero gaps means the profile was already search-ready (the
// "Keytruda mom" clean-narrative case keeps searching immediately, no added
// friction). This reducer does NOT own trial results, map state, or the
// compose drawer — those are just data, not flow-routing, and stay as plain
// useState in App.jsx.

export const STAGES = {
  CHATTING: 'chatting',
  COLLECTING_PROFILE: 'collecting_profile',
}

export const initialConversationState = {
  stage: STAGES.CHATTING,
  profile: null,
}

function stageFor(profile) {
  // Only a `required` gap (currently: an unresolved/missing condition) blocks
  // the search — an optional gap (e.g. missing biomarker status) is worth
  // asking but doesn't invalidate matching, so it never gates a clean,
  // well-specified narrative from searching immediately.
  const hasRequiredGap = (profile?.gaps ?? []).some((g) => g.required)
  return hasRequiredGap ? STAGES.COLLECTING_PROFILE : STAGES.CHATTING
}

export function conversationReducer(state, action) {
  switch (action.type) {
    case 'EXTRACTION_RESOLVED':
    case 'PROFILE_PATCHED':
    case 'PROFILE_EDITED':
      return { ...state, profile: action.profile, stage: stageFor(action.profile) }
    case 'MATCH_STARTED':
      return { ...state, stage: STAGES.CHATTING }
    case 'RESET':
      return initialConversationState
    default:
      return state
  }
}
