"""Fetch a single full ClinicalTrials.gov study record by NCT ID, plus the
contact fallback chain (CLAUDE.md Phase 4): centralContacts -> overallOfficials
-> nearest location.contacts -> sponsor name with "call the site" guidance.
`contact_source` is always returned so the UI can label the contact honestly
rather than implying a level of directness that isn't there.
"""

from strands import tool

from . import _ctgov_client
from .geo import nearest_sites


@tool
def fetch_trial(nct_id: str, offline: bool = False) -> dict:
    """Fetch the full study record for a given NCT ID from ClinicalTrials.gov.

    Args:
        nct_id: The trial's NCT identifier, e.g. "NCT06917079".
        offline: When true, only use the local fixtures/cache/ — never call the
            live API. Also forced on by the OFFLINE=1 environment variable.

    Returns:
        {"study": <raw protocolSection/derivedSection JSON>} on success, or
        {"error": "<message>"} on failure (network error, unknown NCT ID,
        offline cache miss) — never raises into the agent loop.
    """
    try:
        data = _ctgov_client.request_json(f"/{nct_id}", {"format": "json"}, offline=offline)
        return {"study": data}
    except Exception as e:  # noqa: BLE001 — tool boundary: must never raise into the agent loop (CLAUDE.md §6)
        return {"error": str(e)}


def _contact_from_central(central_contacts: list[dict]) -> dict | None:
    for c in central_contacts:
        if c.get("email") or c.get("phone"):
            return {
                "name": c.get("name"), "role": c.get("role"),
                "phone": c.get("phone"), "email": c.get("email"),
                "contact_source": "central_contact",
            }
    return None


def _contact_from_official(overall_officials: list[dict]) -> dict | None:
    for o in overall_officials:
        if o.get("name"):
            return {
                "name": o.get("name"), "role": o.get("role"),
                "phone": o.get("phone"), "email": o.get("email"),
                "contact_source": "overall_official",
                "affiliation": o.get("affiliation"),
            }
    return None


def _contact_from_site(locations: list[dict], patient_lat: float | None, patient_lon: float | None) -> dict | None:
    if not locations:
        return None
    nearest = nearest_sites(locations, patient_lat, patient_lon, n=1)[0] if patient_lat is not None and patient_lon is not None else locations[0]
    for c in nearest.get("contacts", []):
        if c.get("email") or c.get("phone") or c.get("name"):
            return {
                "name": c.get("name"), "role": c.get("role"),
                "phone": c.get("phone"), "email": c.get("email"),
                "contact_source": "site_contact",
                "facility": nearest.get("facility"),
            }
    return None


def get_contact(study: dict, patient_lat: float | None = None, patient_lon: float | None = None) -> dict:
    """Resolve the best available contact for a trial via the fallback chain.

    Args:
        study: Raw study record dict, from fetch_trial (or its "study" value).
        patient_lat / patient_lon: Used to pick the nearest site when falling
            back to a site-level contact; optional.

    Returns:
        {"name", "role", "phone", "email", "contact_source", ...} — always
        includes "contact_source" so the UI can label how direct this contact
        actually is, per CLAUDE.md Phase 4. Never raises; the final fallback
        (sponsor name + "call the site" guidance) always succeeds.
    """
    protocol = study.get("protocolSection", study)
    contacts_locations = protocol.get("contactsLocationsModule", {})
    central_contacts = contacts_locations.get("centralContacts", [])
    overall_officials = contacts_locations.get("overallOfficials", [])
    locations = contacts_locations.get("locations", [])

    for resolver in (
        lambda: _contact_from_central(central_contacts),
        lambda: _contact_from_official(overall_officials),
        lambda: _contact_from_site(locations, patient_lat, patient_lon),
    ):
        contact = resolver()
        if contact:
            return contact

    sponsor_name = protocol.get("identificationModule", {}).get("organization", {}).get("fullName")
    return {
        "name": sponsor_name, "role": None, "phone": None, "email": None,
        "contact_source": "sponsor_only",
        "guidance": "No direct contact is listed for this trial — call the site directly and reference this NCT ID.",
    }
