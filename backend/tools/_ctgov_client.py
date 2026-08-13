"""Shared ClinicalTrials.gov API v2 client: request-hash caching + offline mode.

Not a Strands tool itself — internal helper shared by search_trials.py and
fetch_trial.py, both of which need identical caching/offline behavior
(CLAUDE.md §6: cache every response in fixtures/cache/, --offline forces
fixtures-only for demo insurance).
"""

import hashlib
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

BASE_URL = "https://clinicaltrials.gov/api/v2/studies"
CACHE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "cache"


def _cache_key(path: str, params: dict) -> str:
    canonical = path + "?" + urllib.parse.urlencode(sorted(params.items()))
    return hashlib.sha256(canonical.encode()).hexdigest()


def is_offline(offline: bool | None) -> bool:
    if offline is not None:
        return offline
    return os.environ.get("OFFLINE") == "1"


def request_json(path: str, params: dict, offline: bool | None = None) -> dict:
    """GET `path` (relative to BASE_URL, e.g. "" or "/NCT12345678") with `params`.

    Reads/writes a request-hash-keyed cache in fixtures/cache/. When offline
    (explicit arg or OFFLINE=1 env var), never touches the network — a cache
    miss raises FileNotFoundError so callers can turn it into a structured
    tool error rather than a silent empty result.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = _cache_key(path, params)
    cache_file = CACHE_DIR / f"{key}.json"

    if cache_file.exists():
        return json.loads(cache_file.read_text())

    if is_offline(offline):
        raise FileNotFoundError(f"offline mode: no cached response for {path} {params}")

    url = BASE_URL + path + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=15) as resp:
        data = json.loads(resp.read())

    cache_file.write_text(json.dumps(data))
    return data
