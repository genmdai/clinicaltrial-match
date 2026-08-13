"""Search ClinicalTrials.gov v2 for candidate trials, normalized to TrialSummary."""

from strands import tool

from ..schemas import NearestSite, TrialSummary
from . import _ctgov_client
from .geo import haversine_miles, nearest_recruiting_distance_mi

MAX_CANDIDATES = 50


def _site_summary(loc: dict, distance_mi: float | None) -> NearestSite:
    return NearestSite(
        facility=loc.get("facility"),
        city=loc.get("city"),
        state=loc.get("state"),
        country=loc.get("country"),
        distance_mi=distance_mi,
    )


def _nearest_site(locations: list[dict], lat: float | None, lon: float | None) -> NearestSite | None:
    """Picks a representative site to show on the trial's summary card.

    With a patient location, this is the actual nearest site (by haversine
    distance). Without one, we still surface a real site from the trial's own
    data — preferring one that's individually RECRUITING — with distance_mi
    left null, rather than showing nothing at all. The trial's location is
    always known here; only the patient's location might not be.
    """
    if not locations:
        return None

    if lat is not None and lon is not None:
        best, best_dist = None, None
        for loc in locations:
            geo_point = loc.get("geoPoint")
            if not geo_point:
                continue
            dist = haversine_miles(lat, lon, geo_point["lat"], geo_point["lon"])
            if best_dist is None or dist < best_dist:
                best_dist, best = dist, loc
        if best is not None:
            return _site_summary(best, round(best_dist, 1))
        # Locations exist but none have a geoPoint to measure from — still show one.
        return _site_summary(locations[0], None)

    recruiting = next((loc for loc in locations if loc.get("status") == "RECRUITING"), None)
    return _site_summary(recruiting or locations[0], None)


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
        nearest_site=_nearest_site(locations, lat, lon),
        has_central_contact=bool(contacts_locations.get("centralContacts")),
        nearest_recruiting_distance_mi=nearest_recruiting_distance_mi(locations, lat, lon),
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
        {"trials": [TrialSummary, ...], "total_count": int} on success — trials
        capped at MAX_CANDIDATES (latency budget for downstream criteria
        parsing), total_count is the true registry-wide match count from
        ClinicalTrials.gov (via countTotal=true) so the UI can show an honest
        "screening N of M" figure instead of implying M were all scored — or
        {"error": "<message>"} on failure — never raises into the agent loop.
    """
    try:
        statuses = "RECRUITING|NOT_YET_RECRUITING" if include_not_yet_recruiting else "RECRUITING"
        params = {
            "query.cond": condition,
            "filter.overallStatus": statuses,
            "pageSize": MAX_CANDIDATES,
            "countTotal": "true",
            "format": "json",
        }
        if intervention:
            params["query.intr"] = intervention
        if lat is not None and lon is not None:
            params["filter.geo"] = f"distance({lat},{lon},{radius_mi}mi)"

        data = _ctgov_client.request_json("", params, offline=offline)
        studies = data.get("studies", [])[:MAX_CANDIDATES]
        trials = [_normalize(s, lat, lon) for s in studies]
        total_count = data.get("totalCount", len(studies))
        return {"trials": [t.model_dump() for t in trials], "total_count": total_count}
    except Exception as e:  # noqa: BLE001 — tool boundary: must never raise into the agent loop (CLAUDE.md §6)
        return {"error": str(e)}
