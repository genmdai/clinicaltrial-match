"""Rules x PatientProfile -> CriterionVerdict[] — pure Python, deterministic, no LLM.

CLAUDE.md §4: "LLM parses, Python judges." parse_criteria.py (LLM) turns free text
into EligibilityRule[]; this module is the reproducible, testable judge. P2/P3
apply: missing data -> UNKNOWN + a follow-up question, never a guessed FAIL/PASS,
and any rule the parser wasn't confident about is capped at UNKNOWN too.
"""

import re

from strands import tool

from ..schemas import CriterionVerdict, EligibilityRule, PatientProfile


def _normalize(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _unknown(rule: EligibilityRule, reason: str, follow_up: str) -> CriterionVerdict:
    return CriterionVerdict(
        rule_id=rule.rule_id,
        verdict="UNKNOWN",
        reason=reason,
        source_quote=rule.source_quote,
        follow_up_question=follow_up,
    )


def _verdict(rule: EligibilityRule, ok: bool, reason: str) -> CriterionVerdict:
    return CriterionVerdict(
        rule_id=rule.rule_id,
        verdict="PASS" if ok else "FAIL",
        reason=reason,
        source_quote=rule.source_quote,
        follow_up_question=None,
    )


def _compare(operator: str, actual: int, value: int) -> bool | None:
    if operator == "gte":
        return actual >= value
    if operator == "lte":
        return actual <= value
    if operator == "eq":
        return actual == value
    return None


def _evaluate_age(rule: EligibilityRule, profile: PatientProfile) -> CriterionVerdict:
    if profile.age is None:
        return _unknown(rule, "Patient's age is not known.", "What is the patient's age?")
    ok = _compare(rule.operator, profile.age, int(rule.value))
    if ok is None:
        return _unknown(rule, f"Unsupported age operator {rule.operator!r}.", "Can you confirm this criterion with the trial team?")
    return _verdict(rule, ok, f"Patient age {profile.age} {'meets' if ok else 'does not meet'} the requirement ({rule.operator} {rule.value}).")


def _evaluate_ecog(rule: EligibilityRule, profile: PatientProfile) -> CriterionVerdict:
    if profile.ecog is None:
        return _unknown(rule, "Patient's ECOG performance status is not known.", "What is the patient's ECOG performance status?")
    ok = _compare(rule.operator, profile.ecog, int(rule.value))
    if ok is None:
        return _unknown(rule, f"Unsupported ecog operator {rule.operator!r}.", "Can you confirm this criterion with the trial team?")
    return _verdict(rule, ok, f"Patient ECOG {profile.ecog} {'meets' if ok else 'does not meet'} the requirement ({rule.operator} {rule.value}).")


def _evaluate_condition(rule: EligibilityRule, profile: PatientProfile) -> CriterionVerdict:
    text = f"{profile.condition or ''} {profile.condition_raw or ''}".strip().lower()
    if not text:
        return _unknown(rule, "Patient's diagnosed condition is not known.", "What is the patient's diagnosed condition?")
    ok = str(rule.value).lower() in text
    return _verdict(rule, ok, f"Patient's condition {'matches' if ok else 'does not appear to match'} the requirement ({rule.value}).")


def _biomarker_label(value: str) -> str:
    return value if "status" in value.lower() else f"{value} status"


def _evaluate_biomarker(rule: EligibilityRule, profile: PatientProfile) -> CriterionVerdict:
    keyword = str(rule.value).lower()
    label = _biomarker_label(str(rule.value))
    follow_up = f"What is the patient's {label}?"
    for b in profile.biomarkers:
        b_lower = b.lower()
        if keyword not in b_lower:
            continue
        if "unknown" in b_lower:
            return _unknown(rule, f"Biomarker {label} is explicitly unknown.", follow_up)
        negative = "negative" in b_lower or b_lower.strip().endswith("-")
        ok = not negative if rule.operator == "must_have" else True
        return _verdict(rule, ok, f"Biomarker {label} recorded as {b!r}.")
    return _unknown(rule, f"No information on {label}.", follow_up)


def _evaluate_treatment_naive(rule: EligibilityRule, profile: PatientProfile) -> CriterionVerdict:
    if profile.prior_treatments:
        first = profile.prior_treatments[0]
        return _verdict(rule, False, f"Patient has received prior systemic treatment ({first.drug_brand or first.drug_generic or first.raw_mention}), so the treatment-naive requirement is not met.")
    if profile.treatment_line == 0:
        return _verdict(rule, True, "Patient has had no prior systemic treatment.")
    return _unknown(rule, "Whether the patient has had any prior systemic treatment is not known.", "Has the patient had any prior systemic treatment?")


def _evaluate_not_had_class(rule: EligibilityRule, profile: PatientProfile) -> CriterionVerdict:
    keyword = _normalize(str(rule.value))
    for pt in profile.prior_treatments:
        haystack = _normalize(f"{pt.drug_class or ''} {pt.drug_generic or ''} {pt.drug_brand or ''}")
        if keyword and keyword in haystack:
            return _verdict(rule, False, f"Patient's prior treatment with {pt.drug_brand or pt.drug_generic} ({pt.drug_class}) falls under the excluded class ({rule.value}).")
    if profile.prior_treatments or profile.treatment_line == 0:
        return _verdict(rule, True, f"None of the patient's known prior treatments fall under the excluded class ({rule.value}).")
    return _unknown(rule, "Prior treatment history is not known.", "Has the patient received any prior systemic therapy, and if so which drugs or drug classes?")


_EVALUATORS = {
    ("age", "gte"): _evaluate_age,
    ("age", "lte"): _evaluate_age,
    ("age", "eq"): _evaluate_age,
    ("ecog", "gte"): _evaluate_ecog,
    ("ecog", "lte"): _evaluate_ecog,
    ("ecog", "eq"): _evaluate_ecog,
    ("condition", "contains"): _evaluate_condition,
    ("condition", "eq"): _evaluate_condition,
    ("biomarker", "must_have"): _evaluate_biomarker,
    ("biomarker", "contains"): _evaluate_biomarker,
    ("treatment_naive", "must_have"): _evaluate_treatment_naive,
    ("treatment_naive", "eq"): _evaluate_treatment_naive,
    ("prior_therapy_class", "not_had"): _evaluate_not_had_class,
}


def _rollup(verdicts: list[CriterionVerdict]) -> str:
    if any(v.verdict == "FAIL" for v in verdicts):
        return "Likely not eligible"
    unknown_count = sum(1 for v in verdicts if v.verdict == "UNKNOWN")
    if unknown_count:
        return f"Possibly eligible — {unknown_count} open question{'s' if unknown_count != 1 else ''}"
    return "Looks eligible (confirm with team)"


def evaluate(rules: list[EligibilityRule], profile: PatientProfile) -> tuple[list[CriterionVerdict], str]:
    """Typed entry point for direct Python callers (e.g. unit tests)."""
    verdicts = []
    for rule in rules:
        if rule.parse_confidence == "low":
            verdicts.append(_unknown(rule, "This criterion's wording was ambiguous to parse confidently.", "Can you confirm this criterion with the trial team?"))
            continue
        evaluator = _EVALUATORS.get((rule.field, rule.operator))
        if evaluator is None:
            verdicts.append(_unknown(rule, "This criterion type isn't automatically checkable yet.", "Can you confirm this criterion with the trial team?"))
            continue
        verdicts.append(evaluator(rule, profile))
    return verdicts, _rollup(verdicts)


@tool
def check_eligibility(rules: list[dict], profile: dict) -> dict:
    """Evaluate a trial's parsed eligibility rules against a patient profile.

    Args:
        rules: List of EligibilityRule dicts (from parse_criteria).
        profile: PatientProfile dict (from extract_profile).

    Returns:
        {"verdicts": [CriterionVerdict, ...], "rollup": "<summary string>"} on
        success, or {"error": "<message>"} on failure — never raises into the
        agent loop.
    """
    try:
        rule_objs = [EligibilityRule(**r) for r in rules]
        profile_obj = PatientProfile(**profile)
        verdicts, rollup = evaluate(rule_objs, profile_obj)
        return {"verdicts": [v.model_dump() for v in verdicts], "rollup": rollup}
    except Exception as e:  # noqa: BLE001 — tool boundary: must never raise into the agent loop (CLAUDE.md §6)
        return {"error": str(e)}
