"""Free-text location -> lat/lon via OpenStreetMap Nominatim: request-hash
caching + offline mode, same pattern as _ctgov_client.py (CLAUDE.md §6: cache
every response in fixtures/cache/, --offline forces fixtures-only for demo
insurance).

Not a Strands tool itself — internal helper for geo.py's resolve_location(),
the fallback path for any location text that isn't a recognized US ZIP (non-US
postal codes, "city, country" text, etc.). No API key required; Nominatim's
usage policy just asks for a descriptive User-Agent and modest request volume
— both fine for this app's per-patient, cached lookup volume.
"""

import hashlib
import json
import urllib.parse
import urllib.request
from pathlib import Path

from ._ctgov_client import is_offline

BASE_URL = "https://nominatim.openstreetmap.org/search"
CACHE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "cache"
USER_AGENT = "Pathway-ClinicalTrialMatcher/1.0 (informational research tool, not medical advice)"


def _cache_key(query: str) -> str:
    canonical = "geocode:" + query.strip().lower()
    return hashlib.sha256(canonical.encode()).hexdigest()


def geocode(query: str, offline: bool | None = None) -> dict | None:
    """Resolve free-text `query` (e.g. "Paris, France", "SW1A 1AA, UK") to a
    best-guess lat/lon + city/state via Nominatim.

    Returns None (never raises) when offline with no cached response, or when
    the geocoder has no match — callers should treat that the same as an
    unrecognized ZIP: a graceful "location not recognized", never a crash
    (CLAUDE.md §6).
    """
    if not query:
        return None

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = _cache_key(query)
    cache_file = CACHE_DIR / f"{key}.json"

    if cache_file.exists():
        data = json.loads(cache_file.read_text())
    elif is_offline(offline):
        return None
    else:
        params = {"q": query, "format": "jsonv2", "limit": 1}
        url = BASE_URL + "?" + urllib.parse.urlencode(params)
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=10) as resp:
                data = json.loads(resp.read())
        except Exception:  # noqa: BLE001 — never raise into geo.py's caller (CLAUDE.md §6)
            return None
        cache_file.write_text(json.dumps(data))

    if not data:
        return None
    result = data[0]
    return {
        "lat": float(result["lat"]),
        "lon": float(result["lon"]),
        "city": result.get("name"),
        "state": None,
    }
