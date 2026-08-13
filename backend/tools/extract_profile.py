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
- age, sex, condition, condition_raw, location_zip: leave null if not mentioned. Do \
NOT guess or fabricate. condition_raw is the patient's own words; condition is your \
normalized version (e.g. "non-small cell lung cancer") — leave condition null if you \
can't normalize it confidently, but still keep condition_raw.
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
- comorbidities: list any significant medical conditions mentioned that are NOT the \
primary condition being treated (e.g. "heart failure", "diabetes"). Empty list if none \
mentioned.
- assumptions: a plain-English sentence for EVERY inference you made (outcome \
inference, subject inference, drug identification, normalized condition, etc.) so a \
human can review and correct it. If information is too vague to extract most fields, \
say so here instead of guessing.

Never fabricate a value for a field the narrative doesn't support — null/empty is \
always better than a guess.

--- Worked example 1 (third person, clear progression) ---
Narrative: "my mom's been on Keytruda for a year and it stopped working, she's 68"
subject="relative", age=68, sex="female", prior_treatments=[{raw_mention: "Keytruda \
for a year", drug_brand: "Keytruda", drug_generic: "pembrolizumab", drug_class: \
"anti-PD-1 checkpoint inhibitor", outcome: "progression", inferred: true, confidence: \
"high"}], treatment_line=1, assumptions=["'Mom' means this is about the user's \
relative, not the user.", "Interpreted 'stopped working' as disease progression on \
Keytruda."]

--- Worked example 2 (misspelled drug, self) ---
Narrative: "I've been on keitruda for 6 months and my scans got worse"
subject="self", prior_treatments=[{raw_mention: "keitruda for 6 months", drug_brand: \
"Keytruda", drug_generic: "pembrolizumab", drug_class: "anti-PD-1 checkpoint \
inhibitor", outcome: "progression", inferred: true, confidence: "high"}], \
treatment_line=1, assumptions=["Interpreted 'keitruda' as a likely misspelling of \
Keytruda.", "Interpreted 'scans got worse' as disease progression."]

--- Worked example 3 (adversarial vagueness — mostly nulls) ---
Narrative: "grandma is sick with cancer"
subject="relative", age=null, sex=null, condition=null, condition_raw="cancer", \
biomarkers=[], prior_treatments=[], treatment_line=null, assumptions=["Condition is \
only described as 'cancer' with no type, stage, or treatment history given — treated \
as unknown rather than guessed.", "Follow-up needed: what type of cancer, and has she \
had any treatment?"]
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

    treatment_line = profile.treatment_line
    if treatment_line is None and reconciled:
        treatment_line = len(reconciled)

    return profile.model_copy(update={
        "prior_treatments": reconciled,
        "subject": subject,
        "treatment_line": treatment_line,
        "assumptions": [*profile.assumptions, *extra_assumptions],
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
