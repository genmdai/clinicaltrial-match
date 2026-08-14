# CLAUDE.md — Pathway: Treatment Observability Agent

One-day hackathon project. Read this file fully before writing any code. When this file
and your instincts conflict, this file wins. When this file is ambiguous, ASK the human —
do not guess on anything marked ⚠️.

## 1. What we are building (and what we are NOT)

An agent that helps patients with serious/rare conditions understand their treatment
options in clinical trials, built on **AWS Strands Agents SDK** (Python) with a custom
interactive web UI.

The pipeline, end to end:

1. Patient types a free-text narrative in chat
   (e.g. "my mom's been on Keytruda for a year and it stopped working, she's 68").
2. Agent extracts a **structured PatientProfile** (age, condition, biomarkers, prior
   treatments, treatment line, inferred events like "progression on anti-PD-1").
3. Agent shows an **"Assumptions I made"** card; user confirms/edits before matching.
4. Agent searches **ClinicalTrials.gov API v2** for candidate trials.
5. Agent parses each candidate trial's free-text eligibility criteria into
   **checkable structured rules** and evaluates them against the profile.
6. Agent computes a per-trial **Access Outlook** — the user-facing answer to
   "how likely can I actually get into this trial?" — a tiered heuristic
   (High / Moderate / Low / Blocked / Unclear) built from four transparent
   components: eligibility fit, recruitment momentum, geographic access,
   contactability. Eligibility is the evidence layer; Access Outlook is the answer
   layer.
7. UI renders the outlook tier with its component breakdown; expanding eligibility
   shows the per-criterion checklist: ✅ PASS / ❌ FAIL / ❓ UNKNOWN, each row
   citing the **verbatim criterion text** from the trial record.
8. ❓ UNKNOWN criteria drive follow-up questions back into the chat; answering
   re-computes verdicts AND the outlook tier live.
9. For matched trials: show recruiter/contact info, nearest site with distance, and a
   **drafted outreach message** (email to trial contact, or a note the patient can give
   their doctor). Compose only — NEVER send.

We are NOT building: a generic search wrapper, user accounts/auth, a database of users,
an auto-emailer, a diagnosis tool, or an FDA-approval predictor.

## 2. Non-negotiable product principles

These are demo-critical AND safety-critical. Violating any of these is a bug of the
highest severity.

- **P1 — No verdict without evidence.** Every eligibility PASS/FAIL/UNKNOWN must carry
  the exact quoted substring of the trial's `eligibilityCriteria` text it derives from.
  If the model cannot point to a quote, the verdict is UNKNOWN.
- **P2 — Tri-state, never binary.** Missing information → UNKNOWN + a generated
  follow-up question. Never coerce UNKNOWN into FAIL or PASS.
- **P3 — FAIL is expensive.** A wrong "ineligible" closes a door for a patient. When
  criterion logic is ambiguous (nested OR/UNLESS, washout windows), prefer UNKNOWN over
  FAIL and say why.
- **P4 — Inferences are visible.** Anything inferred rather than stated (e.g.
  "stopped working" → "disease progression") is labeled `inferred: true`, shown in the
  Assumptions card, and user-editable before matching.
- **P5 — Drug facts come from the ontology first.** Use `data/drug_ontology.json`
  (brand → generic → class → mechanism) for drug normalization. LLM fallback only for
  drugs not in the table, and the result must be flagged `confidence: "low"` in the UI.
- **P6 — Compose, never send.** The compose tool outputs a draft with a copy button.
  No SMTP, no mailto auto-fire, no third-party send API.
- **P7 — No persistence of patient data.** Profile lives in browser/session memory
  only. No writes of PatientProfile to disk or DB. Trial data caching is fine.
- **P8 — Standing disclaimer.** UI shows persistently: "Informational only — not
  medical advice. Eligibility is determined by the trial team. Confirm everything with
  your care team." Do not remove or bury it.
- **P9 — No fake probabilities.** Access Outlook is NEVER a percentage or numeric
  "likelihood" — there is no outcome data to calibrate one, and an invented number in
  a medical context is a credibility-ending bug. Output a tier
  (High / Moderate / Low / Blocked / Unclear) with all four component sub-scores and
  the registry data behind each one visible in the UI, labeled
  "heuristic estimate from registry signals". A hard eligibility FAIL caps the tier
  at Blocked regardless of other components.

## 3. External API ground truth (verified live in Phase 0, 2026-08-13)

The API shapes below were originally written from memory by a planning model and have
now been checked against live sources. Findings below are confirmed, not assumed.

### ClinicalTrials.gov API v2 — verified against a live search + a live single-study
fetch (`fixtures/smoke_search.json`, `fixtures/smoke_study.json`)

- Base: `GET https://clinicaltrials.gov/api/v2/studies` — confirmed working.
- Params confirmed working exactly as named: `query.cond`, `query.intr`,
  `filter.overallStatus=RECRUITING`, `filter.geo=distance(LAT,LON,50mi)`, `pageSize`,
  `format=json`. `fields=` also works but takes a separate PascalCase shorthand
  (e.g. `NCTId`, `BriefTitle`, `OverallStatus`) — NOT the dotted JSON paths below.
- Study record paths — all confirmed present exactly as originally drafted:
  `protocolSection.identificationModule.nctId` / `.briefTitle`;
  `protocolSection.statusModule.overallStatus`; `protocolSection.designModule.phases`;
  `protocolSection.eligibilityModule.eligibilityCriteria` (free text, uses
  "Inclusion Criteria:" / "Exclusion Criteria:" headers in practice — confirms the
  Phase 3 chunking approach), `.sex`;
  `protocolSection.contactsLocationsModule.centralContacts[]` (name/role/phone/email)
  and `.locations[]` (facility, city, state, zip, country, geoPoint.lat/lon,
  contacts[]); `protocolSection.contactsLocationsModule.overallOfficials[]`
  (name/affiliation/role) — present on many but not all studies.
- Two items BUILD_TEMPLATE.md flagged ⚠️ are now resolved:
  - Recency field is `protocolSection.statusModule.lastUpdatePostDateStruct.date`
    (also `.primaryCompletionDateStruct.date` for completion proximity).
  - `locations[]` entries DO carry their own individual `status` field
    (e.g. `"RECRUITING"`) — Phase 3B's `geographic_access` scoring is buildable as
    designed.
- New detail not previously documented: `.minimumAge` / `.maximumAge` are strings
  like `"18 Years"` / `"48 Months"`, not integers — the rule engine must parse
  value+unit, not assume a number.
- This is a JSON API. **Do not scrape HTML.** Respect rate limits: cache every response
  in `fixtures/cache/` keyed by request hash; reuse cache during development.

### AWS Strands Agents — verified against the installed `strands-agents` 1.52.0
package source (not just docs — inspected the actual `.whl` contents to rule out
doc/hallucination drift)

- Install confirmed: `pip install strands-agents strands-agents-tools` (both exist on
  PyPI as named).
- ⚠️ **Correction**: the GitHub repo has been renamed. `github.com/strands-agents/
  sdk-python` now 301-redirects to **`github.com/strands-agents/harness-sdk`**
  (Python SDK lives under its `strands-py` subdirectory; a TypeScript SDK now lives
  alongside it under `strands-ts`). Docs are still at https://strandsagents.com.
- Core usage pattern confirmed correct as drafted: `from strands import Agent, tool`;
  `@tool` decorator (docstring = tool description); `Agent(model=..., tools=[...],
  system_prompt=...)`.
- Bedrock wiring (new detail, not previously documented — confirmed from
  `strands/models/bedrock.py` source): `from strands.models import BedrockModel`;
  `BedrockModel(region_name=..., **model_config)` where `model_config` includes
  `model_id`, `temperature`, `max_tokens`, etc. Region resolves, in order: explicit
  `region_name` → boto3 session's configured region → `AWS_REGION` env var →
  hardcoded `"us-west-2"` fallback. `Agent(model=None)` would default to a
  `BedrockModel` with a hardcoded default model ID baked into the SDK — we do not
  rely on that default; region and model ID are explicitly resolved per below.
- Model provider: **Amazon Bedrock** (decided). Region + model ID resolved live via
  AWS CLI probing: `us-east-1`, model ID `us.anthropic.claude-sonnet-4-5-20250929-v1:0`
  (a cross-region inference profile — plain on-demand IDs like `anthropic.claude-
  sonnet-5` returned `AccessDeniedException` for this account; the SDK's own default,
  `global.anthropic.claude-sonnet-4-6`, was not tested but the resolved ID above is
  confirmed separately). Recorded in `.env` (gitignored) as `BEDROCK_REGION` /
  `BEDROCK_MODEL_ID`.
- ⚠️ **New finding, not previously documented anywhere**: even with model access
  granted and a valid inference-profile ID, Bedrock's Converse/ConverseStream APIs
  reject Anthropic model calls with `ResourceNotFoundException: Model use case
  details have not been submitted for this account. Fill out the Anthropic use case
  details form before using the model.` This is a separate, additional gate from
  the normal Bedrock "model access" request — it's an Anthropic-specific account-
  level use-case questionnaire in the Bedrock console. Resolved once the human
  submitted that form (propagated within a few minutes). If this project moves to a
  fresh AWS account later, expect to hit this again and budget time for it.
- **Echo agent confirmed working end-to-end** (`backend/agent.py`, run via
  `python backend/agent.py` with `.env` loaded): live Bedrock call + tool
  invocation both succeeded against `us-east-1` /
  `us.anthropic.claude-sonnet-4-5-20250929-v1:0`.

## 4. Architecture

```
frontend/            React + Vite single-page app (no auth, no router needed)
  src/App.jsx        chat pane + results pane
  src/components/    AssumptionsCard, TrialCard, CriterionChecklist,
                     SiteList, ComposeDrawer, ProgressStream
backend/             Python 3.11+, FastAPI
  main.py            /chat endpoint (SSE or websocket for streamed progress)
  agent.py           Strands Agent assembly + system prompt
  tools/
    search_trials.py       CT.gov v2 search → normalized TrialSummary list
    fetch_trial.py         full study record by NCT ID
    extract_profile.py     narrative → PatientProfile (structured LLM call)
    parse_criteria.py      eligibilityCriteria text → EligibilityRule[] (LLM, cached)
    check_eligibility.py   PURE PYTHON, deterministic: rules × profile → verdicts
    geo.py                 ZIP → lat/lon (static table in data/zip_latlon.csv),
                           distance sort of sites
    compose.py             draft outreach (email to contact / note for doctor)
  data/
    drug_ontology.json     seeded brand/generic/class table (~40 oncology + rare dz)
    zip_latlon.csv         US ZIP centroid table (or small subset for demo cities)
  fixtures/                cached live responses + canned demo JSON (offline fallback)
  evals/
    cases.json             10 utterance → expected-profile → expected-verdict cases
    run_evals.py           prints pass/fail table; run after every rule-engine change
```

Key separation: **LLM parses, Python judges.** `parse_criteria` uses the model to turn
free text into structured rules (with quoted source spans). `check_eligibility` is
deterministic Python with unit tests — no LLM inside. This is the technical story for
judges: the matching verdict is reproducible and testable.

## 5. Core data shapes (source of truth; keep in `backend/schemas.py` as Pydantic)

```python
class PriorTreatment(BaseModel):
    raw_mention: str            # "Keytruda for a year"
    drug_brand: str | None      # "Keytruda"
    drug_generic: str | None    # "pembrolizumab"
    drug_class: str | None      # "anti-PD-1 checkpoint inhibitor"
    outcome: str | None         # "progression" | "toxicity" | "ongoing" | None
    inferred: bool              # True if outcome/class was inferred, not stated
    confidence: str             # "high" | "low"

class PatientProfile(BaseModel):
    subject: str                # "self" | "relative" (affects compose voice)
    relation: str | None         # added Phase 4 — "mother"/"father"/etc, only set
                                 # when subject=="relative"; compose.py's "on behalf
                                 # of my mother" voice needs the specific relation,
                                 # not just the self/relative binary
    age: int | None
    sex: str | None
    condition: str | None       # normalized, e.g. "non-small cell lung cancer"
    condition_raw: str | None
    biomarkers: list[str]       # e.g. ["EGFR unknown"] — keep unknowns explicit
    prior_treatments: list[PriorTreatment]
    treatment_line: int | None  # inferred count of prior lines
    ecog: int | None            # added Phase 2 — EligibilityRule.field already listed
                                 # "ecog" in its vocab and eval case 10 needs it
                                 # captured, but the original draft never added it here
    comorbidities: list[str]    # added Phase 2 — eval case 8 ("naive BUT comorbidity
                                 # captured, feeds an exclusion later") needs somewhere
                                 # to land; "other"-field exclusions in Phase 3 read this
    location_zip: str | None
    assumptions: list[str]      # human-readable inferred statements for the card

class EligibilityRule(BaseModel):
    rule_id: str
    kind: str        # "inclusion" | "exclusion"
    field: str       # "age" | "prior_therapy_class" | "condition" | "biomarker"
                     # | "treatment_naive" | "ecog" | "other"
    operator: str    # "gte" | "lte" | "eq" | "contains" | "not_had" | "must_have"
    value: str | int
    source_quote: str           # VERBATIM substring of eligibilityCriteria (P1)
    parse_confidence: str       # "high" | "low" — low ⇒ verdict capped at UNKNOWN

class CriterionVerdict(BaseModel):
    rule_id: str
    verdict: str                # "PASS" | "FAIL" | "UNKNOWN"
    reason: str                 # one sentence, plain language
    source_quote: str
    follow_up_question: str | None   # required when verdict == "UNKNOWN"

class OutlookComponent(BaseModel):
    name: str        # "eligibility_fit" | "recruitment_momentum"
                     # | "geographic_access" | "contactability"
    score: float     # 0.0–1.0, internal only — UI shows band + evidence, not decimals
    band: str        # "strong" | "fair" | "weak"
    evidence: list[str]   # plain sentences citing registry data, e.g.
                     # "Trial-level status RECRUITING, last updated 2026-07-30",
                     # "2 of 4 sites within 50 mi are individually recruiting"

class AccessOutlook(BaseModel):
    trial_nct_id: str
    tier: str        # "High" | "Moderate" | "Low" | "Blocked" | "Unclear"
    components: list[OutlookComponent]     # always all four
    blocking_rule_id: str | None           # set when tier == "Blocked" (links to the
                                           # FAIL criterion + its quote — P1 applies)
    open_questions: int                    # UNKNOWN count; ≥3 unknowns ⇒ "Unclear"
    caveat: str      # fixed string: "Heuristic estimate from registry signals —
                     # not a probability. Final say is the trial team's."
```

OMOP vocabulary alignment (roadmap-grade, zero runtime cost): `PriorTreatment` gains
optional `rxnorm_ingredient: str | None` (populate from `drug_ontology.json` where
known); `PatientProfile` gains optional `condition_code: str | None` (SNOMED-style
concept label from a tiny lookup for the demo conditions). Do NOT implement OMOP CDM
tables or OHDSI tooling — the alignment exists so the pitch can truthfully say the
profile schema could be populated from EHR data downstream.

## 6. Coding standards & workflow

- Python: type hints everywhere, Pydantic for all cross-boundary data, `ruff` clean.
- Every tool function: docstring first (Strands uses it), then happy path, then
  explicit error return (tools must never raise into the agent loop — return a
  structured error the agent can explain to the user).
- Unit tests for `check_eligibility.py` and `geo.py` (pytest). Run
  `python evals/run_evals.py` after any change to extraction or rule logic.
- **Git workflow (human-specified, follow exactly):**
  - Commit AND push after every minor change — not just at phase milestones.
  - Remote: `https://github.com/genmdai/clinicaltrial-match` (set as `origin` in
    Phase 0; if push auth fails, stop and ask the human for their preferred auth —
    do not fiddle with credentials unilaterally).
  - Commit messages: concise one-liners, imperative mood
    (e.g. `add access outlook scorer`, `fix haversine unit test`).
  - Never commit: `.env`, credentials, `fixtures/cache/` bulk (keep the handful of
    named demo fixtures tracked; gitignore the request-hash cache).
- All secrets via env vars (`.env`, gitignored). Never hardcode keys.
- If the CT.gov API is unreachable, the app must transparently fall back to
  `fixtures/` and show a small "offline demo data" badge — never crash the demo.

## 7. Things to ASK the human about (do not decide unilaterally)

1. Bedrock region + which Claude model IDs have access granted in their console —
   blocks agent setup (provider itself is decided: Bedrock).
2. Whether a map library is worth it vs a sorted site list with distances (map is
   prettier; list is faster to ship). Default to list if no answer.
3. Any hackathon-imposed constraints (deployment target, submission format, rubric).
4. Demo condition to optimize fixtures for (default: NSCLC / the "Keytruda mom" story).

## 8. Demo north star

The 3-minute demo beat sheet lives in BUILD_TEMPLATE.md §Demo Script. Every build
decision should be tested against: "does this make the Keytruda-mom demo sharper?"
If a feature doesn't serve that demo, it goes below the cut line.
