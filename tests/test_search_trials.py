"""Phase 1 accept criterion: a cached NSCLC search returns >=3 normalized
summaries fully offline (no network involved).
"""

from backend.tools.search_trials import _nearest_site, search_trials


def test_offline_nsclc_search_returns_normalized_summaries():
    result = search_trials("non small cell lung cancer", offline=True)

    assert "error" not in result
    trials = result["trials"]
    assert len(trials) >= 3

    for t in trials:
        assert t["nct_id"].startswith("NCT")
        assert t["title"]
        assert t["status"]


def test_offline_search_with_geo_computes_nearest_site():
    result = search_trials(
        "non small cell lung cancer", lat=39.9612, lon=-82.9988, offline=True
    )

    assert "error" not in result
    trials = result["trials"]
    assert len(trials) >= 3
    assert any(t["nearest_site"] is not None for t in trials)


def test_offline_cache_miss_returns_structured_error_not_raise():
    result = search_trials("a condition that was never cached", offline=True)

    assert "error" in result
    assert "trials" not in result


# --- real bug: a trial with a real registry location must still surface it
# when the patient's own location is unknown, rather than showing nothing ---

def test_nearest_site_shown_without_patient_location():
    locations = [
        {
            "facility": "Peking University People's Hospital",
            "status": "RECRUITING",
            "city": "Beijing",
            "state": "Beijing Municipality",
            "country": "China",
            "geoPoint": {"lat": 39.9075, "lon": 116.39723},
        }
    ]
    site = _nearest_site(locations, None, None)

    assert site is not None
    assert site.facility == "Peking University People's Hospital"
    assert site.city == "Beijing"
    assert site.country == "China"
    assert site.distance_mi is None


def test_nearest_site_prefers_recruiting_status_without_patient_location():
    locations = [
        {"facility": "Closed Site", "status": "COMPLETED", "city": "A"},
        {"facility": "Open Site", "status": "RECRUITING", "city": "B"},
    ]
    site = _nearest_site(locations, None, None)

    assert site.facility == "Open Site"


def test_nearest_site_none_when_no_locations_at_all():
    assert _nearest_site([], None, None) is None
    assert _nearest_site([], 39.96, -83.0) is None
