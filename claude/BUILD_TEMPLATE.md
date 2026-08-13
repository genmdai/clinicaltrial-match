# BUILD_TEMPLATE.md — Execution Plan (one-day hackathon)

Companion to CLAUDE.md (read that first; its principles P1–P9 override anything here).
Work phases in order. Each phase has a timebox, acceptance criteria, and a commit.
If a phase overruns its timebox by >50%, consult the Cut Lines section and move on.

Total budget assumption: ~8 working hours. Adjust proportionally if the human says
otherwise.

---

## Phase 0 — Ground truth & scaffolding (45 min)

Goal: eliminate all "verify live" uncertainty from CLAUDE.md before building on it.

Tasks:
1. `curl 'https://clinicaltrials.gov/api/v2/studies?query.cond=non+small+cell+lung+cancer&filter.overallStatus=RECRUITING&pageSize=3&format=json'`
   → save to `fixtures/smoke_search.json`. Inspect real field paths; update CLAUDE.md
   §3 if they differ from the documented starting points.
2. Fetch one full study by NCT ID → `fixtures/smoke_study.json`. Confirm locations of:
   eligibilityCriteria text, min/max age, centralContacts, locations[].geoPoint,
   locations[].contacts.
3. Install Strands SDK; run the smallest possible agent ("echo agent" with one trivial
   tool) against **Amazon Bedrock**. First verify: AWS credentials resolve
   (`aws sts get-caller-identity`), then ask the human which region their Bedrock
   model access is granted in and which Claude model IDs are enabled (read IDs from
   their console/docs — do not trust memory for model ID strings). Wire that
   region/model into Strands' Bedrock provider config.
3b. Git: `git init`, add remote `origin` →
   `https://github.com/genmdai/clinicaltrial-match`, add `.gitignore`
   (.env, fixtures/cache/, node_modules, __pycache__), first commit + push. From here
   on, EVERY "Commit:" line in this file means commit AND push (concise one-liner
   messages), and you additionally commit+push after every minor working change
   between milestones (CLAUDE.md git workflow).
4. Scaffold repo per CLAUDE.md §4 (empty modules, schemas.py filled in, FastAPI
   `/health`, Vite React app renders "hello").
5. Seed `data/drug_ontology.json` with ~40 entries. Must include (oncology):
   Keytruda/pembrolizumab/anti-PD-1; Opdivo/nivolumab/anti-PD-1;
   Tecentriq/atezolizumab/anti-PD-L1; Tagrisso/osimertinib/EGFR TKI;
   Tarceva/erlotinib/EGFR TKI; Xalkori/crizotinib/ALK TKI; Alecensa/alectinib/ALK TKI;
   Avastin/bevacizumab/anti-VEGF; carboplatin, cisplatin, pemetrexed, paclitaxel,
   docetaxel (platinum/taxane chemo classes); Herceptin/trastuzumab/anti-HER2;
   Enhertu/trastuzumab deruxtecan/HER2 ADC; Ibrance/palbociclib/CDK4-6;
   Lynparza/olaparib/PARP; Imbruvica/ibrutinib/BTK; Revlimid/lenalidomide/IMiD;
   Rituxan/rituximab/anti-CD20 — plus a handful of rare-disease drugs
   (e.g. Spinraza/nusinersen, Trikafta/elexacaftor-tezacaftor-ivacaftor,
   Evrysdi/risdiplam). ⚠️ Verify each generic/class pairing against the label or a
   reliable source via web lookup before committing — do not trust memory for these.

Accept: both fixtures on disk; echo agent responds; `pytest` and eval harness stubs run.
Commit: `phase0: scaffolding + live API ground truth`.

---

## Phase 1 — Trial search + normalization (45 min)

Build `tools/search_trials.py` and `tools/fetch_trial.py`.

- Input: condition (normalized string), optional lat/lon + radius, optional
  intervention keywords. Filter `RECRUITING` (plus `NOT_YET_RECRUITING` behind a flag).
- Output: `TrialSummary[]` — nctId, title, phase, status, interventions, siteCount,
  nearestSite (if geo given), hasCentralContact (bool).
- Response caching to `fixtures/cache/` (request-hash keyed). A `--offline` env flag
  forces fixtures only (demo insurance).
- Cap candidate set at 5 trials for downstream parsing (latency budget).

Accept: unit test proves a cached NSCLC search returns ≥3 normalized summaries offline.
Commit: `phase1: search + fetch tools with cache`.

---

## Phase 2 — Patient profile extraction (75 min) ← first differentiator

Build `tools/extract_profile.py` (LLM structured-output call → `PatientProfile`).

Requirements:
- Handles third-person narratives ("my mom…" → subject="relative", compose voice
  changes later).
- Prior-treatment chain: mention → ontology lookup → class; outcome phrases
  ("stopped working", "quit responding", "scans got worse") → outcome="progression",
  `inferred=true`. Toxicity phrases ("couldn't tolerate", "bad side effects") →
  outcome="toxicity", inferred=true.
- Derived flags: any prior treatment ⇒ NOT treatment-naïve; count distinct lines for
  `treatment_line`.
- Everything inferred lands in `assumptions[]` as plain sentences, e.g.
  "I assumed 'stopped working' means the cancer progressed while on Keytruda."
- Prompt technique: give the model the schema, 3 worked examples (incl. one
  third-person, one with a misspelled drug), instruction to output ONLY JSON, and to
  leave fields null rather than guess. Parse defensively (strip fences, retry once on
  invalid JSON).

Eval cases (put in `evals/cases.json`; extraction must pass ≥9/10):
1. "my mom's been on Keytruda for a year and it stopped working, she's 68"
   → age 68, relative, pembrolizumab/anti-PD-1, progression(inferred), not naïve.
2. "62, lung cancer, nothing yet" → treatment-naïve, line 0.
3. "I have stage 4 NSCLC, EGFR positive, failed Tagrisso" → biomarker EGFR+,
   osimertinib, progression.
4. "dad, 71, prostate cancer, on hormone therapy, PSA rising" → class ADT,
   progression inferred.
5. "I'm 45, triple negative breast cancer, did chemo and immunotherapy, both stopped
   helping" → 2 lines, classes chemo + checkpoint inhibitor.
6. "my sister has SMA type 2, she's 9, on Spinraza" → pediatric, ongoing treatment.
7. Misspelling: "keytruda" / "keitruda" still maps via fuzzy ontology match.
8. "68 year old never treated for her melanoma but has bad heart failure"
   → naïve BUT comorbidity captured (feeds an exclusion later).
9. Adversarial vagueness: "grandma is sick with cancer" → mostly nulls + follow-up
   questions, NO fabricated fields.
10. "I progressed on two lines of platinum chemo, ECOG 1, 55F"
    → line 2, ECOG captured, sex F.

Accept: `run_evals.py --stage extraction` ≥9/10.
Commit: `phase2: profile extraction + assumptions + evals`.

---

## Phase 3 — Eligibility rule engine (100 min) ← the core differentiator

Two modules, strictly separated (CLAUDE.md §4: LLM parses, Python judges):

**A. `tools/parse_criteria.py` (LLM):** eligibilityCriteria free text →
`EligibilityRule[]`.
- Chunk by the conventional "Inclusion Criteria:" / "Exclusion Criteria:" headers
  (fall back to whole-text if absent).
- Each rule MUST include `source_quote` copied verbatim; validate with
  `source_quote in criteria_text` — if validation fails, drop to
  `parse_confidence="low"` and re-ask once.
- Map to the small `field` vocabulary in schemas.py; anything unmappable →
  field="other", parse_confidence="low".
- Parse candidates concurrently (asyncio.gather over ≤5 trials).
- Cache parsed rules per NCT ID (criteria text rarely changes intraday).

**B. `tools/check_eligibility.py` (pure Python, unit-tested):** rules × profile →
`CriterionVerdict[]`.
- Deterministic table of (field, operator) → evaluator function.
- Missing profile datum ⇒ UNKNOWN + generated follow_up_question
  ("Has she had any treatment before Keytruda?").
- parse_confidence="low" ⇒ verdict capped at UNKNOWN regardless of evaluator output
  (principles P2/P3).
- Special evaluators to get right for the demo:
  - `treatment_naive` (inclusion "no prior systemic therapy") vs profile with prior
    anti-PD-1 ⇒ FAIL with quote — this is THE demo beat.
  - `prior_therapy_class not_had "anti-PD-(L)1"` (exclusion) vs Keytruda history
    ⇒ FAIL.
  - Age gte/lte from min/max age fields (structured, easy PASS/FAIL wins).
- Trial-level rollup: any FAIL ⇒ "Likely not eligible", else any UNKNOWN ⇒
  "Possibly eligible — N open questions", else "Looks eligible (confirm with team)".
  Sort results: eligible first, then possibly, then not — but SHOW the not-eligibles
  with their red rows (transparency is the pitch).

Eval: extend cases.json — Keytruda-mom profile vs (a) a fixture trial requiring
treatment-naïve ⇒ that criterion FAIL with correct quote; (b) a fixture trial
allowing prior anti-PD-1 with progression ⇒ PASS/UNKNOWN mix, zero false FAILs.
Accept: `run_evals.py --stage verdicts` passes; pytest green on evaluators.
Commit: `phase3: rule engine (parse + deterministic check)`.

---

## Phase 3B — Access Outlook scorer (40 min) ← the user-facing answer

The user's question is not "am I eligible?" but "how likely can I actually get in?"
Build `tools/access_outlook.py` — **pure Python, deterministic, unit-tested**, no LLM.
It consumes CriterionVerdicts + trial record fields + geo output and returns an
`AccessOutlook` (schema in CLAUDE.md §5). P9 applies absolutely: tiers + evidence,
never a percentage.

Four components (each → score 0–1 internally, band strong/fair/weak, evidence
sentences):

1. **eligibility_fit** — from verdicts: any FAIL ⇒ component 0 AND overall tier
   forced to "Blocked" with `blocking_rule_id` set (the red criterion + quote is the
   explanation). Otherwise ratio of PASS to (PASS+UNKNOWN); ≥3 UNKNOWNs ⇒ overall
   tier "Unclear" with `open_questions` count (the fix is answering questions, and
   the UI should say so).
2. **recruitment_momentum** — trial-level overallStatus (RECRUITING strong;
   NOT_YET_RECRUITING fair; anything else weak), recency of lastUpdatePostDate
   (⚠️ verify field name in fixtures; <6 months strong, <18 fair, else weak —
   stale RECRUITING flags are notoriously common and calling this out is a judge-
   pleasing insight), and primaryCompletionDate proximity (<4 months away ⇒ likely
   closing ⇒ weak).
3. **geographic_access** — nearest site that is *individually* recruiting
   (⚠️ verify: locations[] entries carry their own status field): <50 mi strong,
   <150 fair, else weak; count of recruiting sites in radius as secondary evidence.
   No user location ⇒ band "fair" with evidence "location not provided" + follow-up.
4. **contactability** — central contact with email strong; phone-only or
   site-contact-only fair; sponsor-name-only weak (ties into Phase 4 fallback chain).

Tier mapping (only when not Blocked/Unclear): all strong ⇒ High; any weak ⇒ Low;
else Moderate. Keep the mapping table in one place with unit tests per row — judges
may ask "why Moderate?" and the answer must be mechanical, not vibes.

Evals: extend cases — (a) Keytruda-mom vs treatment-naïve trial ⇒ Blocked with
blocking quote; (b) same profile vs prior-IO-allowed trial with 2 UNKNOWNs, recruiting
site 22 mi, fresh update, contact present ⇒ Moderate, open_questions=2; (c) answer
the 2 questions ⇒ recompute ⇒ High (this recompute IS demo beat 5).
Accept: pytest green on mapping table; eval (a)–(c) pass.
Commit: `phase3b: access outlook scorer`.

---

## Phase 4 — Contacts, geo, compose (60 min) ← the action payoff

**Contacts (`fetch_trial.py` extension):** fallback chain
centralContacts → overallOfficials → nearest location.contacts → sponsor name with
"call the site" guidance. Return `contact_source` so the UI can label it honestly.

**Geo (`tools/geo.py`):** ZIP → lat/lon from `data/zip_latlon.csv` (US centroid table;
if full table is heavy, ship top-200 metro ZIPs + graceful "unknown ZIP" handling).
Haversine sort of trial sites; attach nearest 3 sites with miles to each TrialCard.
Also pass lat/lon into the CT.gov geo filter at search time when available.

**Compose (`tools/compose.py`):** generates a draft, never sends (P6). Two variants:
1. Email to trial contact — subject with NCT ID + condition; body states: candidate's
   age/condition/relevant history (ONLY confirmed profile fields, no speculation),
   which criteria appear to match, the open UNKNOWN questions phrased as questions to
   the coordinator, requested next step (pre-screening call). Voice adapts to
   subject=self vs relative ("I am writing on behalf of my mother…").
2. Doctor note — one-pager the patient can hand their oncologist: trial title, NCT ID,
   phase, why it may fit (with the quoted criteria), site + distance, contact details.
Include a visible line in every draft: "Drafted with an AI assistant; please verify
details." Copy-to-clipboard button in UI; optional `mailto:` link that only opens the
user's own mail client prefilled (still human-sent).

Accept: for the Keytruda-mom fixture, a complete draft renders containing NCT ID, the
two UNKNOWN questions, correct relative voice, and contact from the fallback chain.
Commit: `phase4: contacts + geo + compose`.

---

## Phase 5 — UI (120 min)

Read `/mnt/skills` frontend guidance if available in your environment; otherwise
follow this. Layout: left chat pane, right results pane; streamed progress.

Components & beats:
1. **ProgressStream** — agent steps stream as they happen ("Reading your story…",
   "Found 5 recruiting trials", "Checking eligibility for NCT0512… ✓"). Kills the
   dead-air latency problem and demos the agent loop visibly.
2. **AssumptionsCard** — inferred statements as editable chips with confirm button.
   Matching does not run until confirmed (P4). One-click "looks right".
3. **TrialCard** — leads with the **Access Outlook tier pill**
   (High/Moderate/Low/Blocked/Unclear) + four component mini-bars
   (eligibility · momentum · distance · contact), each hoverable/tappable to its
   evidence sentences, plus the fixed P9 caveat line. Then title, phase badge,
   nearest site + miles. Expand → CriterionChecklist. "Blocked" cards show the
   blocking quote inline; "Unclear" cards show "N questions stand between you and an
   answer" with a button that queues them into chat.
4. **CriterionChecklist** — the evidence layer. Rows: ✅/❌/❓ + plain-language reason;
   each row expands to a quote block of the verbatim criterion text. ❓ rows have an
   "Answer this" button that injects the follow-up question into chat; answering
   re-runs ONLY check_eligibility + access_outlook (both pure Python — instant
   re-render, and the tier pill visibly upgrades: great demo moment).
5. **SiteList** (skip the map unless ahead of schedule) — nearest sites sorted by
   distance, each with its contact if present.
6. **ComposeDrawer** — tabs: "Email trial team" / "Note for your doctor"; copy button.
7. **Persistent disclaimer bar** (P8) + "offline demo data" badge when fixtures mode.

Design intent: calm clinical palette, generous whitespace, real typographic hierarchy —
this is for scared families, not dashboards. No walls of JSON anywhere.

Accept: full happy path clickable end-to-end against fixtures with network unplugged.
Commit: `phase5: UI end-to-end`.

---

## Phase 6 — Demo hardening + pitch assets (60 min)

1. Record eval numbers: extraction N/10, verdict cases pass — put them on a slide/README.
2. Warm the cache with the exact demo queries; test on hotspot AND offline flag.
3. README.md: problem, architecture diagram (ASCII fine), the P1 evidence principle,
   competitor table (Antidote/Massive Bio/Power/TrialGPT vs us), monetization line
   (patient-aligned pre-screening for sites — no lead-selling), limitations section
   (free-text parsing imperfect; not medical advice; US-registry only).
4. Dry-run the demo script below twice, timed.

---

## Demo Script (3 minutes)

1. (0:00) One line of problem framing: "50k+ recruiting trials; patients can't read
   eligibility criteria, and search engines don't try."
2. (0:20) Type: *"my mom's been on Keytruda for a year and it stopped working, she's
   68, we're near Columbus Ohio."* Progress stream runs.
3. (0:45) **Assumptions card**: "Keytruda = pembrolizumab, an anti-PD-1 immunotherapy.
   'Stopped working' → I assumed progression. She is not treatment-naïve." Confirm.
   → Narrate: "Every other demo skips this step. We show our reasoning and let the
   family correct it."
4. (1:15) Results ranked by **Access Outlook**. Point at a "Blocked" card: the
   verbatim quote "No prior systemic therapy for advanced disease" sits right on the
   card — "the agent read the fine print and ruled this out FOR the right reason,
   with the trial's own words as evidence." Then point at a "Low" card that is
   perfectly eligible on paper: last registry update 20 months ago, one site 400 mi
   away — "eligibility isn't access. Nobody else is modeling this."
5. (1:45) The "Moderate — 2 open questions" trial: click "Answer this" → answer the
   ECOG question in chat → checklist flips and the tier pill upgrades to **High**
   live. Narrate the P9 line: "tiers with evidence, never an invented percentage."
6. (2:15) Open ComposeDrawer: drafted email to the site coordinator 22 miles away,
   including the two open questions for pre-screening. Copy. "From a mother's story to
   a sendable email in ninety seconds — with every claim traceable to the registry."
7. (2:45) Close: eval numbers + limitations honesty + monetization one-liner.

---

## Cut Lines (apply in order when behind schedule)

1. Drop map → sorted SiteList (already default).
2. Drop live geo filter → distance sort only on returned sites.
3. Drop doctor-note compose variant → email only.
4. Shrink ontology to the 12 drugs the eval cases need.
5. Trim Access Outlook to two components (eligibility_fit + geographic_access) —
   keep the tier pill and evidence sentences; momentum/contactability return
   post-hackathon. Never cut the tier system down to a raw eligibility verdict —
   "access, not just eligibility" is now the headline claim.
6. Drop concurrent parsing → parse top 3 trials serially.
7. LAST RESORT: fixtures-only demo (never cut: assumptions card, Access Outlook tier
   with evidence, criterion checklist with quotes, tri-state verdicts, compose draft
   — these ARE the product).

## Explicitly out of scope (do not build even if tempted)

- FDA approval / PDUFA "approved soon" prediction (no reliable free data source;
  if asked, the honest proxy is a "Phase 3 / late-stage" filter tab — build only if
  every phase above is done).
- Numeric probability of enrollment (P9 — no data to calibrate one; tiers only).
- OMOP CDM implementation / OHDSI tooling. We only ALIGN vocabulary fields
  (rxnorm_ingredient, condition_code — CLAUDE.md §5) so the roadmap slide can say
  "EHR-pluggable schema"; cite Criteria2Query (Columbia/OHDSI) as prior art in the
  README competitor section (⚠️ verify its details via web before citing aloud).
- Auto-sending messages, EHR integration, auth, multi-language, non-US registries.
