"""Search ClinicalTrials.gov v2 for candidate trials, normalized to TrialSummary."""

from strands import tool

from ..schemas import NearestSite, TrialSummary
from . import _ctgov_client
from .geo import haversine_miles

MAX_CANDIDATES = 5


def _nearest_site(locations: list[dict], lat: float, lon: float) -> NearestSite | None:
    best = None
    best_dist = None
    for loc in locations:
        geo_point = loc.get("geoPoint")
        if not geo_point:
            continue
        dist = haversine_miles(lat, lon, geo_point["lat"], geo_point["lon"])
        if best_dist is None or dist < best_dist:
            best_dist = dist
            best = loc
    if best is None:
        return None
    return NearestSite(
        facility=best.get("facility"),
        city=best.get("city"),
        state=best.get("state"),
        distance_mi=round(best_dist, 1),
    )


def _normalize(study: dict, lat: float | None, lon: float | None) -> TrialSummary:
    ps = study["protocolSection"]
    ident = ps.get("identificationModule", {})
    status = ps.get("statusModule", {})
    design = ps.get("designModule", {})
    arms = ps.get("armsInterventionsModule", {})
    contacts_locations = ps.get("contactsLocationsModule", {})
    locations = contacts_locations.get("locations", [])

    return TrialSummary(
        nct_id=ident["nctId"],
        title=ident.get("briefTitle", ""),
        phase=design.get("phases", []),
        status=status.get("overallStatus", ""),
        interventions=[i["name"] for i in arms.get("interventions", [])],
        site_count=len(locations),
        nearest_site=_nearest_site(locations, lat, lon) if lat is not None and lon is not None else None,
        has_central_contact=bool(contacts_locations.get("centralContacts")),
    )


@tool
def search_trials(
    condition: str,
    lat: float | None = None,
    lon: float | None = None,
    radius_mi: float = 50.0,
    intervention: str | None = None,
    include_not_yet_recruiting: bool = False,
    offline: bool = False,
) -> dict:
    """Search ClinicalTrials.gov for candidate trials matching a condition.

    Args:
        condition: Normalized condition string, e.g. "non small cell lung cancer".
        lat: Patient latitude, if known — enables nearest_site on each result.
        lon: Patient longitude, if known.
        radius_mi: Geo search radius in miles (only used when lat/lon given).
        intervention: Optional drug/intervention keyword to narrow the search.
        include_not_yet_recruiting: If true, also include NOT_YET_RECRUITING
            trials alongside RECRUITING (default is RECRUITING only).
        offline: When true, only use the local fixtures/cache/ — never call the
            live API. Also forced on by the OFFLINE=1 environment variable.

    Returns:
        {"trials": [TrialSummary, ...]} (capped at 5, latency budget for
        downstream criteria parsing) on success, or {"error": "<message>"} on
        failure — never raises into the agent loop.
    """
    try:
        statuses = "RECRUITING|NOT_YET_RECRUITING" if include_not_yet_recruiting else "RECRUITING"
        params = {
            "query.cond": condition,
            "filter.overallStatus": statuses,
            "pageSize": MAX_CANDIDATES,
            "format": "json",
        }
        if intervention:
            params["query.intr"] = intervention
        if lat is not None and lon is not None:
            params["filter.geo"] = f"distance({lat},{lon},{radius_mi}mi)"

        data = _ctgov_client.request_json("", params, offline=offline)
        studies = data.get("studies", [])[:MAX_CANDIDATES]
        trials = [_normalize(s, lat, lon) for s in studies]
        return {"trials": [t.model_dump() for t in trials]}
    except Exception as e:  # noqa: BLE001 — tool boundary: must never raise into the agent loop (CLAUDE.md §6)
        return {"error": str(e)}
