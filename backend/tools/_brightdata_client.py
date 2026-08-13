"""Shared Bright Data API client: request-hash caching + offline mode.

Not a Strands tool itself — internal helper used by enrich_trial_access.py,
mirroring the caching/offline conventions in _ctgov_client.py.

One endpoint serves both products; only the zone name and format/data_format
differ. Confirmed 2026-08-13 against the human's own Bright Data dashboard
SERP-zone quickstart snippet (a real, zone-specific example — takes priority
over the generic published docs, which showed a different-looking `format:
"raw"` + `brd_json=1`-on-the-URL variant that we are NOT using):

    POST https://api.brightdata.com/request
    header: Authorization: Bearer <BRIGHTDATA_API_KEY>
    body:   {"zone": <zone>, "url": <target>, "format": "json"|"raw",
             ["data_format"]}

- SERP zone: `url` is a plain Google search URL (just `?q=...`, no extra
  param); `format: "json", data_format: "parsed"` per the dashboard snippet.
  CONFIRMED live against zone "serp_api1": the response is
  {"status_code", "headers", "body"} where "body" is a JSON-ENCODED STRING
  (needs a second json.loads) containing {"general", "input", "navigation",
  "organic", "videos", "knowledge", "overview", "pagination", "related",
  "people_also_ask", ...}. Each `organic[]` entry has "link" (URL), "title",
  "description", "source", "rank"/"global_rank" (no "url"/"snippet" keys —
  `search()` checks those as a fallback only, they never actually fire).
  `_find_organic()` still walks a couple of alternate envelope shapes
  defensively, which costs nothing and is harmless now that the real shape
  is known.
- Web Unlocker zone: `url` is the target page; `format: "raw",
  data_format: "markdown"` converts the scraped page to clean markdown text.
  This one is still only verified against the generic published docs, not a
  live call — re-verify the same way (real dashboard snippet + a live
  request) before relying on it in a demo.
"""

import hashlib
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

REQUEST_URL = "https://api.brightdata.com/request"
CACHE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "cache"
TIMEOUT_S = 30


def _is_offline(offline: bool | None) -> bool:
    if offline is not None:
        return offline
    return os.environ.get("OFFLINE") == "1"


def _cache_path(kind: str, key_material: str) -> Path:
    digest = hashlib.sha256(key_material.encode()).hexdigest()
    return CACHE_DIR / f"brightdata_{kind}_{digest}.json"


def _post(
    zone_env: str,
    target_url: str,
    cache_kind: str,
    offline: bool | None,
    format_: str = "raw",
    data_format: str | None = None,
) -> str:
    """POST to Bright Data's unified request endpoint; returns the raw response body text."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = _cache_path(cache_kind, target_url)

    if cache_file.exists():
        return json.loads(cache_file.read_text())["raw"]

    if _is_offline(offline):
        raise FileNotFoundError(f"offline mode: no cached Bright Data response for {target_url}")

    api_key = os.environ["BRIGHTDATA_API_KEY"]
    zone = os.environ[zone_env]

    body = {"zone": zone, "url": target_url, "format": format_}
    if data_format:
        body["data_format"] = data_format

    req = urllib.request.Request(
        REQUEST_URL,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        raw_body = resp.read().decode()

    cache_file.write_text(json.dumps({"raw": raw_body}))
    return raw_body


def _find_organic(payload: object) -> list[dict]:
    """Dig out the organic-results list regardless of which envelope layer
    Bright Data put it behind — unconfirmed against a live response yet (see
    module docstring), so this tries the plausible shapes rather than
    assuming one.
    """
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return []
    if not isinstance(payload, dict):
        return []
    if isinstance(payload.get("organic"), list):
        return payload["organic"]
    for key in ("body", "parsed", "result", "results"):
        if key in payload:
            found = _find_organic(payload[key])
            if found:
                return found
    return []


def search(query: str, offline: bool | None = None) -> list[dict]:
    """Run one Google search through the Bright Data SERP zone.

    Returns a list of {"title", "url", "snippet"} organic results. Best
    effort: an unexpected/malformed response yields an empty list rather than
    raising, since web search is inherently best-effort enrichment and one
    odd query should never sink the whole enrichment call.
    """
    search_url = "https://www.google.com/search?" + urllib.parse.urlencode({"q": query})
    raw_body = _post("BRIGHTDATA_SERP_ZONE", search_url, "search", offline, format_="json", data_format="parsed")
    try:
        parsed = json.loads(raw_body)
    except json.JSONDecodeError:
        return []

    results = []
    for item in _find_organic(parsed):
        url = item.get("link") or item.get("url")
        if not url:
            continue
        results.append({
            "title": item.get("title"),
            "url": url,
            "snippet": item.get("description") or item.get("snippet"),
        })
    return results


def scrape(url: str, offline: bool | None = None) -> str:
    """Fetch `url` through the Bright Data Web Unlocker zone as clean markdown text."""
    return _post("BRIGHTDATA_UNLOCKER_ZONE", url, "scrape", offline, format_="raw", data_format="markdown")
