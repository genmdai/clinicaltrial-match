"""Narrative -> structured PatientProfile (LLM extraction + ontology reconciliation).

CLAUDE.md P5: drug identity comes from data/drug_ontology.json FIRST. The LLM only
extracts raw mentions + its own best-guess identification; Python then overrides
drug_brand/drug_generic/drug_class from the ontology whenever a match is found
(confidence "high", including corrected misspellings) and forces confidence "low"
for anything the ontology can't confirm. This is the same "LLM parses, Python
judges" split used for eligibility rules (CLAUDE.md §4), applied to drug facts.
"""

import difflib
import json
import re
from pathlib import Path

from strands import Agent, tool

from ..schemas import PatientProfile, PriorTreatment
from ._llm import get_model

_ONTOLOGY_PATH = Path(__file__).resolve().parents[1] / "data" / "drug_ontology.json"
_ONTOLOGY = json.loads(_ONTOLOGY_PATH.read_text())

_RELATIVE_WORDS = (
    "mom", "mother", "dad", "father", "sister", "brother", "grandma", "grandmother",
    "grandpa", "grandfather", "son", "daughter", "wife", "husband", "spouse",
    "aunt", "uncle", "cousin", "friend", "she's", "he's", "her ", "his ",
)

SYSTEM_PROMPT = """You extract a structured PatientProfile from a patient's (or their \
loved one's) free-text narrative about a serious illness, for a clinical-trial \
matching tool. Follow these rules exactly:

- subject: exactly "self" or "relative" — "relative" whenever the narrative is about \
someone else (mom, dad, sister, grandma, ...), "self" whenever the speaker is the patient.
- relation: only when subject=="relative", a single lowercase word for which relative \
("mother", "father", "sister", "brother", "grandmother", "grandfather", "wife", \
"husband", "daughter", "son", "friend", ...) — normalize "mom"->"mother", "dad"-> \
"father", etc. null when subject=="self".
- age, sex, condition, condition_raw, location_zip: leave null if not mentioned. Do \
NOT guess or fabricate. condition_raw is the patient's own words; condition is your \
normalized version (e.g. "non-small cell lung cancer") — leave condition null if you \
can't normalize it confidently, but still keep condition_raw. location_zip holds \
WHATEVER location detail was given — a ZIP/postal code, or a city/region/country \
(e.g. "Paris, France", "SW1A 1AA, UK") — not just US ZIP codes.
- condition_needs_clarification / condition_clarifying_question: ALWAYS leave both \
false/null — they are computed automatically afterward from your `gaps` list below. Do \
NOT set them yourself.
- gaps: list of ProfileGap objects — everything worth asking the patient before the \
profile is ready to search trials with. Each has: gap_id (short stable slug, e.g. \
"condition_subtype", "ecog", "biomarker_status"), field (the PatientProfile attribute \
it targets, e.g. "condition", "ecog", "biomarkers"), reason ("ambiguous" if something \
WAS stated but underspecified, "missing" if it's simply not mentioned at all), label \
(ONE natural question, in your own words, that would resolve it), answer_mode (pick \
whichever fits best: "choice", "yes_no_notsure", "no_or_specify", or "free_text"), \
options (short answer options YOU propose, only when answer_mode=="choice" — e.g. \
["Type 1", "Type 2", "Gestational", "Not sure"] for a diabetes-type question; empty \
list for every other answer_mode — never leave option generation to a hardcoded table, \
you decide the options per narrative), example_quote (a short verbatim snippet from the \
narrative motivating the question, or null), required (true ONLY for field="condition" \
gaps — searching is genuinely meaningless without a resolvable diagnosis, so these \
block the search until answered. ALWAYS false for every other field: a missing ECOG or \
biomarker status doesn't invalidate the search, it just means those specific trial \
criteria show up as an honest "unknown, confirm with the trial team" instead of a \
guess — asking is still worth doing, just never worth blocking a clean, well-specified \
narrative like "68F, NSCLC, progressed on Keytruda, zip 10001" from searching \
immediately).
  - No diagnosis at all: if condition_raw is empty (the narrative never names any \
condition), create exactly one gap with field="condition", reason="missing", \
answer_mode="free_text", label="What condition is this for?" (or a natural variant). \
This is the ONLY gap you should produce in that case — every other field is moot until \
there's a diagnosis to search on.
  - Condition ambiguity: otherwise, create exactly one gap with field="condition", \
reason="ambiguous" whenever condition_raw names only a broad diagnostic category with \
clinically distinct subtypes materially affecting which trials apply (e.g. "diabetes" — \
Type 1 vs Type 2 vs gestational are different diseases with non-overlapping trials; \
"cancer" with no organ/type; "hepatitis" with no A/B/C) AND no such subtype/detail was \
given anywhere in the narrative. Do NOT create this gap once the narrative already gives \
enough specificity (e.g. "type 2 diabetes", "non-small cell lung cancer").
  - Missing-field gaps: only once the condition itself is specific enough to search, you \
may add up to 2 more gaps (reason="missing") for fields genuinely material to matching \
that were never mentioned — e.g. ECOG performance status for an oncology condition, \
biomarker status when a targeted-therapy class is relevant, whether prior treatment \
count is 0 vs. simply unknown. Never invent more than 3 gaps total. Most narratives \
should produce 0 or 1 gap, not a checklist — only ask about fields that would \
meaningfully change which trials are relevant, and when in doubt ask fewer, not more.
- biomarkers: list of strings. If a biomarker is mentioned but status is unclear, keep \
that explicit, e.g. "EGFR unknown" rather than omitting it.
- prior_treatments: one entry per distinct treatment mentioned.
  - raw_mention: copy the patient's own words for this treatment VERBATIM, including \
any misspelling — do not correct spelling yourself.
  - drug_brand / drug_generic / drug_class: your best identification if you recognize \
the drug or treatment category; null if you don't recognize it at all. (A downstream \
step will authoritatively correct/override this against a verified drug database, so \
just do your best — don't spend effort on precision here.)
  - outcome: exactly one of "progression", "toxicity", "ongoing", or null.
    - Phrases like "stopped working", "quit responding", "scans got worse", "PSA \
rising" mean outcome="progression" and inferred=true (the patient never said the word \
"progression" — you inferred it).
    - Phrases like "couldn't tolerate", "bad side effects" mean outcome="toxicity" and \
inferred=true.
    - If the narrative just says they're currently on a treatment with no outcome \
mentioned, outcome="ongoing" and inferred=false (that's a direct statement, not an \
inference).
  - inferred: true whenever outcome or drug_class is your interpretation rather than \
the patient's literal words. false when directly stated.
  - confidence: "high" if you recognize the drug confidently, else "low".
- treatment_line: your best count of distinct prior treatment lines.
  - If prior treatments are mentioned, count them (an explicit count like "two lines \
of chemo" wins even if you only extract one raw_mention entry for it).
  - If the narrative explicitly says no treatment yet ("nothing yet", "just \
diagnosed", "treatment-naive"), set treatment_line=0.
  - If treatment history is simply never mentioned (truly unknown either way), leave \
treatment_line null — do not assume 0.
- ecog: integer ECOG performance status ONLY if explicitly stated (e.g. "ECOG 1"). \
Otherwise null.
- comorbidities: list any significant medical conditions mentioned ADDITIONAL to a \
DISTINCT primary diagnosis already identified in condition/condition_raw (e.g. "heart \
failure" alongside melanoma, "high blood pressure" alongside lung cancer). If only ONE \
condition is mentioned in the whole narrative, that condition is the primary diagnosis \
(condition/condition_raw) — never a comorbidity, even if it's a condition (like \
diabetes or hypertension) that's often secondary in other contexts. Empty list if no \
second condition is mentioned.
- assumptions: a plain-English sentence for EVERY inference you made (outcome \
inference, subject inference, drug identification, normalized condition, etc.) so a \
human can review and correct it. If information is too vague to extract most fields, \
say so here instead of guessing.

Never fabricate a value for a field the narrative doesn't support — null/empty is \
always better than a guess.

--- Worked example 1 (third person, clear progression) ---
Narrative: "my mom's been on Keytruda for a year and it stopped working, she's 68"
subject="relative", relation="mother", age=68, sex="female", prior_treatments=[{raw_mention: "Keytruda \
for a year", drug_brand: "Keytruda", drug_generic: "pembrolizumab", drug_class: \
"anti-PD-1 checkpoint inhibitor", outcome: "progression", inferred: true, confidence: \
"high"}], treatment_line=1, assumptions=["'Mom' means this is about the user's \
relative, not the user.", "Interpreted 'stopped working' as disease progression on \
Keytruda."]

--- Worked example 2 (misspelled drug, self) ---
Narrative: "I've been on keitruda for 6 months and my scans got worse"
subject="self", relation=null, prior_treatments=[{raw_mention: "keitruda for 6 months", drug_brand: \
"Keytruda", drug_generic: "pembrolizumab", drug_class: "anti-PD-1 checkpoint \
inhibitor", outcome: "progression", inferred: true, confidence: "high"}], \
treatment_line=1, assumptions=["Interpreted 'keitruda' as a likely misspelling of \
Keytruda.", "Interpreted 'scans got worse' as disease progression."]

--- Worked example 3 (adversarial vagueness — mostly nulls) ---
Narrative: "grandma is sick with cancer"
subject="relative", relation="grandmother", age=null, sex=null, condition=null, condition_raw="cancer", \
biomarkers=[], prior_treatments=[], treatment_line=null, condition_needs_clarification=false, \
condition_clarifying_question=null, gaps=[{gap_id: "condition_subtype", field: "condition", \
reason: "ambiguous", label: "What type of cancer does she have?", answer_mode: "free_text", \
options: [], example_quote: "cancer", required: true}], assumptions=["Condition is \
only described as 'cancer' with no type, stage, or treatment history given — treated \
as unknown rather than guessed.", "Follow-up needed: what type of cancer, and has she \
had any treatment?"]

--- Worked example 4 (non-oncology, only condition mentioned -> primary, not comorbidity) ---
Narrative: "I have diabetes, I'm 55, zip 94061"
subject="self", relation=null, age=55, condition=null, condition_raw="diabetes", \
comorbidities=[], location_zip="94061", condition_needs_clarification=false, \
condition_clarifying_question=null, gaps=[{gap_id: "condition_subtype", field: "condition", \
reason: "ambiguous", label: "What type of diabetes does the patient have?", \
answer_mode: "choice", options: ["Type 1", "Type 2", "Gestational", "Not sure"], \
example_quote: "I have diabetes", required: true}], assumptions=["Diabetes is the only \
condition mentioned, so it's treated as the primary diagnosis, not a comorbidity.", \
"Type of diabetes (Type 1, Type 2, gestational) is needed since eligible trials differ \
sharply by type."]

--- Worked example 5 (specific subtype already given -> no clarification needed) ---
Narrative: "I have type 2 diabetes, 60 years old, live in Paris, France"
subject="self", age=60, condition="type 2 diabetes", condition_raw="type 2 diabetes", \
comorbidities=[], location_zip="Paris, France", condition_needs_clarification=false, \
condition_clarifying_question=null, gaps=[], assumptions=["Type 2 diabetes is specific \
enough to search trials directly — no clarification needed."]

--- Worked example 6 (condition specific, but a material field is simply missing) ---
Narrative: "I was just diagnosed with non-small cell lung cancer, I'm 62, haven't \
started any treatment"
subject="self", age=62, condition="non-small cell lung cancer", \
condition_raw="non-small cell lung cancer", treatment_line=0, biomarkers=[], ecog=null, \
condition_needs_clarification=false, condition_clarifying_question=null, \
gaps=[{gap_id: "biomarker_status", field: "biomarkers", reason: "missing", \
label: "Has she had biomarker testing done, like EGFR, ALK, or PD-L1?", \
answer_mode: "yes_no_notsure", options: [], example_quote: null, required: false}], \
assumptions=["Explicit 'haven't started any treatment' means treatment_line=0, not \
unknown.", "No biomarker testing mentioned — many NSCLC trials require specific \
biomarker status, so this is worth asking rather than assuming untested."]

--- Worked example 7 (no diagnosis mentioned at all) ---
Narrative: "she's 68 and has been on Keytruda for a year"
subject="relative", relation=null, age=68, condition=null, condition_raw=null, \
prior_treatments=[{raw_mention: "Keytruda for a year", drug_brand: "Keytruda", \
drug_generic: "pembrolizumab", drug_class: "anti-PD-1 checkpoint inhibitor", \
outcome: null, inferred: false, confidence: "high"}], condition_needs_clarification=false, \
condition_clarifying_question=null, gaps=[{gap_id: "condition_missing", field: "condition", \
reason: "missing", label: "What condition is this for?", answer_mode: "free_text", \
options: [], example_quote: null, required: true}], assumptions=["No condition was \
named anywhere in the narrative — every other field is on hold until there's a \
diagnosis to search trials against."]
"""


def _build_ontology_index() -> dict[str, dict]:
    index: dict[str, dict] = {}
    for entry in _ONTOLOGY:
        for name in (entry.get("brand"), entry.get("generic")):
            if name:
                index[name.lower()] = entry
    return index


_ONTOLOGY_INDEX = _build_ontology_index()


def _match_drug(raw_mention: str) -> tuple[dict | None, bool]:
    """Returns (ontology_entry_or_None, was_fuzzy_correction)."""
    text = raw_mention.lower()
    for name in sorted(_ONTOLOGY_INDEX, key=len, reverse=True):
        if name in text:
            return _ONTOLOGY_INDEX[name], False

    tokens = re.findall(r"[a-z][a-z\-]{3,}", text)
    for token in tokens:
        close = difflib.get_close_matches(token, _ONTOLOGY_INDEX.keys(), n=1, cutoff=0.75)
        if close:
            return _ONTOLOGY_INDEX[close[0]], True
    return None, False


def _guess_subject(narrative: str) -> str:
    lower = narrative.lower()
    return "relative" if any(w in lower for w in _RELATIVE_WORDS) else "self"


_RELATION_ALIASES = {
    "mom": "mother", "mother": "mother",
    "dad": "father", "father": "father",
    "sister": "sister", "brother": "brother",
    "grandma": "grandmother", "grandmother": "grandmother",
    "grandpa": "grandfather", "grandfather": "grandfather",
    "wife": "wife", "husband": "husband", "spouse": "spouse",
    "son": "son", "daughter": "daughter",
    "aunt": "aunt", "uncle": "uncle", "cousin": "cousin", "friend": "friend",
}


def _guess_relation(narrative: str) -> str | None:
    lower = narrative.lower()
    for word, normalized in _RELATION_ALIASES.items():
        if word in lower:
            return normalized
    return None


def _reconcile(profile: PatientProfile, narrative: str) -> PatientProfile:
    extra_assumptions = []
    reconciled: list[PriorTreatment] = []

    for pt in profile.prior_treatments:
        entry, was_fuzzy = _match_drug(pt.raw_mention)
        if entry:
            if was_fuzzy:
                shown_name = entry["brand"] or entry["generic"]
                extra_assumptions.append(
                    f'Matched "{pt.raw_mention}" to {shown_name} ({entry["generic"]}) '
                    "via fuzzy drug-name matching against the verified ontology."
                )
            pt = pt.model_copy(update={
                "drug_brand": entry["brand"],
                "drug_generic": entry["generic"],
                "drug_class": entry["class"],
                "rxnorm_ingredient": entry.get("rxnorm_ingredient"),
                "confidence": "high",
            })
        else:
            pt = pt.model_copy(update={"confidence": "low"})
        reconciled.append(pt)

    subject = profile.subject if profile.subject in ("self", "relative") else _guess_subject(narrative)
    relation = (profile.relation or _guess_relation(narrative)) if subject == "relative" else None

    treatment_line = profile.treatment_line
    if treatment_line is None and reconciled:
        treatment_line = len(reconciled)

    # Cap defensively — the prompt asks for at most 3, but never trust the LLM
    # as the sole enforcement of "don't ask a wall of questions."
    gaps = profile.gaps[:3]
    condition_gap = next((g for g in gaps if g.field == "condition"), None)

    return profile.model_copy(update={
        "prior_treatments": reconciled,
        "subject": subject,
        "relation": relation,
        "treatment_line": treatment_line,
        "assumptions": [*profile.assumptions, *extra_assumptions],
        "gaps": gaps,
        # Legacy fields are a pure projection of gaps — single source of
        # truth, so evals/cases.json's existing assertions keep passing
        # regardless of how the richer gaps list evolves.
        "condition_needs_clarification": condition_gap is not None,
        "condition_clarifying_question": condition_gap.label if condition_gap else None,
    })


def _run_extraction(narrative: str) -> PatientProfile:
    agent = Agent(model=get_model(), system_prompt=SYSTEM_PROMPT)
    result = agent(narrative, structured_output_model=PatientProfile)
    if result.structured_output is None:
        raise ValueError("model returned no structured output")
    return result.structured_output


@tool
def extract_profile(narrative: str) -> dict:
    """Extract a structured PatientProfile from a patient/caregiver narrative.

    Args:
        narrative: Free-text description of the patient's condition, treatment
            history, and situation, e.g. "my mom's been on Keytruda for a year
            and it stopped working, she's 68".

    Returns:
        {"profile": <PatientProfile JSON>} on success, or {"error": "<message>"}
        on failure (retried once internally on the first failure) — never
        raises into the agent loop.
    """
    try:
        try:
            profile = _run_extraction(narrative)
        except Exception:  # noqa: BLE001 — one defensive retry before giving up
            profile = _run_extraction(narrative)
        profile = _reconcile(profile, narrative)
        return {"profile": profile.model_dump()}
    except Exception as e:  # noqa: BLE001 — tool boundary: must never raise into the agent loop (CLAUDE.md §6)
        return {"error": str(e)}
