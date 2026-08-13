"""FastAPI app entrypoint — TrialPath API (CLAUDE.md §4).

Thin HTTP layer over the existing Strands tools. No logic lives here beyond
request/response shaping and stitching the pipeline together: extract_profile
-> search_trials -> fetch_trial -> parse_criteria -> check_eligibility. Every
tool already traps its own errors into {"error": ...} (CLAUDE.md §6); this
layer preserves that shape per-trial so one bad trial never sinks the batch.
"""

from fastapi import Body, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .tools.check_eligibility import check_eligibility
from .tools.compose import compose_packet
from .tools.enrich_trial_access import enrich_trial_access
from .tools.extract_profile import extract_profile
from .tools.fetch_trial import fetch_trial
from .tools.parse_criteria import parse_criteria
from .tools.search_trials import search_trials

app = FastAPI(title="ClinicalCohort")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/profile")
def api_profile(body: dict = Body(...)):
    """Narrative -> structured PatientProfile (extract_profile.py, LLM)."""
    narrative = (body.get("narrative") or "").strip()
    if not narrative:
        return {"error": "narrative is required"}
    return extract_profile(narrative=narrative)


@app.post("/api/match")
def api_match(body: dict = Body(...)):
    """PatientProfile -> candidate trials with per-criterion verdicts.

    Pipeline: search_trials(condition) -> for each candidate, fetch_trial +
    parse_criteria (LLM, disk-cached per NCT ID) -> check_eligibility
    (deterministic). A trial that fails any pipeline step is returned with
    its own "error" instead of dropping the whole response.
    """
    profile = body.get("profile") or {}
    condition = (profile.get("condition") or profile.get("condition_raw") or "").strip()
    if not condition:
        return {"error": "profile has no condition to search for"}

    offline = bool(body.get("offline", False))
    intervention = (body.get("intervention") or None) or None
    radius_mi = body.get("radius_mi", 50.0)
    lat = body.get("lat")
    lon = body.get("lon")

    search_res = search_trials(
        condition=condition,
        lat=lat,
        lon=lon,
        radius_mi=radius_mi,
        intervention=intervention,
        offline=offline,
    )
    if "error" in search_res:
        return {"error": search_res["error"], "stage": "search"}

    results = []
    for trial in search_res["trials"]:
        nct_id = trial["nct_id"]

        study_res = fetch_trial(nct_id=nct_id, offline=offline)
        if "error" in study_res:
            results.append({"trial": trial, "error": study_res["error"], "stage": "fetch"})
            continue
        protocol = study_res["study"].get("protocolSection", {})
        criteria_text = protocol.get("eligibilityModule", {}).get("eligibilityCriteria", "")
        contacts_locations = protocol.get("contactsLocationsModule", {})
        sponsor = protocol.get("sponsorCollaboratorsModule", {}).get("leadSponsor", {}).get("name")

        rules_res = parse_criteria(nct_id=nct_id, criteria_text=criteria_text)
        if "error" in rules_res:
            results.append({"trial": trial, "error": rules_res["error"], "stage": "parse_criteria"})
            continue

        elig_res = check_eligibility(rules=rules_res["rules"], profile=profile)
        if "error" in elig_res:
            results.append({"trial": trial, "error": elig_res["error"], "stage": "check_eligibility"})
            continue

        results.append({
            "trial": {**trial, "sponsor": sponsor},
            "rules": rules_res["rules"],
            "verdicts": elig_res["verdicts"],
            "rollup": elig_res["rollup"],
            "central_contacts": contacts_locations.get("centralContacts", []),
            "locations": contacts_locations.get("locations", []),
        })

    return {"results": results}


@app.post("/api/packet")
def api_packet(body: dict = Body(...)):
    """Compose a copy-ready access packet for the selected trial (compose.py)."""
    return compose_packet(
        profile=body.get("profile") or {},
        trial=body.get("trial") or {},
        verdicts=body.get("verdicts") or [],
    )


@app.post("/api/enrich")
def api_enrich(body: dict = Body(...)):
    """Bright Data enrichment for a selected trial/site (enrich_trial_access.py).

    Call after the patient has picked a trial from /api/match — this is
    supplementary public access info (contacts, referral, documents), never
    part of matching/eligibility, and it never receives patient data: only
    trial identity ({"nct_id", "title", "sponsor"}) and site identity
    ({"facility", "city", "state", "hospital_domain"}) are read from the body.
    A Bright Data failure returns {"error": ...} rather than raising, so the
    caller can show the core trial result regardless.
    """
    return enrich_trial_access(
        trial=body.get("trial") or {},
        site=body.get("site") or {},
        offline=bool(body.get("offline", False)),
    )
