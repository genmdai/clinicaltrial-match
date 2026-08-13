# ClinicalCohort

An agent that helps patients (and the family members advocating for them) with
serious or rare conditions understand their real options in clinical trials —
built on **AWS Strands Agents SDK** running Claude on **Amazon Bedrock**, against
the live **ClinicalTrials.gov API v2**.

> Informational only — not medical advice. Eligibility is determined by the trial
> team. Confirm everything with your care team.

## The problem

There are 50,000+ recruiting trials on ClinicalTrials.gov at any given time.
Patients can't read eligibility criteria written for clinical coordinators, and
existing search tools don't try to translate it for them. Worse, "am I eligible?"
isn't even the question that matters most — a patient can be eligible on paper for
a trial with one site 400 miles away and a registry entry nobody's touched in
20 months. Nobody is modeling *access*, only eligibility.

## What it does

1. Patient (or caregiver) types a free-text narrative in chat.
2. The agent extracts a structured **PatientProfile** — and shows its work: an
   **"Assumptions I made"** card the family can edit before anything else runs.
3. It searches ClinicalTrials.gov for recruiting trials matching the (normalized)
   condition and, if given, a ZIP code.
4. For each candidate, it parses the trial's free-text eligibility criteria into
   structured, checkable rules, and evaluates them against the profile —
   deterministically, in pure Python.
5. It computes a per-trial **Access Outlook**: not a raw eligibility verdict, but
   a tiered answer to "how likely can I actually get in?" — built from four
   transparent components (eligibility fit, recruitment momentum, geographic
   access, contactability).
6. Every PASS/FAIL/UNKNOWN cites the **verbatim trial text** it came from.
   ❓ UNKNOWNs drive follow-up questions; answering one recomputes the verdict
   *and* the tier live, instantly (no LLM round-trip needed for that step).
7. For a trial the family wants to pursue: a **drafted** outreach email or
   one-page doctor's note — compose only, never sent.

## Architecture

```
┌────────────────────────┐        HTTP + SSE       ┌──────────────────────────────┐
│   Frontend (React/Vite)│◄────────────────────────►│      Backend (FastAPI)       │
│  chat pane │ results   │                          │  /extract /match /recompute  │
└────────────────────────┘                          │  /compose  — all stateless   │
                                                     └───────────────┬───────────────┘
                                                                     │
                                        deterministic orchestration (not agentic —
                                            this is what makes it reproducible)
                                                                     │
        ┌───────────────┬───────────────┬───────────────┬───────────┴────┬──────────────┐
        ▼               ▼               ▼               ▼                ▼              ▼
  extract_profile  search_trials   fetch_trial     parse_criteria   check_eligibility  access_outlook
     (LLM)          (CT.gov v2)    (CT.gov v2)        (LLM)          (pure Python)      (pure Python)
        │               │               │                │                                   │
        ▼               └───────┬───────┘                ▼                                   │
  Amazon Bedrock                ▼                  Amazon Bedrock                              │
  (Claude, via Strands)  ClinicalTrials.gov    (Claude, via Strands)                            │
                             API v2                                                             │
                                                                                                  ▼
                                                                              geo.py (ZIP→lat/lon, haversine)
                                                                              compose.py (draft, never send)
```

**LLM parses, Python judges.** The two LLM calls (`extract_profile`,
`parse_criteria`) turn free text into structured data. Everything downstream —
matching a profile against rules, scoring access, drafting outreach — is
deterministic, unit-tested Python with zero model calls. That's the whole
technical pitch: the verdict you see is reproducible, not a fresh roll of the
dice per page load.

## The evidence principle (P1)

Every eligibility verdict must carry the **exact quoted substring** of the
trial's own eligibility criteria text it derives from. This is enforced, not
just requested: `parse_criteria.py` validates each parsed rule's quote against
the original text and re-asks once if it doesn't match verbatim; anything still
unverified is forced to low confidence, which `check_eligibility.py` then caps
at `UNKNOWN` regardless of what the raw evaluator would have said. **If the
model can't point to a quote, the verdict is UNKNOWN — never a guessed FAIL.**
A wrong "ineligible" closes a door for a patient; that's the single most
expensive mistake this system can make, so it's structurally prevented rather
than just discouraged in a prompt.

The same conservatism applies to eligibility judgment itself: condition-matching
was tuned (via real bugs caught in live testing, not just spec-reading) to say
UNKNOWN rather than FAIL whenever a trial's wording is more specific or more
generic than what's on record — e.g. a trial requiring "non-squamous NSCLC"
against a profile with plain "NSCLC" recorded is unconfirmed, not contradicted.

## Access Outlook — never a fake number (P9)

The tier (**High / Moderate / Low / Blocked / Unclear**) is a mechanical
function of four component bands (strong/fair/weak), each with its own
evidence sentences — never a percentage. There's no outcome data on
ClinicalTrials.gov to calibrate a real probability against, and an invented
number in a medical context is a credibility-ending bug. A hard eligibility
FAIL always forces Blocked, regardless of the other three components.

## Eval numbers

| Stage | Result |
|---|---|
| Patient-profile extraction (10 hand-written narrative cases, incl. third-person, misspelled drug names, and adversarial vagueness) | **10/10**, reproduced across independent runs |
| Eligibility verdicts (Keytruda-mom profile vs. a treatment-naive-required fixture and a prior-IO-allowed fixture) | **2/2** |
| Unit tests (deterministic modules: `check_eligibility`, `access_outlook`, `geo`, `compose`, `fetch_trial`'s contact chain, ontology matching, criteria chunking) | **92/92**, zero LLM calls, run in <0.3s |

Run them yourself: `python evals/run_evals.py` (needs live Bedrock) and
`pytest` (fully offline).

## Competitive landscape

|  | Audience | Shows *why* it matched (per-criterion evidence) | Answers "how likely can I get in," not just "am I eligible" |
|---|---|---|---|
| **Antidote** | Patient | Not documented — presents a match list, not per-criterion reasoning | No |
| **Massive Bio** | Physician/site-first, now also a patient portal (match report) | Marketing claims "auditability" for clinical/regulatory use; no confirmed patient-facing quote UI | No |
| **Power** | Patient (search + filter across 30k+ trials) | Shows raw criteria text on the trial page; no automated per-criterion verdict | No |
| **TrialGPT** (NIH/NCBI research system) | Research/clinician tooling, not a deployed consumer product | Yes — its actual contribution is faithful per-criterion explanations | Not its focus (a matching/ranking benchmark) |
| **Criteria2Query** (Columbia/OHDSI) | Informatics researchers — turns criteria into OMOP cohort queries | N/A — structured query output, not a patient-facing evidence UI | No |
| **ClinicalCohort** | Patient/caregiver | Yes — verbatim quote behind every verdict, always | Yes — 4-component Access Outlook tier |

TrialGPT is the closest technical relative — its core finding (LLM-derived,
per-criterion, *faithful* explanations beat black-box matching) is exactly the
thesis this project is built on. The difference is packaging: TrialGPT is
research/benchmark infrastructure for clinicians; ClinicalCohort is the patient-
facing product built on that same idea, plus the access-vs-eligibility layer on
top. Criteria2Query is cited as prior art for the general "structure the free
text criteria" move, not as a direct competitor — it targets OMOP cohort
definition for researchers, not individual patient matching.

## Monetization

Patient-aligned pre-screening for trial **sites** — license the matching +
pre-screening pipeline to sponsors/CROs/site networks as a smarter intake
funnel that reduces coordinator time spent on unqualified leads, with every
verdict traceable to the trial's own criteria text. Explicitly **not** a
lead-selling model: no selling of patient contact info to multiple competing
sites, no auctioning attention. The patient's interest (a fast, honest answer)
and the site's interest (fewer unqualified pre-screens) point the same
direction; monetizing patient data would point them apart.

## Limitations

- **Free-text parsing is imperfect.** Both patient-narrative extraction and
  trial-criteria parsing are LLM calls; nuance, unusual phrasing, or deeply
  nested criteria logic can be missed or misparsed. The system is built to fail
  toward `UNKNOWN` rather than a wrong verdict, but "ask the coordinator" is a
  real, frequent outcome for complex real-world trials — in live testing, real
  trials routinely produced 10-40 UNKNOWN criteria each, not a tidy handful.
- **The diagnosis must be stated, not implied.** Extraction deliberately will
  not guess an unstated condition (P4/no-speculation) — a narrative that only
  says "she's been on Keytruda" (which treats many different cancers) correctly
  leaves `condition` null, and search can't run without one. State the
  diagnosis explicitly in the narrative.
- **Not medical advice, and not a replacement for the trial team** (P8) — this
  is a pre-screening aid, not a determination. The registry's own recency and
  completeness limits apply; "RECRUITING" can be stale.
- **US ClinicalTrials.gov registry only** — no international trial registries.
- **Condition matching uses keyword/token overlap, not a medical ontology** — it
  correctly avoids confident false-FAILs on subtype/genericity mismatches (see
  above), but it also can't affirmatively confirm a subtype match it isn't
  certain of; some genuinely-matching criteria will show as `UNKNOWN` rather
  than `PASS`.

## Demo prep notes

The registry is real and messy, which changes what shows up depending on when
you run this:

- The "Keytruda mom" narrative **must state the diagnosis explicitly** (e.g.
  "...advanced non-small cell lung cancer, been on Keytruda...") — see
  Limitations above.
- Live NSCLC + prior-anti-PD-1 searches naturally surface mostly **Blocked**
  and **Unclear** cards — genuinely correct, and great material for the
  "the agent read the fine print" beat and the "eligibility isn't access" beat.
  Real trials have far more UNKNOWN criteria than a hand-picked example would
  (10-40 is typical), which is honest but less tidy on screen.
- The clean **"2 open questions → answer → High"** beat is the one place a live
  search may not cooperate (a real trial with *exactly* 2 UNKNOWNs is luck of
  the draw). That exact scenario is built, tested, and proven via
  `evals/run_evals.py --stage verdicts` and `pytest tests/test_access_outlook.py`
  against a hand-built fixture trial — use that as the rehearsed fallback for
  this beat if live search doesn't hand you a clean one.
- `fixtures/cache/` warms on first live run; `OFFLINE=1` forces fixtures-only
  and is confirmed to fail over cleanly (verified: same trials, `offline: true`
  badge shows, zero network calls).
- **Timed dry-run** (automated, two consecutive runs, cache pre-warmed as above):
  narrative → assumptions card **~7.5-7.9s** (the one live Bedrock extraction
  call — this is the only step with real latency), → trial cards **+0.3s**,
  → checklist expanded and both compose drafts ready **+0.1-0.2s** more.
  **Total ~8s** end-to-end for the full technical pipeline, both runs, zero
  console errors. System latency is not the constraint on the 3-minute demo —
  the pacing is entirely the presenter's narration between beats.

## Running it

```bash
# backend (run from the repo root — backend/ is imported as a package)
pip install -r backend/requirements.txt
cp .env.example .env   # fill in BEDROCK_REGION / BEDROCK_MODEL_ID
python -m uvicorn backend.main:app --reload --port 8123

# frontend (separate terminal — Vite proxies API calls to the backend above)
cd frontend && npm install && npm run dev
```

`pytest` (offline, no credentials needed) and `python evals/run_evals.py`
(needs live Bedrock + AWS credentials) from the repo root.
