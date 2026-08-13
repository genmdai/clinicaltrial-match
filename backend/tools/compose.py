"""Compose a trial access packet — plain templating, no LLM, no send (CLAUDE.md P6).

Deterministic string formatting only: everything here is already-known structured
data (PatientProfile, TrialSummary, CriterionVerdict[]). The output is a draft the
user copies themselves — this module has no SMTP client and no send path.
"""

from strands import tool

from ..schemas import CriterionVerdict, PatientProfile


def _treatment_line(profile: PatientProfile) -> str:
    parts = []
    for pt in profile.prior_treatments:
        name = pt.drug_brand or pt.drug_generic or pt.raw_mention
        parts.append(name + (f" ({pt.outcome})" if pt.outcome else ""))
    return "; ".join(parts) if parts else "none recorded"


def _profile_summary(profile: PatientProfile) -> str:
    bits = []
    if profile.age is not None:
        bits.append(f"age {profile.age}")
    if profile.sex:
        bits.append(profile.sex)
    if profile.condition or profile.condition_raw:
        bits.append(profile.condition or profile.condition_raw)
    if profile.biomarkers:
        bits.append(", ".join(profile.biomarkers))
    header = ", ".join(bits) if bits else "profile in progress"
    return f"{header}. Prior treatment: {_treatment_line(profile)}."


@tool
def compose_packet(profile: dict, trial: dict, verdicts: list[dict]) -> dict:
    """Build a copy-ready trial access packet from already-computed data.

    Args:
        profile: PatientProfile dict.
        trial: TrialSummary dict for the selected trial.
        verdicts: CriterionVerdict dicts for the selected trial (from
            check_eligibility), used to summarize confirmed vs. open items.

    Returns:
        {"packet": {...}} with plain-text sections (patient_summary, trial,
        criteria_summary, next_steps) on success, or {"error": "<message>"} on
        failure — never raises into the agent loop. Every field is composed
        text only; nothing here sends anything.
    """
    try:
        profile_obj = PatientProfile(**profile)
        verdict_objs = [CriterionVerdict(**v) for v in verdicts]

        confirmed = [v for v in verdict_objs if v.verdict == "PASS"]
        open_items = [v for v in verdict_objs if v.verdict == "UNKNOWN"]

        phase = ", ".join(trial.get("phase") or []) or "Phase not listed"
        nearest = trial.get("nearest_site") or {}
        site_line = nearest.get("facility") or "Site not listed in registry"
        if nearest.get("city"):
            site_line += f", {nearest['city']}"
            if nearest.get("state"):
                site_line += f", {nearest['state']}"
        if nearest.get("distance_mi") is not None:
            site_line += f" ({nearest['distance_mi']} mi away)"

        packet = {
            "patient_summary": _profile_summary(profile_obj),
            "trial": (
                f"{trial.get('title', 'Untitled study')} — {trial.get('nct_id', '')} — "
                f"{phase} — {site_line}"
            ),
            "criteria_summary": (
                f"{len(confirmed)} criteria confirmed from patient information · "
                f"{len(open_items)} still need verification"
                + ("." if not open_items else ": " + "; ".join(v.follow_up_question or v.reason for v in open_items[:5]))
            ),
            "next_steps": [
                "Confirm remaining open criteria with the study team.",
                "Share this summary with the treating physician.",
                "Contact the study site to begin formal screening.",
            ],
            "caveat": (
                "Informational only — not medical advice. Eligibility is determined "
                "by the trial team. Confirm everything with your care team."
            ),
        }
        return {"packet": packet}
    except Exception as e:  # noqa: BLE001 — tool boundary: must never raise into the agent loop (CLAUDE.md §6)
        return {"error": str(e)}
