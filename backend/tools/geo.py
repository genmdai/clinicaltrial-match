"""Geo helpers: haversine distance, ZIP->lat/lon lookup, nearest-site sorting.

Plain utility functions (not @tool) — used internally by search_trials.py and
access_outlook.py rather than called directly by the agent.
"""

import csv
import re
from math import asin, cos, radians, sin, sqrt
from pathlib import Path

from . import _geocode_client

EARTH_RADIUS_MI = 3958.8
_US_ZIP_RE = re.compile(r"^\d{5}(-\d{4})?$")

_ZIP_CSV_PATH = Path(__file__).resolve().parents[1] / "data" / "zip_latlon.csv"
_zip_index: dict[str, dict] | None = None


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two lat/lon points, in miles."""
    lat1_r, lon1_r, lat2_r, lon2_r = map(radians, (lat1, lon1, lat2, lon2))
    dlat = lat2_r - lat1_r
    dlon = lon2_r - lon1_r
    a = sin(dlat / 2) ** 2 + cos(lat1_r) * cos(lat2_r) * sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_MI * asin(sqrt(a))


def _load_zip_index() -> dict[str, dict]:
    global _zip_index
    if _zip_index is None:
        index: dict[str, dict] = {}
        with _ZIP_CSV_PATH.open(newline="") as f:
            for row in csv.DictReader(f):
                zip_code = row["zip"].strip().zfill(5)
                index[zip_code] = {
                    "lat": float(row["lat"]),
                    "lon": float(row["lon"]),
                    "city": row.get("city") or None,
                    "state": row.get("state") or None,
                }
        _zip_index = index
    return _zip_index


def zip_to_latlon(zip_code: str) -> dict | None:
    """Look up a US ZIP code's centroid lat/lon (+ city/state if known).

    Returns None (never raises) for a ZIP not in our table — CLAUDE.md §6:
    "the app must transparently fall back... never crash the demo." Callers
    should show a graceful "location not recognized" message on None.
    """
    if not zip_code:
        return None
    index = _load_zip_index()
    return index.get(zip_code.strip().zfill(5))


def resolve_location(text: str, offline: bool | None = None) -> dict | None:
    """Resolve a patient-entered location — a US ZIP or free text like "Paris,
    France" / "SW1A 1AA, UK" — to lat/lon (+ city/state if known).

    Tries the local US ZIP table first (fast, offline, no network) whenever
    `text` looks like a 5-digit ZIP; everything else (and any 5-digit-looking
    text that isn't actually in the table) falls back to a geocoding API call.
    Returns None (never raises) when nothing resolves — same "graceful
    unrecognized location" contract as zip_to_latlon (CLAUDE.md §6).
    """
    if not text:
        return None
    text = text.strip()
    if _US_ZIP_RE.match(text):
        coords = zip_to_latlon(text)
        if coords:
            return coords
    return _geocode_client.geocode(text, offline=offline)


def nearest_recruiting_distance_mi(
    locations: list[dict], lat: float | None, lon: float | None
) -> float | None:
    """Distance in miles to the nearest individually RECRUITING site, or None if
    the patient's location isn't known or no site is both geo-located and
    individually recruiting. Shared by access_outlook.py's geographic_access
    scoring and next_question.py's travel-radius filter so the two can never
    disagree about what "nearest recruiting site" means.
    """
    if lat is None or lon is None:
        return None
    dists = []
    for loc in locations:
        geo_point = loc.get("geoPoint")
        if not geo_point or loc.get("status") != "RECRUITING":
            continue
        dists.append(haversine_miles(lat, lon, geo_point["lat"], geo_point["lon"]))
    return min(dists) if dists else None


def nearest_sites(locations: list[dict], lat: float | None, lon: float | None, n: int = 3) -> list[dict]:
    """Sort trial locations by distance from (lat, lon); attach distance_mi.

    Locations without a geoPoint are skipped when a patient location is given
    (can't be distance-sorted). Without a patient location, the trial's own
    sites are still returned — just unsorted and without a distance_mi — so
    the UI can show real site data instead of nothing.
    """
    if lat is None or lon is None:
        return [{**loc, "distance_mi": None} for loc in locations[:n]]

    with_distance = []
    for loc in locations:
        geo_point = loc.get("geoPoint")
        if not geo_point:
            continue
        dist = haversine_miles(lat, lon, geo_point["lat"], geo_point["lon"])
        with_distance.append({**loc, "distance_mi": round(dist, 1)})
    with_distance.sort(key=lambda loc: loc["distance_mi"])
    return with_distance[:n]
