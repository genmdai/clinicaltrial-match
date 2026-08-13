from backend.tools.geo import haversine_miles


def test_haversine_zero_distance():
    assert haversine_miles(39.9612, -82.9988, 39.9612, -82.9988) == 0.0


def test_haversine_columbus_to_cleveland_roughly_correct():
    # Columbus, OH -> Cleveland, OH is ~125 miles by air.
    dist = haversine_miles(39.9612, -82.9988, 41.4993, -81.6944)
    assert 115 < dist < 135
