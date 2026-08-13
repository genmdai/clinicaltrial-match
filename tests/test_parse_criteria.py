import asyncio

from backend.schemas import EligibilityRule
from backend.tools.parse_criteria import (
    _cache_path,
    _write_cache,
    parse_criteria_stream,
    split_criteria,
)


def test_split_criteria_standard_order():
    text = (
        "Inclusion Criteria:\n\n* Age >= 18\n* NSCLC\n\n"
        "Exclusion Criteria:\n\n* Untreated brain metastases"
    )
    chunks = split_criteria(text)
    assert "Age >= 18" in chunks["inclusion"]
    assert "NSCLC" in chunks["inclusion"]
    assert "Untreated brain metastases" in chunks["exclusion"]
    assert "Exclusion Criteria" not in chunks["inclusion"]


def test_split_criteria_reversed_order():
    text = "Exclusion Criteria:\n\n* Prior chemo\n\nInclusion Criteria:\n\n* Age >= 18"
    chunks = split_criteria(text)
    assert "Prior chemo" in chunks["exclusion"]
    assert "Age >= 18" in chunks["inclusion"]
    assert "Inclusion Criteria" not in chunks["exclusion"]


def test_split_criteria_inclusion_only():
    chunks = split_criteria("Inclusion Criteria:\n\n* Age >= 18")
    assert chunks == {"inclusion": "* Age >= 18"}


def test_split_criteria_no_headers_falls_back_to_unspecified():
    chunks = split_criteria("Patients must be over 18 and have no prior chemo.")
    assert list(chunks.keys()) == ["unspecified"]
    assert "over 18" in chunks["unspecified"]


def test_split_criteria_case_insensitive_headers():
    text = "inclusion criteria:\n* Age >= 18\n\nEXCLUSION CRITERIA:\n* Prior chemo"
    chunks = split_criteria(text)
    assert "Age >= 18" in chunks["inclusion"]
    assert "Prior chemo" in chunks["exclusion"]


def _fake_rule(rule_id: str) -> EligibilityRule:
    return EligibilityRule(
        rule_id=rule_id, kind="inclusion", field="age", operator="gte", value=18,
        source_quote="Age 18 years or older", parse_confidence="high",
    )


def test_parse_criteria_stream_yields_from_cache_without_llm_call():
    # Self-contained offline test: seed the cache directly rather than depending
    # on pre-existing cache state from manual/live testing elsewhere.
    nct_ids = ["TEST-STREAM-A", "TEST-STREAM-B"]
    try:
        for nct_id in nct_ids:
            _write_cache(nct_id, [_fake_rule(f"{nct_id}-0")])

        async def run():
            trials = [{"nct_id": nct_id, "criteria_text": "unused, cached"} for nct_id in nct_ids]
            return {nct_id: result async for nct_id, result in parse_criteria_stream(trials)}

        results = asyncio.run(run())
        assert set(results.keys()) == set(nct_ids)
        assert all("error" not in r for r in results.values())
    finally:
        for nct_id in nct_ids:
            _cache_path(nct_id).unlink(missing_ok=True)
