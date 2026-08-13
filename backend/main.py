"""FastAPI app — orchestrates the deterministic pipeline (extract -> confirm ->
search -> parse -> check -> score) around the LLM tool calls. CLAUDE.md P7: no
server-side persistence — every endpoint is stateless; the frontend holds
profile/trial state in browser memory and resends what it needs (rules, study,
verdicts) for /recompute and /compose.

Architecture note: the pipeline order is fixed and deterministic (not decided
by an autonomous agent tool-loop) — this is what makes the matching verdict
reproducible and testable (CLAUDE.md §4). The LLM calls inside extract_profile
and parse_criteria are still real Strands Agent calls; only the orchestration
connecting them is plain Python.
"""

import json
import os
import re

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .api_models import ComposeRequest, ExtractRequest, MatchRequest, RecomputeRequest
from .tools.access_outlook import access_outlook
from .tools.check_eligibility import check_eligibility, extract_marker_name
from .tools.compose import compose_doctor_note, compose_email
from .tools.extract_profile import extract_profile
from .tools.fetch_trial import fetch_trial, get_contact
from .tools.geo import nearest_sites, zip_to_latlon
from .tools.parse_criteria import parse_criteria_stream
from .tools.search_trials import search_trials

app = FastAPI(title="ClinicalCohort")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

_TIER_RANK = {"High": 0, "Moderate": 1, "Unclear": 2, "Low": 3, "Blocked": 4}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/extract")
def extract(payload: ExtractRequest) -> dict:
    return extract_profile(payload.narrative)


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


def _resolve_patient_location(profile: dict) -> tuple[float | None, float | None]:
    zip_code = profile.get("location_zip")
    if not zip_code:
        return None, None
    coords = zip_to_latlon(zip_code)
    return (coords["lat"], coords["lon"]) if coords else (None, None)


@app.post("/match")
async def match(payload: MatchRequest):
    async def stream():
        profile = payload.profile
        condition = profile.get("condition") or profile.get("condition_raw")
        if not condition:
            yield _sse({
                "type": "error",
                "message": "I don't have enough information about the diagnosis yet "
                           "— could you say more about the condition?",
            })
            return

        patient_lat, patient_lon = _resolve_patient_location(profile)

        yield _sse({"type": "progress", "message": f"Searching for recruiting trials matching {condition}…"})

        offline_mode = os.environ.get("OFFLINE") == "1"
        search_result = search_trials(
            condition, lat=patient_lat, lon=patient_lon, radius_mi=payload.radius_mi, offline=offline_mode,
        )
        if "error" in search_result and not offline_mode:
            # Transparent fixtures fallback — CLAUDE.md §6: never crash the demo.
            search_result = search_trials(
                condition, lat=patient_lat, lon=patient_lon, radius_mi=payload.radius_mi, offline=True,
            )
            offline_mode = True
        if "error" in search_result:
            yield _sse({"type": "error", "message": search_result["error"]})
            return

        trials = search_result["trials"]
        yield _sse({
            "type": "progress",
            "message": f"Found {len(trials)} recruiting trials",
            "offline": offline_mode,
        })

        studies = {}
        for t in trials:
            nct_id = t["nct_id"]
            fetch_result = fetch_trial(nct_id, offline=offline_mode)
            if "error" not in fetch_result:
                studies[nct_id] = fetch_result["study"]

        parse_inputs = [
            {
                "nct_id": nct_id,
                "criteria_text": study.get("protocolSection", {})
                    .get("eligibilityModule", {}).get("eligibilityCriteria", ""),
            }
            for nct_id, study in studies.items()
        ]
        rules_by_trial: dict[str, list[dict]] = {}
        async for nct_id, result in parse_criteria_stream(parse_inputs):
            if "error" in result:
                yield _sse({
                    "type": "progress",
                    "message": f"Could not parse eligibility criteria for {nct_id} — skipping it.",
                })
                continue
            rules_by_trial[nct_id] = result["rules"]
            yield _sse({"type": "progress", "message": f"Checking eligibility for {nct_id}… ✓"})

        results = []
        for t in trials:
            nct_id = t["nct_id"]
            if nct_id not in rules_by_trial:
                continue
            study = studies[nct_id]
            protocol = study.get("protocolSection", {})

            check_result = check_eligibility(rules_by_trial[nct_id], profile)
            if "error" in check_result:
                continue
            contact = get_contact(study, patient_lat, patient_lon)
            outlook_result = access_outlook(
                nct_id, check_result["verdicts"], study, patient_lat, patient_lon, payload.radius_mi,
            )
            if "error" in outlook_result:
                continue
            locations = protocol.get("contactsLocationsModule", {}).get("locations", [])
            sites = (
                nearest_sites(locations, patient_lat, patient_lon, n=3)
                if patient_lat is not None and patient_lon is not None else []
            )

            results.append({
                "summary": t,
                "study": study,
                "rules": rules_by_trial[nct_id],
                "verdicts": check_result["verdicts"],
                "rollup": check_result["rollup"],
                "outlook": outlook_result["outlook"],
                "nearest_sites": sites,
                "contact": contact,
            })

        results.sort(key=lambda r: _TIER_RANK.get(r["outlook"]["tier"], 99))
        yield _sse({
            "type": "result",
            "offline": offline_mode,
            "patient_lat": patient_lat,
            "patient_lon": patient_lon,
            "trials": results,
        })

    return StreamingResponse(stream(), media_type="text/event-stream")


def _apply_answer(profile: dict, rules: list[dict], answer) -> dict:
    """Deterministic, instant patch of a single profile field from a follow-up
    answer — NOT another LLM call, so "answering re-runs ONLY check_eligibility
    + access_outlook" (CLAUDE.md Phase 5) actually stays instant. Covers the
    field types the demo's follow-up questions actually produce (numeric
    fields, biomarker status, and "no prior treatment"); anything else is left
    for the user to redescribe in the main chat instead.
    """
    if answer is None:
        return profile
    rule = next((r for r in rules if r["rule_id"] == answer.rule_id), None)
    if rule is None:
        return profile

    profile = dict(profile)
    text_lower = answer.text.lower()
    field = rule["field"]

    if field in ("ecog", "age"):
        m = re.search(r"\d+", answer.text)
        if m:
            profile[field] = int(m.group())
    elif field == "biomarker":
        marker = extract_marker_name(str(rule["value"]))
        if any(w in text_lower for w in ("positive", "yes", "present", "+")):
            status = "positive"
        elif any(w in text_lower for w in ("negative", "no", "absent", "-")):
            status = "negative"
        else:
            status = "unknown"
        biomarkers = [b for b in profile.get("biomarkers", []) if marker.lower() not in b.lower()]
        biomarkers.append(f"{marker} {status}")
        profile["biomarkers"] = biomarkers
    elif field in ("treatment_naive", "prior_therapy_class"):
        if any(w in text_lower for w in ("no", "never", "none", "hasn't", "has not", "naive")):
            profile["treatment_line"] = 0
            profile["prior_treatments"] = []

    return profile


@app.post("/recompute")
def recompute(payload: RecomputeRequest) -> dict:
    """Re-run ONLY check_eligibility + access_outlook (both pure Python) after
    a follow-up question is answered — CLAUDE.md Phase 5's "instant re-render,
    tier pill visibly upgrades" demo beat.
    """
    try:
        profile = _apply_answer(payload.profile, payload.rules, payload.answer)

        check_result = check_eligibility(payload.rules, profile)
        if "error" in check_result:
            return {"error": check_result["error"]}

        outlook_result = access_outlook(
            payload.nct_id, check_result["verdicts"], payload.study,
            payload.patient_lat, payload.patient_lon,
        )
        if "error" in outlook_result:
            return {"error": outlook_result["error"]}

        return {
            "profile": profile,
            "verdicts": check_result["verdicts"],
            "rollup": check_result["rollup"],
            "outlook": outlook_result["outlook"],
        }
    except Exception as e:  # noqa: BLE001 — endpoint boundary: never a raw 500, CLAUDE.md §6 spirit
        return {"error": str(e)}


@app.post("/compose")
def compose(payload: ComposeRequest) -> dict:
    try:
        if payload.variant == "email":
            return compose_email(
                payload.profile, payload.nct_id, payload.trial_title or "", payload.verdicts, payload.contact,
            )
        if payload.variant == "doctor_note":
            return compose_doctor_note(
                payload.profile, payload.nct_id, payload.study or {}, payload.verdicts,
                payload.contact, payload.nearest_site,
            )
        return {"error": f"unknown compose variant {payload.variant!r}"}
    except Exception as e:  # noqa: BLE001 — endpoint boundary: never a raw 500, CLAUDE.md §6 spirit
        return {"error": str(e)}
