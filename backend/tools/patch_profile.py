"""Apply structured answers to specific PatientProfile `gaps`, without
re-running full narrative extraction on concatenated text.

Deterministic Python handles the shapes that are safe to parse directly (a
digit for age/ecog, picking one of the LLM-proposed `options` for a
choice-mode gap). Anything needing semantic normalization — an open-ended
free-text answer — gets ONE narrow LLM call scoped to just that field, never
a full narrative re-extraction (CLAUDE.md §4: "LLM parses, Python judges",
applied here at field granularity instead of whole-profile granularity).

CLAUDE.md P2: an explicit "not sure"/"I don't know" answer must stay an
unresolved gap, never get coerced into a guessed value.
"""

import re

from pydantic import BaseModel
from strands import Agent, tool

from ..schemas import PatientProfile, ProfileGap
from ._llm import get_model

_UNSURE_WORDS = ("not sure", "unsure", "don't know", "dont know", "no idea")
_NUMERIC_FIELDS = {"age", "ecog", "treatment_line"}
_STRING_FIELDS = {"condition", "sex", "location_zip"}
_LIST_FIELDS = {"biomarkers", "comorbidities"}


def _is_unsure(text: str) -> bool:
    return any(w in text.lower() for w in _UNSURE_WORDS)


def _apply_numeric(text: str) -> int | None:
    m = re.search(r"\d+", text)
    return int(m.group()) if m else None


def _apply_choice(gap: ProfileGap, text: str) -> str | None:
    """Deterministic path for a choice-mode answer matching one of the gap's
    own LLM-proposed options — e.g. picking "Type 2" for a diabetes-subtype
    gap. Returns None (falls through to the LLM path) on anything that isn't
    an exact option match, including the "Not sure" option itself.
    """
    text_stripped = text.strip()
    matched = next((o for o in gap.options if o.lower() == text_stripped.lower()), None)
    if matched is None or _is_unsure(matched):
        return None
    return matched


def _patch_condition_choice(profile: PatientProfile, choice_text: str) -> PatientProfile:
    base = profile.condition_raw or profile.condition or ""
    normalized = base if choice_text.lower() in base.lower() else f"{choice_text} {base}".strip()
    return profile.model_copy(update={"condition": normalized.lower(), "condition_raw": normalized})


_PATCH_SYSTEM_PROMPT = """You are patching exactly ONE field of an \
already-extracted PatientProfile, based on the patient's answer to a single \
follow-up question. Do not touch or reinterpret any other field — only \
normalize this one answer for this one field.

Given the field name, its current value, the question that was asked, and \
the patient's raw answer, return:
- value: the normalized value for that field, matching its existing type \
(a string for "condition"/"sex"/"location_zip", an integer for \
"age"/"ecog"/"treatment_line", a list of strings for \
"biomarkers"/"comorbidities" — for "biomarkers" each string is \
"<MARKER> <status>", e.g. "EGFR positive", "PD-L1 unknown"; keep any \
markers the answer didn't mention out of the list entirely). For list \
fields, "value" is the FULL replacement list — carry over any existing \
entries from "Current value" that the answer doesn't touch, don't drop \
them. Null if the answer doesn't resolve anything.
- resolved: true whenever the patient's answer is definite, even if the \
definite answer is a negative that adds nothing to a list field — e.g. "No, \
no biomarker testing was done" resolves the "biomarkers" gap with \
value=[] (an empty list IS a real, deliberate answer: testing wasn't done, \
so there's nothing to add, and the question shouldn't be asked again). \
resolved is false ONLY when the answer itself expresses genuine \
uncertainty (e.g. "not sure", "I don't know", "maybe") — in that case \
value MUST be null. A definite "yes" that lacks enough detail to set a real \
value (e.g. "yes, testing was done" with no marker or result named) is \
ALSO resolved=true — set value=null (never invent the missing detail) and \
say what's known in "assumption" instead (e.g. "Biomarker testing was \
done; specific marker/result not yet provided."). The question has been \
answered either way — it must not keep re-appearing just because the exact \
structured value couldn't be determined.
- assumption: one short plain-English sentence describing what you did \
(e.g. "Confirmed condition as Type 2 diabetes from your answer.", or what \
you learned even without a structured value), for the patient-facing \
assumptions list. Empty string only if resolved is false.
"""


class _FieldPatch(BaseModel):
    value: str | int | list[str] | None = None
    resolved: bool = False
    assumption: str = ""


def _coerce_value(field: str, value):
    """The LLM is asked to match the field's existing type but isn't
    trustworthy on shape — coerce or reject rather than let a malformed
    value (e.g. a list where a string was expected) slip through. Returns
    None for anything that can't be sanely coerced, including unsupported
    fields (e.g. "prior_treatments" is too structured to patch this way).
    """
    if value is None:
        return None
    if field in _STRING_FIELDS:
        if isinstance(value, list):
            return " ".join(str(v) for v in value).strip() or None
        return str(value)
    if field in _NUMERIC_FIELDS:
        if isinstance(value, (list, dict)):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    if field in _LIST_FIELDS:
        if isinstance(value, str):
            return [value]
        if isinstance(value, list):
            return [str(v) for v in value]
        return None
    return None


def _patch_via_llm(
    profile: PatientProfile, gap: ProfileGap | None, field: str, text: str,
) -> tuple[PatientProfile, str | None, bool]:
    question = gap.label if gap else f"Please clarify {field}."
    current_value = getattr(profile, field, None)
    narrative = (
        f'Field: "{field}"\n'
        f"Current value: {current_value!r}\n"
        f'Question asked: "{question}"\n'
        f'Patient answer: "{text}"'
    )
    agent = Agent(model=get_model(), system_prompt=_PATCH_SYSTEM_PROMPT)
    result = agent(narrative, structured_output_model=_FieldPatch)
    patch = result.structured_output
    if patch is None or not patch.resolved:
        return profile, None, False
    value = _coerce_value(field, patch.value)
    if value is None:
        # Resolved (a definite answer), but nothing structured to set — e.g.
        # "yes, testing was done" with no marker/result given. Still counts
        # as answered: the gap shouldn't loop forever just because the fixed
        # yes/no/not-sure buttons can't capture more detail. Record what's
        # known as an assumption and leave the field itself untouched rather
        # than inventing a value.
        return profile, (patch.assumption or None), True
    update = {field: value}
    if field == "condition":
        # condition_raw is the patient's own words — a follow-up answer is
        # still their own words, so keep the two in sync the same way
        # extract_profile does on the first turn.
        update["condition_raw"] = value if isinstance(value, str) else profile.condition_raw
    try:
        # model_copy(update=...) skips validation entirely — re-validate via
        # the constructor so a malformed/coerced value can never slip through.
        updated = PatientProfile(**{**profile.model_dump(), **update})
    except Exception:  # noqa: BLE001 — a malformed LLM value must never break the turn
        return profile, None, False
    return updated, (patch.assumption or None), True


def _apply_one_answer(
    profile: PatientProfile, gap: ProfileGap | None, field: str, text: str,
) -> tuple[PatientProfile, str | None, bool]:
    if field == "condition" and gap and gap.answer_mode == "choice" and gap.options:
        matched = _apply_choice(gap, text)
        if matched is not None:
            updated = _patch_condition_choice(profile, matched)
            return updated, f'Confirmed condition as "{updated.condition_raw}" from your answer.', True

    if field in _NUMERIC_FIELDS and not _is_unsure(text):
        value = _apply_numeric(text)
        if value is not None:
            updated = profile.model_copy(update={field: value})
            return updated, f"Set {field.replace('_', ' ')} to {value} from your answer.", True

    if _is_unsure(text):
        return profile, None, False  # explicit "not sure" — leave the gap open (P2)

    return _patch_via_llm(profile, gap, field, text)


@tool
def patch_profile(profile: dict, answers: list[dict]) -> dict:
    """Patch specific PatientProfile fields from answers to open `gaps`,
    without re-running full narrative extraction.

    Args:
        profile: The current PatientProfile as already extracted/patched.
        answers: [{"gap_id": str, "field": str, "text": str}, ...] — one or
            more answers to specific open gaps from this turn.

    Returns:
        {"profile": <PatientProfile JSON>} on success, or {"error": "<message>"}
        on failure — never raises into the agent loop.
    """
    try:
        current = PatientProfile(**profile)
        gaps_by_id = {g.gap_id: g for g in current.gaps}
        remaining_gap_ids = {g.gap_id for g in current.gaps}
        extra_assumptions: list[str] = []

        for answer in answers:
            gap_id = answer.get("gap_id")
            field = answer.get("field")
            text = (answer.get("text") or "").strip()
            if not field or not text:
                continue
            gap = gaps_by_id.get(gap_id)
            try:
                current, note, resolved = _apply_one_answer(current, gap, field, text)
            except Exception:  # noqa: BLE001 — one bad answer must not sink the whole batch
                resolved, note = False, None
            if note:
                extra_assumptions.append(note)
            if resolved and gap_id:
                remaining_gap_ids.discard(gap_id)

        remaining_gaps = [g for g in current.gaps if g.gap_id in remaining_gap_ids]
        condition_gap = next((g for g in remaining_gaps if g.field == "condition"), None)
        current = current.model_copy(update={
            "gaps": remaining_gaps,
            "assumptions": [*current.assumptions, *extra_assumptions],
            "condition_needs_clarification": condition_gap is not None,
            "condition_clarifying_question": condition_gap.label if condition_gap else None,
        })
        return {"profile": current.model_dump()}
    except Exception as e:  # noqa: BLE001 — tool boundary: must never raise into the agent loop
        return {"error": str(e)}
