"""Phase 1 accept criterion: a cached NSCLC search returns >=3 normalized
summaries fully offline (no network involved).
"""

from backend.tools.search_trials import search_trials


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
