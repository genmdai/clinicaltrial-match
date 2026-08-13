from backend.schemas import CriterionVerdict
from backend.tools.access_outlook import (
    _contactability,
    _eligibility_fit,
    _geographic_access,
    _recruitment_momentum,
    _tier_from_bands,
    compute_access_outlook,
)

COLUMBUS = (39.9612, -82.9988)
NEARBY_SITE = {"facility": "Site A", "status": "RECRUITING", "geoPoint": {"lat": 40.2812, "lon": -82.9988}}  # ~22mi
FRESH_STATUS = {
    "overallStatus": "RECRUITING",
    "lastUpdatePostDateStruct": {"date": "2026-07-01"},
    "primaryCompletionDateStruct": {"date": "2027-08"},
}
EMAIL_CONTACT = {"name": "Jane Doe", "role": "CONTACT", "email": "jane@example.com", "contact_source": "central_contact"}


def _v(**kwargs) -> CriterionVerdict:
    defaults = {"rule_id": "r1", "verdict": "PASS", "reason": "ok", "source_quote": "q", "follow_up_question": None}
    defaults.update(kwargs)
    return CriterionVerdict(**defaults)


# --- tier mapping table (BUILD_TEMPLATE: "keep the mapping table in one place,
#     unit tests per row") ---

def test_tier_all_strong_is_high():
    assert _tier_from_bands(["strong", "strong", "strong", "strong"]) == "High"


def test_tier_any_weak_is_low():
    assert _tier_from_bands(["strong", "strong", "strong", "weak"]) == "Low"
    assert _tier_from_bands(["weak", "weak", "weak", "weak"]) == "Low"
    assert _tier_from_bands(["strong", "weak", "fair", "strong"]) == "Low"


def test_tier_fair_no_weak_is_moderate():
    assert _tier_from_bands(["fair", "strong", "strong", "strong"]) == "Moderate"
    assert _tier_from_bands(["fair", "fair", "fair", "fair"]) == "Moderate"


# --- eligibility_fit ---

def test_eligibility_fit_fail_blocks_with_quote():
    component, blocking_rule_id, open_q = _eligibility_fit(
        [_v(rule_id="naive", verdict="FAIL", reason="not naive", source_quote="No prior systemic therapy")]
    )
    assert component.band == "weak"
    assert component.score == 0.0
    assert blocking_rule_id == "naive"
    assert open_q == 0


def test_eligibility_fit_strong_when_all_pass():
    component, blocking_rule_id, open_q = _eligibility_fit([_v(verdict="PASS"), _v(rule_id="r2", verdict="PASS")])
    assert component.band == "strong"
    assert blocking_rule_id is None
    assert open_q == 0


def test_eligibility_fit_fair_with_unknowns_under_three():
    component, blocking_rule_id, open_q = _eligibility_fit(
        [_v(verdict="PASS"), _v(rule_id="r2", verdict="UNKNOWN"), _v(rule_id="r3", verdict="UNKNOWN")]
    )
    assert component.band == "fair"
    assert blocking_rule_id is None
    assert open_q == 2


# --- recruitment_momentum ---

def test_momentum_strong_when_recruiting_and_fresh():
    component = _recruitment_momentum(FRESH_STATUS)
    assert component.band == "strong"


def test_momentum_weak_when_not_recruiting():
    component = _recruitment_momentum({"overallStatus": "TERMINATED"})
    assert component.band == "weak"


def test_momentum_weak_when_completion_imminent():
    component = _recruitment_momentum({
        "overallStatus": "RECRUITING",
        "lastUpdatePostDateStruct": {"date": "2026-07-01"},
        "primaryCompletionDateStruct": {"date": "2026-09"},  # ~1 month away
    })
    assert component.band == "weak"


def test_momentum_weak_when_stale_update():
    component = _recruitment_momentum({
        "overallStatus": "RECRUITING",
        "lastUpdatePostDateStruct": {"date": "2023-01-01"},  # >18 months ago
    })
    assert component.band == "weak"


# --- geographic_access ---

def test_geo_strong_when_recruiting_site_within_50mi():
    component = _geographic_access([NEARBY_SITE], *COLUMBUS, radius_mi=50.0)
    assert component.band == "strong"
    assert "22" in component.evidence[0]


def test_geo_fair_when_no_location_provided():
    component = _geographic_access([NEARBY_SITE], None, None, radius_mi=50.0)
    assert component.band == "fair"


def test_geo_evidence_blames_missing_patient_location_not_the_trial():
    # Real bug: this must never read as "the trial has no location" — the
    # trial's site IS known; only the patient's location is missing.
    component = _geographic_access([NEARBY_SITE], None, None, radius_mi=50.0)
    full_text = " ".join(component.evidence).lower()
    assert "add your zip" in full_text or "we just don't know where you are" in full_text
    assert "site a" in full_text  # the real site name still appears


def test_geo_weak_when_no_recruiting_site_nearby():
    far_site = {"facility": "Site B", "status": "RECRUITING", "geoPoint": {"lat": 5.0, "lon": 5.0}}
    component = _geographic_access([far_site], *COLUMBUS, radius_mi=50.0)
    assert component.band == "weak"


def test_geo_ignores_non_recruiting_sites():
    non_recruiting_nearby = {"facility": "Site C", "status": "COMPLETED", "geoPoint": {"lat": 40.2812, "lon": -82.9988}}
    component = _geographic_access([non_recruiting_nearby], *COLUMBUS, radius_mi=50.0)
    assert component.band == "weak"


# --- contactability ---

def test_contact_strong_with_email():
    assert _contactability(EMAIL_CONTACT).band == "strong"


def test_contact_fair_with_phone_only():
    contact = {"name": "Jane", "phone": "555-1234", "contact_source": "central_contact"}
    assert _contactability(contact).band == "fair"


def test_contact_fair_with_site_contact_only():
    contact = {"name": None, "phone": "555-1234", "contact_source": "site_contact", "facility": "Site A"}
    assert _contactability(contact).band == "fair"


def test_contact_weak_with_none():
    contact = {"name": "Some Sponsor Inc.", "role": None, "phone": None, "email": None, "contact_source": "sponsor_only"}
    assert _contactability(contact).band == "weak"


# --- P9: never a percentage ---

def test_outlook_caveat_present_and_no_component_exposes_score_in_evidence_text():
    outlook = compute_access_outlook(
        nct_id="NCT0", verdicts=[_v()], status_module=FRESH_STATUS,
        locations=[NEARBY_SITE], contact=EMAIL_CONTACT,
        patient_lat=COLUMBUS[0], patient_lon=COLUMBUS[1],
    )
    assert "not a probability" in outlook.caveat
    for component in outlook.components:
        for sentence in component.evidence:
            assert "%" not in sentence


# --- Demo scenarios (a) / (b) / (c) from BUILD_TEMPLATE Phase 3B ---

def test_scenario_a_keytruda_mom_vs_naive_required_is_blocked():
    verdicts = [
        _v(rule_id="naive", verdict="FAIL",
           reason="Patient has received prior systemic treatment (Keytruda), so the "
                   "treatment-naive requirement is not met.",
           source_quote="No prior systemic therapy for advanced or metastatic disease"),
    ]
    outlook = compute_access_outlook(
        nct_id="NCT-NAIVE", verdicts=verdicts, status_module=FRESH_STATUS,
        locations=[NEARBY_SITE], contact=EMAIL_CONTACT,
        patient_lat=COLUMBUS[0], patient_lon=COLUMBUS[1],
    )
    assert outlook.tier == "Blocked"
    # blocking_rule_id links back to the failing verdict, whose source_quote the UI
    # already has (P1) — the component's own evidence echoes the plain-language reason.
    assert outlook.blocking_rule_id == "naive"
    blocking_verdict = next(v for v in verdicts if v.rule_id == outlook.blocking_rule_id)
    assert blocking_verdict.source_quote == "No prior systemic therapy for advanced or metastatic disease"
    blocked_component = next(c for c in outlook.components if c.name == "eligibility_fit")
    assert "treatment-naive requirement is not met" in blocked_component.evidence[0]


def test_scenario_b_two_open_questions_is_moderate():
    verdicts = [
        _v(rule_id="condition", verdict="PASS"),
        _v(rule_id="egfr", verdict="UNKNOWN", follow_up_question="What is the patient's EGFR mutation status?"),
        _v(rule_id="ecog", verdict="UNKNOWN", follow_up_question="What is the patient's ECOG performance status?"),
    ]
    outlook = compute_access_outlook(
        nct_id="NCT-IO", verdicts=verdicts, status_module=FRESH_STATUS,
        locations=[NEARBY_SITE], contact=EMAIL_CONTACT,
        patient_lat=COLUMBUS[0], patient_lon=COLUMBUS[1],
    )
    assert outlook.tier == "Moderate"
    assert outlook.open_questions == 2
    assert outlook.blocking_rule_id is None


def test_scenario_c_answering_open_questions_recomputes_to_high():
    # Same trial as scenario (b), but the two follow-up questions have now been
    # answered and check_eligibility recomputed both to PASS.
    verdicts = [
        _v(rule_id="condition", verdict="PASS"),
        _v(rule_id="egfr", verdict="PASS"),
        _v(rule_id="ecog", verdict="PASS"),
    ]
    outlook = compute_access_outlook(
        nct_id="NCT-IO", verdicts=verdicts, status_module=FRESH_STATUS,
        locations=[NEARBY_SITE], contact=EMAIL_CONTACT,
        patient_lat=COLUMBUS[0], patient_lon=COLUMBUS[1],
    )
    assert outlook.tier == "High"
    assert outlook.open_questions == 0
