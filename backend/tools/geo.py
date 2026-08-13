"""Geo helpers. ZIP->lat/lon lookup and full site-distance sorting land in Phase 4;
haversine_miles is pulled in early since Phase 1's TrialSummary.nearest_site needs it.
"""

from math import asin, cos, radians, sin, sqrt

EARTH_RADIUS_MI = 3958.8


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two lat/lon points, in miles."""
    lat1_r, lon1_r, lat2_r, lon2_r = map(radians, (lat1, lon1, lat2, lon2))
    dlat = lat2_r - lat1_r
    dlon = lon2_r - lon1_r
    a = sin(dlat / 2) ** 2 + cos(lat1_r) * cos(lat2_r) * sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_MI * asin(sqrt(a))
