"""Offline unit tests for enrich_trial_access.py's deterministic pieces (query
building, domain ranking/dedup, merge logic) plus the tool's offline/error
contract. The Bright Data network calls and LLM page extraction themselves
need live credentials and are out of scope here, matching the project's
existing convention for LLM-backed tools (see test_extract_profile.py /
test_parse_criteria.py — only their deterministic pieces get unit tests).
"""

from backend.schemas import SiteEnrichmentInput, TrialEnrichmentInput
from backend.tools.enrich_trial_access import (
    _build_queries,
    _domain_type,
    _merge,
    _PageExtraction,
    _rank_and_select,
    enrich_trial_access,
)

TRIAL = TrialEnrichmentInput(nct_id="NCT01234567", title="A Study of Widget in NSCLC", sponsor="Acme Pharma")
SITE = SiteEnrichmentInput(facility="Stanford Cancer Center", city="Stanford", state="CA", hospital_domain="stanfordhealthcare.org")


# --- _build_queries ---

def test_build_queries_includes_nct_facility_and_sponsor():
    queries = _build_queries(TRIAL, SITE)
    assert '"NCT01234567" "Stanford Cancer Center"' in queries
    assert '"A Study of Widget in NSCLC" "Stanford Cancer Center"' in queries
    assert '"NCT01234567" "Acme Pharma"' in queries


def test_build_queries_includes_site_search_when_domain_known():
    queries = _build_queries(TRIAL, SITE)
    assert "site:stanfordhealthcare.org NCT01234567" in queries


def test_build_queries_skips_optional_fields_when_absent():
    trial = TrialEnrichmentInput(nct_id="NCT01234567", title="A Study of Widget")
    site = SiteEnrichmentInput(facility="Mercy Hospital")
    queries = _build_queries(trial, site)
    assert not any("site:" in q for q in queries)
    assert not any("Acme" in q for q in queries)
    assert len(queries) == 2


# --- _domain_type ---

def test_domain_type_matches_known_hospital_domain():
    assert _domain_type("https://stanfordhealthcare.org/trials/nct01234567", TRIAL, SITE) == "hospital"


def test_domain_type_matches_hospital_hint_without_known_domain():
    site = SiteEnrichmentInput(facility="Mercy Hospital")
    assert _domain_type("https://www.mercyhospital.org/research", TRIAL, site) == "hospital"


def test_domain_type_matches_sponsor_name_in_host():
    site = SiteEnrichmentInput(facility="Mercy Hospital")
    assert _domain_type("https://www.acmepharma.com/studies/nct01234567", TRIAL, site) == "sponsor"


def test_domain_type_falls_back_to_other():
    site = SiteEnrichmentInput(facility="Mercy Hospital")
    trial = TrialEnrichmentInput(nct_id="NCT01234567", title="A Study")
    assert _domain_type("https://www.randomnewsblog.com/article", trial, site) == "other"


# --- _rank_and_select ---

def test_rank_and_select_excludes_clinicaltrials_gov():
    results = [{"url": "https://clinicaltrials.gov/study/NCT01234567", "title": "CT.gov"}]
    assert _rank_and_select(results, TRIAL, SITE) == []


def test_rank_and_select_dedupes_by_url():
    results = [
        {"url": "https://stanfordhealthcare.org/trials", "title": "A"},
        {"url": "https://stanfordhealthcare.org/trials", "title": "A dup"},
    ]
    selected = _rank_and_select(results, TRIAL, SITE)
    assert len(selected) == 1


def test_rank_and_select_prioritizes_hospital_and_sponsor_over_other():
    results = [
        {"url": "https://www.randomnewsblog.com/article", "title": "third party"},
        {"url": "https://www.acmepharma.com/studies", "title": "sponsor"},
        {"url": "https://stanfordhealthcare.org/trials", "title": "hospital"},
    ]
    selected = _rank_and_select(results, TRIAL, SITE)
    assert [r["url"] for r in selected] == [
        "https://stanfordhealthcare.org/trials",
        "https://www.acmepharma.com/studies",
        "https://www.randomnewsblog.com/article",
    ]


def test_rank_and_select_caps_at_max_pages():
    results = [{"url": f"https://site{i}.org/page", "title": str(i)} for i in range(10)]
    assert len(_rank_and_select(results, TRIAL, SITE, max_pages=3)) == 3


# --- _merge ---

def _meta(url="https://stanfordhealthcare.org/trials", title="Trials", domain_type="hospital"):
    return {"url": url, "title": title, "domain_type": domain_type}


def test_merge_skips_irrelevant_pages():
    ext = _PageExtraction(is_relevant=False, trial_office_phone="555-1234")
    result = _merge([(_meta(), ext)], TRIAL, SITE)
    assert result.trial_office.phone is None
    assert result.sources == []


def test_merge_fills_fields_and_records_source():
    ext = _PageExtraction(
        is_relevant=True,
        trial_office_name="Clinical Trials Office",
        trial_office_phone="555-1234",
        trial_office_email="trials@stanford.edu",
        referral_instructions="Ask your oncologist for a referral.",
        physician_referral_required=True,
        documents_mentioned=["pathology report", "imaging"],
    )
    result = _merge([(_meta(), ext)], TRIAL, SITE)

    assert result.trial_id == "NCT01234567"
    assert result.site == "Stanford Cancer Center"
    assert result.trial_office.name == "Clinical Trials Office"
    assert result.trial_office.phone == "555-1234"
    assert result.trial_office.email == "trials@stanford.edu"
    assert result.referral.instructions == "Ask your oncologist for a referral."
    assert result.referral.physician_referral_required is True
    assert result.documents_mentioned == ["pathology report", "imaging"]
    assert len(result.sources) == 1
    assert result.sources[0].url == "https://stanfordhealthcare.org/trials"
    assert result.sources[0].domain_type == "hospital"


def test_merge_first_page_wins_for_singular_fields():
    first = _PageExtraction(is_relevant=True, trial_office_phone="555-1111")
    second = _PageExtraction(is_relevant=True, trial_office_phone="555-2222")
    result = _merge([(_meta(url="https://a.org"), first), (_meta(url="https://b.org"), second)], TRIAL, SITE)
    assert result.trial_office.phone == "555-1111"
    assert len(result.sources) == 1


def test_merge_unions_list_fields_across_pages_without_duplicates():
    first = _PageExtraction(is_relevant=True, documents_mentioned=["pathology report"])
    second = _PageExtraction(is_relevant=True, documents_mentioned=["pathology report", "imaging"])
    result = _merge([(_meta(url="https://a.org"), first), (_meta(url="https://b.org"), second)], TRIAL, SITE)
    assert result.documents_mentioned == ["pathology report", "imaging"]
    assert len(result.sources) == 2


def test_merge_omits_source_when_page_contributes_nothing():
    ext = _PageExtraction(is_relevant=True)  # relevant but nothing extracted
    result = _merge([(_meta(), ext)], TRIAL, SITE)
    assert result.sources == []


# --- enrich_trial_access tool boundary ---

def test_enrich_trial_access_invalid_input_returns_structured_error():
    result = enrich_trial_access(trial={"title": "missing nct_id"}, site={"facility": "Mercy Hospital"})
    assert "error" in result
    assert "enrichment" not in result


def test_enrich_trial_access_offline_with_no_cache_returns_empty_enrichment_not_error():
    result = enrich_trial_access(
        trial={"nct_id": "NCT01234567", "title": "A Study", "sponsor": "Acme Pharma"},
        site={"facility": "Stanford Cancer Center", "hospital_domain": "stanfordhealthcare.org"},
        offline=True,
    )
    assert "error" not in result
    enrichment = result["enrichment"]
    assert enrichment["trial_id"] == "NCT01234567"
    assert enrichment["sources"] == []
    assert enrichment["trial_office"]["phone"] is None


def test_enrich_trial_access_ignores_extra_non_schema_keys_without_raising():
    result = enrich_trial_access(
        trial={"nct_id": "NCT01234567", "title": "A Study", "patient_condition": "should be dropped"},
        site={"facility": "Mercy Hospital", "patient_age": 68},
        offline=True,
    )
    assert "error" not in result
