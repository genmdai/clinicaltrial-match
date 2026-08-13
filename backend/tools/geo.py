"""Geo helpers: haversine distance, ZIP->lat/lon lookup, nearest-site sorting.

Plain utility functions (not @tool) — used internally by search_trials.py and
access_outlook.py rather than called directly by the agent.
"""

import csv
from math import asin, cos, radians, sin, sqrt
from pathlib import Path

EARTH_RADIUS_MI = 3958.8

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


def nearest_sites(locations: list[dict], lat: float, lon: float, n: int = 3) -> list[dict]:
    """Sort trial locations by distance from (lat, lon); attach distance_mi.

    Locations without a geoPoint are skipped (can't be distance-sorted).
    """
    with_distance = []
    for loc in locations:
        geo_point = loc.get("geoPoint")
        if not geo_point:
            continue
        dist = haversine_miles(lat, lon, geo_point["lat"], geo_point["lon"])
        with_distance.append({**loc, "distance_mi": round(dist, 1)})
    with_distance.sort(key=lambda loc: loc["distance_mi"])
    return with_distance[:n]
