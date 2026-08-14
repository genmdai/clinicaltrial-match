"""FastAPI app — orchestrates the deterministic pipeline (extract -> search ->
parse -> check -> score) around the LLM tool calls. CLAUDE.md P7: no
server-side persistence — every endpoint is stateless; the frontend holds
profile/trial state in browser memory and resends what it needs (rules, study
fields, answers) for /screen and /compose.

Architecture note: the pipeline order is fixed and deterministic (not decided
by an autonomous agent tool-loop) — this is what makes the matching verdict
reproducible and testable (CLAUDE.md §4). The LLM calls inside extract_profile
and parse_criteria are still real Strands Agent calls; only the orchestration
connecting them, and the adaptive cross-trial narrowing in next_question.py,
are plain Python.

/match no longer gates on a confirmed profile — it starts scoring as soon as a
condition is extracted, and streams results incrementally (`candidates` ->
`trial_ready`/`trial_error` per trial -> `done`) so the UI can show every
candidate immediately instead of waiting for the full batch. Narrowing after
that point is /screen's job: given the full ordered list of answers so far, it
replays them from the untouched base profile (never patches forward) and
returns the next best cross-trial question.
"""

import asyncio
import json
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .api_models import (
    ComposeRequest,
    ExtractRequest,
    MatchRequest,
    PatchProfileRequest,
    PublicAccessLinksRequest,
    ScreenRequest,
)
from .schemas import EligibilityRule, PatientProfile
from .tools.access_outlook import access_outlook
from .tools.check_eligibility import check_eligibility
from .tools.compose import compose_doctor_note, compose_email
from .tools.extract_profile import extract_profile
from .tools.patch_profile import patch_profile
from .tools.fetch_trial import fetch_trial, get_contact
from .tools.geo import nearest_sites, resolve_location
from .tools.next_question import (
    TRAVEL_RADIUS_CLUSTER_KEY,
    fold_ledger,
    pick_next_question,
)
from .tools.parse_criteria import parse_criteria_stream
from .tools.public_access_links import public_access_links
from .tools.search_trials import search_trials

app = FastAPI(title="Pathway")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/extract")
def extract(payload: ExtractRequest) -> dict:
    return extract_profile(payload.narrative)


@app.post("/patch-profile")
def patch_profile_endpoint(payload: PatchProfileRequest) -> dict:
    return patch_profile(payload.profile, [a.model_dump() for a in payload.answers])


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


def _resolve_patient_location(profile: dict, offline: bool) -> tuple[float | None, float | None]:
    location_text = profile.get("location_zip")
    if not location_text:
        return None, None
    coords = resolve_location(location_text, offline=offline)
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
        if profile.get("condition_needs_clarification") and profile.get("condition_clarifying_question"):
            # The condition is only a broad category (e.g. "diabetes" with no type) —
            # searching now would return a meaningless mix of non-overlapping trials.
            # Mirrors the "no condition at all" bail-out above; a caller that wants to
            # search anyway can clear this flag on the profile it resends (the
            # frontend does this once the user directly edits/confirms the condition).
            yield _sse({"type": "error", "message": profile["condition_clarifying_question"]})
            return

        offline_mode = os.environ.get("OFFLINE") == "1"
        patient_lat, patient_lon = _resolve_patient_location(profile, offline_mode)

        # Fixed narration stages surfaced in the UI (ProgressStream / LoadingSteps) —
        # keep this exact wording in sync with frontend/src/components/matchStages.js.
        yield _sse({"type": "progress", "message": "Searching recruiting trials…"})

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
            "type": "candidates",
            "condition": condition,
            "total_count": search_result.get("total_count", len(trials)),
            "trials": trials,
            "offline": offline_mode,
        })
        if not trials:
            yield _sse({"type": "done", "offline": offline_mode, "patient_lat": patient_lat, "patient_lon": patient_lon})
            return

        yield _sse({"type": "progress", "message": "Checking recruiting sites…"})

        # Fetch full study records in parallel — up to 50 candidates now, a
        # sequential loop here would be the biggest latency line item.
        fetch_results = await asyncio.gather(
            *(asyncio.to_thread(fetch_trial, t["nct_id"], offline_mode) for t in trials)
        )
        studies: dict[str, dict] = {}
        for t, fetch_result in zip(trials, fetch_results, strict=True):
            nct_id = t["nct_id"]
            if "error" in fetch_result:
                yield _sse({"type": "trial_error", "nct_id": nct_id, "message": fetch_result["error"]})
                continue
            studies[nct_id] = fetch_result["study"]

        summary_by_id = {t["nct_id"]: t for t in trials}
        parse_inputs = [
            {
                "nct_id": nct_id,
                "criteria_text": study.get("protocolSection", {})
                    .get("eligibilityModule", {}).get("eligibilityCriteria", ""),
            }
            for nct_id, study in studies.items()
        ]

        yield _sse({"type": "progress", "message": "Comparing eligibility criteria…"})

        hospital_access_stage_sent = False
        total_to_parse = len(parse_inputs)
        parsed_count = 0
        async for nct_id, result in parse_criteria_stream(parse_inputs):
            parsed_count += 1
            # Bedrock parsing (parse_criteria_stream) is the real bottleneck for
            # the rest of this loop's wall-clock time, but the fixed narration
            # stages above only fire once each — without this, the UI freezes
            # on "Looking for hospital access information…" for the entire
            # remaining batch. This gives the wait an honest live counter.
            yield _sse({"type": "parse_progress", "completed": parsed_count, "total": total_to_parse})
            if "error" in result:
                yield _sse({"type": "trial_error", "nct_id": nct_id, "message": result["error"]})
                continue

            study = studies[nct_id]
            protocol = study.get("protocolSection", {})
            rules = result["rules"]

            check_result = check_eligibility(rules, profile)
            if "error" in check_result:
                yield _sse({"type": "trial_error", "nct_id": nct_id, "message": check_result["error"]})
                continue
            if not hospital_access_stage_sent:
                yield _sse({"type": "progress", "message": "Looking for hospital access information…"})
                hospital_access_stage_sent = True
            contact = get_contact(study, patient_lat, patient_lon)
            outlook_result = access_outlook(
                nct_id, check_result["verdicts"], study, patient_lat, patient_lon, payload.radius_mi,
            )
            if "error" in outlook_result:
                yield _sse({"type": "trial_error", "nct_id": nct_id, "message": outlook_result["error"]})
                continue
            locations = protocol.get("contactsLocationsModule", {}).get("locations", [])
            status_module = protocol.get("statusModule", {})
            sites = nearest_sites(locations, patient_lat, patient_lon, n=3)

            yield _sse({
                "type": "trial_ready",
                "nct_id": nct_id,
                "summary": summary_by_id[nct_id],
                "status_module": status_module,
                "locations": locations,
                "rules": rules,
                "verdicts": check_result["verdicts"],
                "rollup": check_result["rollup"],
                "outlook": outlook_result["outlook"],
                "nearest_sites": sites,
                "contact": contact,
            })

        yield _sse({"type": "progress", "message": "Finalizing results…"})
        yield _sse({"type": "done", "offline": offline_mode, "patient_lat": patient_lat, "patient_lon": patient_lon})

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.post("/screen")
def screen(payload: ScreenRequest) -> dict:
    """Stateless cross-trial narrowing step (CLAUDE.md P7): given the full
    ordered list of answers so far and the candidate trials already fetched by
    /match's `trial_ready` events, replays every answer from the untouched base
    profile (never patches forward — see next_question.fold_ledger) and
    returns the next best cross-trial question. Both fold_ledger and
    pick_next_question are pure Python — no LLM call on this path, so every
    answer/retraction is instant.
    """
    try:
        base_profile = PatientProfile(**payload.base_profile)
        answers = [a.model_dump() for a in payload.answers]

        rules_by_trial: dict[str, list[EligibilityRule]] = {}
        trial_bundles = []
        for t in payload.trials:
            rules = [EligibilityRule(**r) for r in t.rules]
            rules_by_trial[t.nct_id] = rules
            trial_bundles.append({
                "nct_id": t.nct_id,
                "rules": rules,
                "status_module": t.status_module,
                "locations": t.locations,
                "contact": t.contact,
                "nearest_recruiting_distance_mi": t.nearest_recruiting_distance_mi,
            })

        fold_result = fold_ledger(base_profile, answers, trial_bundles, payload.patient_lat, payload.patient_lon)

        distance_by_id = {t.nct_id: t.nearest_recruiting_distance_mi for t in payload.trials}
        open_trials_for_ranking = [
            {
                "nct_id": nct_id,
                "rules": rules_by_trial[nct_id],
                "verdicts": fold_result["trials"][nct_id]["verdicts"],
                "nearest_recruiting_distance_mi": distance_by_id.get(nct_id),
            }
            for nct_id in fold_result["open_trial_ids"]
        ]
        asked_cluster_keys = {a["cluster_key"] for a in answers}
        radius_answered = any(a["cluster_key"] == TRAVEL_RADIUS_CLUSTER_KEY for a in answers)
        next_question = pick_next_question(
            open_trials_for_ranking, asked_cluster_keys,
            payload.patient_lat, payload.patient_lon, radius_answered,
        )

        return {
            "profile": fold_result["profile"].model_dump(),
            "trials": {
                nct_id: {
                    "verdicts": [v.model_dump() for v in t["verdicts"]],
                    "rollup": t["rollup"],
                    "outlook": t["outlook"].model_dump(),
                }
                for nct_id, t in fold_result["trials"].items()
            },
            "ledger": fold_result["ledger"],
            "open_trial_ids": fold_result["open_trial_ids"],
            "next_question": next_question,
            "no_further_questions": next_question is None,
        }
    except Exception as e:  # noqa: BLE001 — endpoint boundary: never a raw 500, CLAUDE.md §6 spirit
        return {"error": str(e)}


@app.post("/trial-access-links")
def trial_access_links(payload: PublicAccessLinksRequest) -> dict:
    """Lazy, isolated from the main screening flow — only called when the
    Trial Access view opens for one specific trial, never from /match. Bright
    Data being unset/down/rate-limited must never affect anything else in the
    app (see public_access_links.py's own docstring re: unverified API shape).
    """
    return public_access_links(payload.facility_name, payload.sponsor_name)


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
