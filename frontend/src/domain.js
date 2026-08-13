// Shared vocabulary between the profile card and the adaptive question engine.
// Mirrors backend/schemas.py PatientProfile and the field/operator vocabulary
// check_eligibility.py actually knows how to judge (backend/tools/check_eligibility.py
// _EVALUATORS) — a field outside this list can never resolve from UNKNOWN via the UI,
// so it's intentionally excluded from the adaptive question list.

export const CHECKABLE_FIELDS = new Set([
  'age',
  'ecog',
  'condition',
  'biomarker',
  'treatment_naive',
  'prior_therapy_class',
])

export function emptyProfile() {
  return {
    subject: 'self',
    age: null,
    sex: null,
    condition: '',
    condition_raw: '',
    biomarkers: [],
    prior_treatments: [],
    treatment_line: null,
    ecog: null,
    comorbidities: [],
    location_zip: null,
    assumptions: [],
  }
}

export const PROFILE_FIELDS = [
  { key: 'condition', label: 'Condition / diagnosis', eg: 'e.g. Non-small cell lung cancer', span: true },
  { key: 'biomarkerText', label: 'Biomarker / genomic result', eg: 'e.g. EGFR exon 20 insertion' },
  { key: 'ecog', label: 'ECOG performance status', eg: 'e.g. 1' },
  { key: 'age', label: 'Age', eg: 'e.g. 61' },
  { key: 'sex', label: 'Sex', eg: 'e.g. Female' },
  { key: 'location_zip', label: 'Location (ZIP)', eg: 'e.g. 94301' },
  { key: 'priorTxText', label: 'Previous treatments', eg: 'e.g. Carboplatin + pemetrexed, then amivantamab', span: true },
]

export function profileToFieldValues(profile) {
  return {
    condition: profile.condition_raw || profile.condition || '',
    biomarkerText: (profile.biomarkers || []).join(', '),
    ecog: profile.ecog ?? '',
    age: profile.age ?? '',
    sex: profile.sex || '',
    location_zip: profile.location_zip || '',
    priorTxText: (profile.prior_treatments || []).map((t) => t.raw_mention).join('; '),
  }
}

export function applyFieldEdit(profile, key, value) {
  const next = { ...profile }
  if (key === 'condition') {
    next.condition = value
    next.condition_raw = value
  } else if (key === 'biomarkerText') {
    next.biomarkers = value
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
  } else if (key === 'ecog') {
    next.ecog = value === '' ? null : Number(value)
  } else if (key === 'age') {
    next.age = value === '' ? null : Number(value)
  } else if (key === 'sex') {
    next.sex = value || null
  } else if (key === 'location_zip') {
    next.location_zip = value || null
  } else if (key === 'priorTxText') {
    next.prior_treatments = value.trim()
      ? value.split(';').map((s) => s.trim()).filter(Boolean).map((raw_mention) => ({
          raw_mention,
          drug_brand: null,
          drug_generic: null,
          drug_class: null,
          outcome: null,
          inferred: false,
          confidence: 'low',
        }))
      : []
  }
  return next
}

export function profileSummaryRows(profile) {
  const v = profileToFieldValues(profile)
  return PROFILE_FIELDS.map((f) => ({
    label: f.label.split(' / ')[0],
    value: v[f.key] ? String(v[f.key]) : 'Not provided',
    present: !!v[f.key],
  }))
}

function fieldLabel(field, value) {
  switch (field) {
    case 'age':
      return 'Age'
    case 'ecog':
      return 'ECOG performance status'
    case 'condition':
      return 'Diagnosed condition'
    case 'biomarker':
      return `${value} status`
    case 'treatment_naive':
      return 'Prior systemic treatment'
    case 'prior_therapy_class':
      return `Prior ${value} therapy`
    default:
      return field
  }
}

// Cross-reference a trial result's verdicts with its rules (verdict only carries
// rule_id) to recover field/value, then group UNKNOWN verdicts by field across
// every still-candidate trial. "affects" = how many trials currently have this
// field unresolved — the same discriminating-power idea the design used, driven
// by real backend verdicts instead of a scripted question list.
export function collectQuestions(entries, dismissedFields) {
  const byField = new Map()
  for (const entry of entries) {
    if (!entry.rules || !entry.verdicts) continue
    const rulesById = new Map(entry.rules.map((r) => [r.rule_id, r]))
    for (const v of entry.verdicts) {
      if (v.verdict !== 'UNKNOWN') continue
      const rule = rulesById.get(v.rule_id)
      if (!rule || !CHECKABLE_FIELDS.has(rule.field)) continue
      if (dismissedFields.has(rule.field)) continue
      if (!byField.has(rule.field)) {
        byField.set(rule.field, {
          field: rule.field,
          value: rule.value,
          followUp: v.follow_up_question || rule.source_quote,
          trialIds: new Set(),
        })
      }
      byField.get(rule.field).trialIds.add(entry.trial.nct_id)
    }
  }
  return [...byField.values()]
    .map((q) => ({ ...q, label: fieldLabel(q.field, q.value), affects: q.trialIds.size }))
    .sort((a, b) => b.affects - a.affects)
}

export function isTrialClean(entry) {
  return !entry.error && !(entry.verdicts || []).some((v) => v.verdict === 'FAIL')
}

export function trialFailsField(entry, field) {
  if (!entry.rules || !entry.verdicts) return false
  const rulesById = new Map(entry.rules.map((r) => [r.rule_id, r]))
  return entry.verdicts.some((v) => v.verdict === 'FAIL' && rulesById.get(v.rule_id)?.field === field)
}

export function applyAnswer(profile, question, answer) {
  const next = { ...profile }
  const { field, value } = question
  if (field === 'age' || field === 'ecog') {
    next[field] = answer === '' ? null : Number(answer)
  } else if (field === 'condition') {
    next.condition = answer
    next.condition_raw = answer
  } else if (field === 'biomarker') {
    const keyword = String(value)
    const filtered = (next.biomarkers || []).filter(
      (b) => !b.toLowerCase().startsWith(keyword.toLowerCase()),
    )
    const suffix = answer === 'yes' ? 'positive' : answer === 'no' ? 'negative' : 'unknown'
    next.biomarkers = [...filtered, `${keyword} ${suffix}`]
  } else if (field === 'treatment_naive') {
    if (answer === 'no') next.treatment_line = 0
    else if (answer === 'yes' && !next.prior_treatments?.length) {
      next.treatment_line = next.treatment_line ?? 1
      next.prior_treatments = [
        {
          raw_mention: 'prior systemic treatment (unspecified)',
          drug_brand: null,
          drug_generic: null,
          drug_class: null,
          outcome: null,
          inferred: true,
          confidence: 'low',
        },
      ]
    }
  } else if (field === 'prior_therapy_class') {
    const keyword = String(value)
    if (answer === 'yes') {
      const already = (next.prior_treatments || []).some(
        (t) => (t.drug_class || '').toLowerCase() === keyword.toLowerCase(),
      )
      if (!already) {
        next.prior_treatments = [
          ...(next.prior_treatments || []),
          {
            raw_mention: keyword,
            drug_brand: null,
            drug_generic: null,
            drug_class: keyword,
            outcome: 'ongoing',
            inferred: true,
            confidence: 'low',
          },
        ]
      }
    } else if (answer === 'no' && !next.prior_treatments?.length) {
      next.treatment_line = 0
    }
  }
  return next
}

export const QUESTION_OPTIONS = {
  age: null, // numeric input
  ecog: null, // numeric input
  condition: null, // text input
  biomarker: [
    { label: 'Yes, confirmed', value: 'yes' },
    { label: 'No', value: 'no' },
    { label: 'Not sure', value: 'unsure' },
  ],
  treatment_naive: [
    { label: 'Yes, I have', value: 'yes' },
    { label: 'No prior treatment', value: 'no' },
    { label: 'Not sure', value: 'unsure' },
  ],
  prior_therapy_class: [
    { label: 'Yes', value: 'yes' },
    { label: 'No', value: 'no' },
    { label: 'Not sure', value: 'unsure' },
  ],
}
