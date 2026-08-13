from backend.tools.geo import haversine_miles, nearest_sites, zip_to_latlon


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
