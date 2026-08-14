"""Public (non-registry) access links for a trial's facility/sponsor, via
Bright Data's SERP API — e.g. a hospital's own "clinical trials" page, a
sponsor's study page. Explicitly NOT ClinicalTrials.gov data (CLAUDE.md's
registry-only stance is deliberately widened here, per product decision) —
this is supplementary, best-effort, and must never be treated as more
authoritative than the registry (P8 spirit: it's a convenience for making
contact, not a source of eligibility/status truth).

Verified live against a real account 2026-08-13. The endpoint is
`https://api.brightdata.com/request` (NOT `/serp/req` — that path returns an
async job id (`{"response_id": ...}`) even without `?async=1`, which is a
dead end for a lazy per-trial UI lookup). Confirmed synchronous contract:
    POST https://api.brightdata.com/request
    Authorization: Bearer <BRIGHTDATA_API_KEY>
    {"zone": "<BRIGHTDATA_SERP_ZONE>", "url": "<google search url with &brd_json=1>", "format": "raw"}
Response is the parsed-JSON SERP result directly at the top level (despite
`format: "raw"` in the request — that's Bright Data's own naming, not this
module's) — `{"organic": [{"title", "link", "description", "rank", ...}], ...}`.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request

from strands import tool

from . import _env  # noqa: F401 — side-effect import: loads .env

_ENDPOINT = "https://api.brightdata.com/request"


def _extract_results(body: dict) -> list[dict]:
    organic = body.get("organic") or []
    return [
        {"title": r.get("title", ""), "url": r.get("link", ""), "snippet": r.get("description", "")}
        for r in organic
        if r.get("link")
    ]


def _search(query: str, api_key: str, zone: str | None) -> list[dict]:
    google_url = f"https://www.google.com/search?q={urllib.parse.quote(query)}&brd_json=1"
    payload = json.dumps({"zone": zone, "url": google_url, "format": "raw"}).encode()
    req = urllib.request.Request(
        _ENDPOINT, data=payload, method="POST",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return _extract_results(json.loads(resp.read()))


@tool
def public_access_links(facility_name: str | None, sponsor_name: str | None) -> dict:
    """Look up public (non-registry) web results for a trial's facility and/or
    sponsor via Bright Data's SERP API — e.g. a hospital's clinical trials
    intake page, a sponsor's study page.

    Args:
        facility_name: Trial site facility name, if known (from get_contact()
            or a nearest_site entry).
        sponsor_name: Trial sponsor/organization name, if known.

    Returns:
        {"results": [{"query","title","url","snippet","source_tag"}, ...]} on
        success (empty list if neither name is given or nothing was found), or
        {"results": [], "error": "not_configured" | "<message>"} — never
        raises, so the Trial Access view's other sections render regardless
        of Bright Data being unset, down, or rate-limited.
    """
    api_key = os.environ.get("BRIGHTDATA_API_KEY")
    if not api_key:
        return {"results": [], "error": "not_configured"}
    zone = os.environ.get("BRIGHTDATA_SERP_ZONE")

    queries = []
    if facility_name:
        queries.append((f"{facility_name} clinical trials page", "hospital site"))
    if sponsor_name:
        queries.append((f"{sponsor_name} clinical trial patient contact", "sponsor site"))
    if not queries:
        return {"results": []}

    results = []
    try:
        for query, source_tag in queries:
            for hit in _search(query, api_key, zone)[:3]:
                results.append({**hit, "query": query, "source_tag": source_tag})
        return {"results": results}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        return {"results": [], "error": str(e)}
