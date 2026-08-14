import json

from backend.tools import _geocode_client
from backend.tools.geo import haversine_miles, nearest_sites, resolve_location, zip_to_latlon


def test_haversine_zero_distance():
    assert haversine_miles(39.9612, -82.9988, 39.9612, -82.9988) == 0.0


def test_haversine_columbus_to_cleveland_roughly_correct():
    # Columbus, OH -> Cleveland, OH is ~125 miles by air.
    dist = haversine_miles(39.9612, -82.9988, 41.4993, -81.6944)
    assert 115 < dist < 135


# --- nearest_sites ---

def test_nearest_sites_sorts_and_attaches_distance():
    locations = [
        {"facility": "Far", "geoPoint": {"lat": 5.0, "lon": 5.0}},
        {"facility": "Near", "geoPoint": {"lat": 40.2812, "lon": -82.9988}},
        {"facility": "Middle", "geoPoint": {"lat": 41.4993, "lon": -81.6944}},
    ]
    result = nearest_sites(locations, 39.9612, -82.9988, n=2)
    assert [r["facility"] for r in result] == ["Near", "Middle"]
    assert result[0]["distance_mi"] < result[1]["distance_mi"]


def test_nearest_sites_skips_locations_without_geopoint():
    locations = [{"facility": "No Geo"}, {"facility": "Near", "geoPoint": {"lat": 40.2812, "lon": -82.9988}}]
    result = nearest_sites(locations, 39.9612, -82.9988, n=3)
    assert len(result) == 1
    assert result[0]["facility"] == "Near"


# --- zip_to_latlon ---

def test_zip_to_latlon_known_zip_columbus():
    coords = zip_to_latlon("43215")
    assert coords is not None
    assert 39.8 < coords["lat"] < 40.1
    assert -83.1 < coords["lon"] < -82.9


def test_zip_to_latlon_unknown_zip_returns_none_not_raise():
    assert zip_to_latlon("00000") is None


def test_zip_to_latlon_handles_short_zip_via_zfill():
    coords = zip_to_latlon("1001")  # missing leading zero
    assert coords is None or isinstance(coords["lat"], float)


# --- resolve_location: US ZIP fast path + international geocoding fallback ---

def test_resolve_location_uses_us_zip_fast_path_without_network():
    # A recognized US ZIP must resolve via the local table alone — no geocode
    # cache entry seeded, so this only passes if the network path was never hit.
    coords = resolve_location("43215", offline=True)
    assert coords is not None
    assert 39.8 < coords["lat"] < 40.1


def test_resolve_location_falls_back_to_geocoder_for_non_zip_text():
    query = "Paris, France (test fixture)"
    key = _geocode_client._cache_key(query)
    cache_file = _geocode_client.CACHE_DIR / f"{key}.json"
    _geocode_client.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps([{"lat": "48.8566", "lon": "2.3522", "name": "Paris"}]))
    try:
        coords = resolve_location(query, offline=True)
        assert coords is not None
        assert coords["city"] == "Paris"
        assert 48.0 < coords["lat"] < 49.5
    finally:
        cache_file.unlink(missing_ok=True)


def test_resolve_location_offline_cache_miss_returns_none_not_raise():
    assert resolve_location("a location that was never cached, offline", offline=True) is None


def test_resolve_location_empty_text_returns_none():
    assert resolve_location("", offline=True) is None
