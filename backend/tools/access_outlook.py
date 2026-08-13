"""CriterionVerdicts + trial record + geo -> AccessOutlook — pure Python,
deterministic, no LLM (CLAUDE.md §5/§2 P9).

The user's question isn't "am I eligible?" (that's the evidence layer, from
check_eligibility.py) — it's "how likely can I actually get in?" This is the
answer layer: four transparent components, each a tier band with plain-English
evidence, combined into one overall tier. P9 is absolute: tiers + evidence,
NEVER a percentage or invented probability — there is no outcome data to
calibrate one.
"""

from datetime import date, datetime

from strands import tool

from ..schemas import AccessOutlook, CriterionVerdict, OutlookComponent
from .geo import haversine_miles

_SCORE_BY_BAND = {"strong": 1.0, "fair": 0.6, "weak": 0.2}


def _parse_ct_date(s: str | None) -> date | None:
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m"):
        try:
            return datetime.strptime(s, fmt).date()  # noqa: DTZ007 — CT.gov dates are calendar dates only, no timezone
        except ValueError:
            continue
    return None


def _combine_bands(bands: list[str]) -> str:
    if any(b == "weak" for b in bands):
        return "weak"
    if any(b == "fair" for b in bands):
        return "fair"
    return "strong"


def _eligibility_fit(verdicts: list[CriterionVerdict]) -> tuple[OutlookComponent, str | None, int]:
    fails = [v for v in verdicts if v.verdict == "FAIL"]
    unknowns = [v for v in verdicts if v.verdict == "UNKNOWN"]
    passes = [v for v in verdicts if v.verdict == "PASS"]

    if fails:
        blocking = fails[0]
        component = OutlookComponent(
            name="eligibility_fit", score=0.0, band="weak",
            evidence=[f"Blocking criterion: {blocking.reason}"],
        )
        return component, blocking.rule_id, len(unknowns)

    total = len(passes) + len(unknowns)
    ratio = (len(passes) / total) if total else 1.0
    band = "strong" if not unknowns else "fair"
    evidence = [f"{len(passes)} of {total} evaluated criteria pass." if total else "No checkable criteria found."]
    if unknowns:
        evidence.append(f"{len(unknowns)} open question{'s' if len(unknowns) != 1 else ''} remain.")
    component = OutlookComponent(name="eligibility_fit", score=round(ratio, 2), band=band, evidence=evidence)
    return component, None, len(unknowns)


def _recruitment_momentum(status_module: dict) -> OutlookComponent:
    overall_status = status_module.get("overallStatus", "")
    evidence = [f"Trial-level status: {overall_status or 'unknown'}."]

    if overall_status == "RECRUITING":
        status_band = "strong"
    elif overall_status == "NOT_YET_RECRUITING":
        status_band = "fair"
    else:
        status_band = "weak"

    today = date.today()  # noqa: DTZ011 — comparing against calendar dates only, no timezone involved

    last_update = _parse_ct_date((status_module.get("lastUpdatePostDateStruct") or {}).get("date"))
    if last_update:
        months_ago = (today - last_update).days / 30.44
        if months_ago < 6:
            recency_band = "strong"
        elif months_ago < 18:
            recency_band = "fair"
        else:
            recency_band = "weak"
        evidence.append(f"Registry last updated {last_update.isoformat()} ({months_ago:.0f} months ago).")
    else:
        recency_band = "fair"
        evidence.append("Registry last-update date not available.")

    completion = _parse_ct_date((status_module.get("primaryCompletionDateStruct") or {}).get("date"))
    completion_band = "strong"
    if completion:
        months_away = (completion - today).days / 30.44
        if months_away < 0:
            completion_band = "weak"
            evidence.append(
                f"Primary completion date {completion.isoformat()} has already passed, but the trial "
                f"is still listed as {overall_status} — registry may be stale."
            )
        elif months_away < 4:
            completion_band = "weak"
            evidence.append(
                f"Primary completion date {completion.isoformat()} is only {months_away:.0f} months "
                "away — trial may be closing to enrollment soon."
            )
        else:
            evidence.append(f"Primary completion date {completion.isoformat()} ({months_away:.0f} months away).")

    band = _combine_bands([status_band, recency_band, completion_band])
    return OutlookComponent(name="recruitment_momentum", score=_SCORE_BY_BAND[band], band=band, evidence=evidence)


def _geographic_access(
    locations: list[dict], patient_lat: float | None, patient_lon: float | None, radius_mi: float
) -> OutlookComponent:
    if patient_lat is None or patient_lon is None:
        return OutlookComponent(
            name="geographic_access", score=0.6, band="fair",
            evidence=["Location not provided — distance to sites is unknown."],
        )

    recruiting_dists = []
    for loc in locations:
        geo_point = loc.get("geoPoint")
        if not geo_point or loc.get("status") != "RECRUITING":
            continue
        recruiting_dists.append(haversine_miles(patient_lat, patient_lon, geo_point["lat"], geo_point["lon"]))

    if not recruiting_dists:
        return OutlookComponent(
            name="geographic_access", score=0.2, band="weak",
            evidence=["No individually recruiting site found near the patient."],
        )

    nearest = min(recruiting_dists)
    within_radius = sum(1 for d in recruiting_dists if d <= radius_mi)
    if nearest < 50:
        band = "strong"
    elif nearest < 150:
        band = "fair"
    else:
        band = "weak"

    evidence = [
        f"Nearest individually recruiting site is {nearest:.0f} miles away.",
        f"{within_radius} of {len(locations)} sites are recruiting within {radius_mi:.0f} miles.",
    ]
    return OutlookComponent(name="geographic_access", score=_SCORE_BY_BAND[band], band=band, evidence=evidence)


def _contactability(central_contacts: list[dict], locations: list[dict]) -> OutlookComponent:
    for c in central_contacts:
        if c.get("email"):
            return OutlookComponent(
                name="contactability", score=1.0, band="strong",
                evidence=[f"Central trial contact available with email ({c.get('name', 'contact')})."],
            )
    for c in central_contacts:
        if c.get("phone"):
            return OutlookComponent(
                name="contactability", score=0.6, band="fair",
                evidence=[f"Central trial contact available by phone only ({c.get('name', 'contact')})."],
            )
    for loc in locations:
        for c in loc.get("contacts", []):
            if c.get("email") or c.get("phone"):
                return OutlookComponent(
                    name="contactability", score=0.6, band="fair",
                    evidence=[f"Site-level contact available at {loc.get('facility', 'a trial site')}."],
                )
    return OutlookComponent(
        name="contactability", score=0.2, band="weak",
        evidence=["No direct contact found — only sponsor information is available."],
    )


def _tier_from_bands(bands: list[str]) -> str:
    if all(b == "strong" for b in bands):
        return "High"
    if any(b == "weak" for b in bands):
        return "Low"
    return "Moderate"


def compute_access_outlook(
    nct_id: str,
    verdicts: list[CriterionVerdict],
    status_module: dict,
    locations: list[dict],
    central_contacts: list[dict],
    patient_lat: float | None = None,
    patient_lon: float | None = None,
    radius_mi: float = 50.0,
) -> AccessOutlook:
    """Typed entry point for direct Python callers (e.g. unit tests)."""
    eligibility_component, blocking_rule_id, open_questions = _eligibility_fit(verdicts)
    momentum_component = _recruitment_momentum(status_module)
    geo_component = _geographic_access(locations, patient_lat, patient_lon, radius_mi)
    contact_component = _contactability(central_contacts, locations)
    components = [eligibility_component, momentum_component, geo_component, contact_component]

    if blocking_rule_id:
        tier = "Blocked"
    elif open_questions >= 3:
        tier = "Unclear"
    else:
        tier = _tier_from_bands([c.band for c in components])

    return AccessOutlook(
        trial_nct_id=nct_id,
        tier=tier,
        components=components,
        blocking_rule_id=blocking_rule_id,
        open_questions=open_questions,
    )


@tool
def access_outlook(
    nct_id: str,
    verdicts: list[dict],
    study: dict,
    patient_lat: float | None = None,
    patient_lon: float | None = None,
    radius_mi: float = 50.0,
) -> dict:
    """Compute a trial's Access Outlook tier from eligibility verdicts + registry data.

    Args:
        nct_id: The trial's NCT identifier.
        verdicts: CriterionVerdict dicts, from check_eligibility.
        study: Raw study record dict, from fetch_trial (must contain
            protocolSection.statusModule and .contactsLocationsModule).
        patient_lat: Patient latitude, if known — enables geographic_access.
        patient_lon: Patient longitude, if known.
        radius_mi: Geo radius for the "sites recruiting nearby" count.

    Returns:
        {"outlook": AccessOutlook} on success, or {"error": "<message>"} on
        failure — never raises into the agent loop. Tiers only, per P9 — never
        a percentage.
    """
    try:
        verdict_objs = [CriterionVerdict(**v) for v in verdicts]
        protocol = study.get("protocolSection", study)
        status_module = protocol.get("statusModule", {})
        contacts_locations = protocol.get("contactsLocationsModule", {})

        outlook = compute_access_outlook(
            nct_id=nct_id,
            verdicts=verdict_objs,
            status_module=status_module,
            locations=contacts_locations.get("locations", []),
            central_contacts=contacts_locations.get("centralContacts", []),
            patient_lat=patient_lat,
            patient_lon=patient_lon,
            radius_mi=radius_mi,
        )
        return {"outlook": outlook.model_dump()}
    except Exception as e:  # noqa: BLE001 — tool boundary: must never raise into the agent loop (CLAUDE.md §6)
        return {"error": str(e)}
