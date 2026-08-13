"""Fetch a single full ClinicalTrials.gov study record by NCT ID."""

from strands import tool

from . import _ctgov_client


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
