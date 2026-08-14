"""Cross-trial adaptive question selection — pure Python, deterministic, no LLM
(CLAUDE.md §4: "LLM parses, Python judges" — this module only clusters/ranks
verdicts that check_eligibility.py already produced, it never re-implements
eligibility logic itself).

The screening loop asks ONE question at a time: the fact shared by the most
currently-open trials as an unresolved (UNKNOWN) criterion — e.g. "EGFR exon 20
insertion — decides 8 of the 9 studies below" means 8 open trials each have
their own UNKNOWN tied to that same fact, NOT a prediction of how many will be
ruled out once answered. The ruled-out/remaining counts shown per ledger entry
come from `fold_ledger`, computed AFTER a real answer is applied, by replaying
every answer so far from the untouched base profile (never patching forward —
that's what makes retracting an earlier answer correct).
"""

import re

from ..schemas import CriterionVerdict, EligibilityRule, PatientProfile
from .access_outlook import compute_access_outlook
from .check_eligibility import (
    GENERIC_FOLLOWUP,
    _condition_tokens,
    evaluate,
    extract_marker_name,
)

# These fields have a follow_up_question that's actually about a specific,
# shared fact (vs. the GENERIC_FOLLOWUP catch-all) — see check_eligibility.py.
# field="other" is handled separately in cluster_key(): most of it is free text
# with no shared structure across trials (informed consent, site logistics, ...)
# and stays per-trial ("needs verification" on that trial's own card), but
# parse_criteria.py's LLM also extracts a normalized `topic` (e.g.
# "brain_metastases") whenever an "other" criterion describes a concrete,
# reusable, patient-answerable fact — those DO cluster, keyed dynamically on
# `f"other:{topic}"` rather than a hardcoded field name, so newly-recurring
# criterion patterns become askable without a code change here.
_CLUSTERABLE_FIELDS = {"age", "ecog", "treatment_naive", "prior_therapy_class", "biomarker", "condition"}

# _apply_answer's treatment_naive/prior_therapy_class branch only resolves
# anything on a negative ("No, never treated") answer — a bare "Yes" doesn't
# say *which* drug/class, so it can't resolve a not_had exclusion. These
# clusters must not offer a symmetric Yes/No/Not-sure; "Yes" opens a free-text
# follow-up instead.
_NO_ONLY_FIELDS = {"treatment_naive", "prior_therapy_class"}
# age/ecog need an actual number, never a yes/no button.
_FREE_TEXT_FIELDS = {"age", "ecog"}

TRAVEL_RADIUS_CLUSTER_KEY = "__travel_radius__"
_RADIUS_OPTIONS = [
    {"label": "Up to 50 miles", "radius_mi": 50.0},
    {"label": "Up to 150 miles", "radius_mi": 150.0},
    {"label": "Anywhere in the US", "radius_mi": None},
]
_RADIUS_BY_LABEL = {o["label"]: o["radius_mi"] for o in _RADIUS_OPTIONS}
RADIUS_CHOICES = [o["label"] for o in _RADIUS_OPTIONS]
_TIGHTEST_RADIUS_MI = _RADIUS_OPTIONS[0]["radius_mi"]


def cluster_key(rule: EligibilityRule, verdict: CriterionVerdict) -> str | None:
    """None means "not clusterable" — always falls through to per-trial display."""
    if verdict.verdict != "UNKNOWN":
        return None
    if not verdict.follow_up_question or verdict.follow_up_question == GENERIC_FOLLOWUP:
        return None
    if rule.field == "other":
        # Dynamically extracted fact (see parse_criteria.py's topic/topic_question)
        # — clusterable purely because the LLM found a reusable, patient-answerable
        # fact here, not because "other" is in the fixed field allowlist below.
        return f"other:{rule.topic}" if rule.topic else None
    if rule.field not in _CLUSTERABLE_FIELDS:
        return None
    if rule.field == "biomarker":
        return f"biomarker:{extract_marker_name(str(rule.value)).upper()}"
    if rule.field == "condition":
        tokens = _condition_tokens(str(rule.value))
        return f"condition:{'-'.join(sorted(tokens))}" if tokens else None
    return rule.field


def _answer_mode(key: str) -> str:
    base_field = key.split(":")[0]
    if base_field in _FREE_TEXT_FIELDS:
        return "free_text"
    if base_field in _NO_ONLY_FIELDS:
        return "no_or_specify"
    return "yes_no_notsure"  # biomarker, condition


def find_clusters(open_trials: list[dict]) -> dict[str, list[tuple[str, EligibilityRule, CriterionVerdict]]]:
    """`open_trials`: [{"nct_id", "rules": [EligibilityRule,...], "verdicts": [CriterionVerdict,...]}].

    Returns cluster_key -> [(nct_id, rule, verdict), ...], at most one entry per
    trial per cluster (a trial with two same-cluster UNKNOWNs still only counts
    once toward decides_count).
    """
    clusters: dict[str, list[tuple[str, EligibilityRule, CriterionVerdict]]] = {}
    for trial in open_trials:
        rules_by_id = {r.rule_id: r for r in trial["rules"]}
        seen_this_trial: set[str] = set()
        for verdict in trial["verdicts"]:
            rule = rules_by_id.get(verdict.rule_id)
            if rule is None:
                continue
            key = cluster_key(rule, verdict)
            if key is None or key in seen_this_trial:
                continue
            seen_this_trial.add(key)
            clusters.setdefault(key, []).append((trial["nct_id"], rule, verdict))
    return clusters


def _build_eligibility_question(key: str, entries: list[tuple[str, EligibilityRule, CriterionVerdict]], total_open: int) -> dict:
    nct_id, rule, verdict = min(entries, key=lambda e: e[0])
    affected = sorted({e[0] for e in entries})
    return {
        "cluster_key": key,
        "gap_id": key,  # alias so the frontend can render this via the same
        # GapInput component it uses for pre-search ProfileGaps, without this
        # module's tested decides_count/tiebreak logic changing at all
        "field": rule.field,
        "rule_id": rule.rule_id,
        "label": verdict.follow_up_question,
        "answer_mode": _answer_mode(key),
        "decides_count": len(affected),
        "total_open": total_open,
        "affected_trial_ids": affected,
        "example_quote": rule.source_quote,
        "example_nct_id": nct_id,
    }


def travel_radius_question(open_trials: list[dict], patient_lat: float | None, patient_lon: float | None, radius_answered: bool) -> dict | None:
    """`open_trials` items need a `nearest_recruiting_distance_mi` key. Only
    offered when the patient's location is known (mirrors access_outlook's own
    null-guard) and only when it would actually decide >=2 trials at the
    tightest radius option — otherwise it wouldn't separate anything.
    """
    if patient_lat is None or patient_lon is None or radius_answered:
        return None
    affected = [
        t for t in open_trials
        if t.get("nearest_recruiting_distance_mi") is not None
        and t["nearest_recruiting_distance_mi"] > _TIGHTEST_RADIUS_MI
    ]
    if len(affected) < 2:
        return None
    return {
        "cluster_key": TRAVEL_RADIUS_CLUSTER_KEY,
        "gap_id": TRAVEL_RADIUS_CLUSTER_KEY,
        "field": TRAVEL_RADIUS_CLUSTER_KEY,
        "rule_id": None,
        "label": "How far could you travel for study visits?",
        "answer_mode": "choice",
        "choices": RADIUS_CHOICES,
        "options": RADIUS_CHOICES,  # alias — GapInput reads `options`
        "decides_count": len(affected),
        "total_open": len(open_trials),
        "affected_trial_ids": sorted(t["nct_id"] for t in affected),
    }


def pick_next_question(
    open_trials: list[dict],
    asked_cluster_keys: set[str],
    patient_lat: float | None = None,
    patient_lon: float | None = None,
    radius_answered: bool = False,
) -> dict | None:
    """`open_trials`: [{"nct_id", "rules", "verdicts", "nearest_recruiting_distance_mi"}].

    Returns the single highest-impact question, or None once nothing left
    would decide >=2 of the remaining open trials (the "no further questions"
    stop condition) — deterministic tiebreak on (decides_count desc, cluster_key).
    """
    candidates = []
    for key, entries in find_clusters(open_trials).items():
        if key in asked_cluster_keys:
            continue
        if len({e[0] for e in entries}) < 2:
            continue
        candidates.append(_build_eligibility_question(key, entries, len(open_trials)))

    radius_q = travel_radius_question(open_trials, patient_lat, patient_lon, radius_answered)
    if radius_q is not None:
        candidates.append(radius_q)

    if not candidates:
        return None
    candidates.sort(key=lambda c: (-c["decides_count"], c["cluster_key"]))
    return candidates[0]


def is_open(tier: str, nearest_recruiting_distance_mi: float | None, radius_mi: float | None) -> bool:
    """A trial is "still open" unless a hard eligibility FAIL blocked it
    (tier == "Blocked", unchanged P9/P3 logic) or it fails a chosen travel
    radius. Radius filtering never touches tier — an unknown distance is never
    held against a trial (patient location vs. registry location gaps are
    already handled honestly elsewhere, e.g. access_outlook's null-lat/lon path).
    """
    if tier == "Blocked":
        return False
    if radius_mi is None or nearest_recruiting_distance_mi is None:
        return True
    return nearest_recruiting_distance_mi <= radius_mi


def _apply_single_answer(profile: PatientProfile, rule: EligibilityRule, text: str) -> PatientProfile:
    """Same keyword-matching behavior as the original main.py `_apply_answer`
    (now the only copy — main.py's /screen calls this exclusively via
    fold_ledger), just restructured to take one representative EligibilityRule
    directly instead of a rule list + rule_id lookup, since callers here
    already have the cluster's representative rule in hand.
    """
    text_lower = text.lower()
    field = rule.field
    data = profile.model_dump()

    if field in ("ecog", "age"):
        m = re.search(r"\d+", text)
        if m:
            data[field] = int(m.group())
    elif field == "biomarker":
        marker = extract_marker_name(str(rule.value))
        if any(w in text_lower for w in ("positive", "yes", "present", "+")):
            status = "positive"
        elif any(w in text_lower for w in ("negative", "no", "absent", "-")):
            status = "negative"
        else:
            status = "unknown"
        biomarkers = [b for b in data.get("biomarkers", []) if marker.lower() not in b.lower()]
        biomarkers.append(f"{marker} {status}")
        data["biomarkers"] = biomarkers
    elif field in ("treatment_naive", "prior_therapy_class"):
        if any(w in text_lower for w in ("no", "never", "none", "hasn't", "has not", "naive")):
            data["treatment_line"] = 0
            data["prior_treatments"] = []
    elif field == "other" and rule.topic:
        if any(w in text_lower for w in ("no", "not", "never", "none", "negative", "hasn't", "has not")):
            status = "no"
        elif any(w in text_lower for w in ("yes", "positive", "has", "present", "does")):
            status = "yes"
        else:
            status = "unclear"
        other_facts = dict(data.get("other_facts", {}))
        other_facts[rule.topic] = status
        data["other_facts"] = other_facts

    return PatientProfile(**data)


def _profile_after(base_profile: PatientProfile, answers: list[dict], rule_by_id: dict[str, EligibilityRule], upto: int) -> PatientProfile:
    profile = base_profile
    for answer in answers[:upto]:
        if answer.get("rule_id") is None:
            continue  # travel-radius answers don't touch the profile
        rule = rule_by_id.get(answer["rule_id"])
        if rule is None:
            continue
        profile = _apply_single_answer(profile, rule, answer["text"])
    return profile


def _radius_after(answers: list[dict], upto: int) -> float | None:
    radius = None
    for answer in answers[:upto]:
        if answer["cluster_key"] == TRAVEL_RADIUS_CLUSTER_KEY:
            radius = _RADIUS_BY_LABEL.get(answer["text"])
    return radius


def _score_trials_at(
    trials: list[dict], profile: PatientProfile, radius: float | None,
    patient_lat: float | None, patient_lon: float | None,
) -> tuple[set[str], dict[str, dict]]:
    open_ids: set[str] = set()
    per_trial: dict[str, dict] = {}
    for t in trials:
        verdicts, rollup = evaluate(t["rules"], profile)
        outlook = compute_access_outlook(
            t["nct_id"], verdicts, t["status_module"], t["locations"], t["contact"],
            patient_lat, patient_lon, radius_mi=radius if radius is not None else 50.0,
        )
        per_trial[t["nct_id"]] = {"verdicts": verdicts, "rollup": rollup, "outlook": outlook}
        if is_open(outlook.tier, t.get("nearest_recruiting_distance_mi"), radius):
            open_ids.add(t["nct_id"])
    return open_ids, per_trial


def fold_ledger(
    base_profile: PatientProfile,
    answers: list[dict],
    trials: list[dict],
    patient_lat: float | None,
    patient_lon: float | None,
) -> dict:
    """Replays `answers` in order from the untouched `base_profile` — never
    patches forward from a previously-derived profile — so retracting an
    earlier answer and refolding the remaining list is always correct, not
    order-dependent bookkeeping.

    `trials`: [{"nct_id", "rules": [EligibilityRule,...], "status_module": dict,
    "locations": list[dict], "contact": dict, "nearest_recruiting_distance_mi"}].
    `answers`: [{"cluster_key", "field", "rule_id" (None for travel radius),
    "text", "ledger_label"}], in application order.

    Returns {"profile", "trials": {nct_id: {verdicts, rollup, outlook}},
    "ledger": [{"index","cluster_key","label","ruled_out_count","remaining_count"}],
    "open_trial_ids"}.
    """
    rule_by_id = {r.rule_id: r for t in trials for r in t["rules"]}

    profile = _profile_after(base_profile, answers, rule_by_id, 0)
    radius = _radius_after(answers, 0)
    open_ids, per_trial = _score_trials_at(trials, profile, radius, patient_lat, patient_lon)

    ledger = []
    for k in range(1, len(answers) + 1):
        next_profile = _profile_after(base_profile, answers, rule_by_id, k)
        next_radius = _radius_after(answers, k)
        next_open_ids, next_per_trial = _score_trials_at(trials, next_profile, next_radius, patient_lat, patient_lon)

        ledger.append({
            "index": k - 1,
            "cluster_key": answers[k - 1]["cluster_key"],
            "label": answers[k - 1]["ledger_label"],
            "ruled_out_count": len(open_ids - next_open_ids),
            "remaining_count": len(next_open_ids),
        })
        profile, open_ids, per_trial = next_profile, next_open_ids, next_per_trial

    return {
        "profile": profile,
        "trials": per_trial,
        "ledger": ledger,
        "open_trial_ids": sorted(open_ids),
    }
