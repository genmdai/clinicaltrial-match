from backend.tools.fetch_trial import fetch_trial


def test_offline_fetch_returns_cached_study():
    result = fetch_trial("NCT06917079", offline=True)

    assert "error" not in result
    study = result["study"]
    assert study["protocolSection"]["identificationModule"]["nctId"] == "NCT06917079"


def test_offline_fetch_unknown_nct_returns_structured_error():
    result = fetch_trial("NCT00000000", offline=True)

    assert "error" in result
    assert "study" not in result
