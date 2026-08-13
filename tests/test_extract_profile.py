"""Offline unit tests for extract_profile.py's deterministic pieces (ontology
matching, subject heuristic, reconciliation). The LLM extraction itself is
covered by evals/run_evals.py --stage extraction (needs live Bedrock).
"""

from backend.schemas import PatientProfile, PriorTreatment
from backend.tools.extract_profile import _guess_subject, _match_drug, _reconcile


def test_match_drug_exact_brand():
    entry, was_fuzzy = _match_drug("Keytruda for a year")
    assert entry["generic"] == "pembrolizumab"
    assert was_fuzzy is False


def test_match_drug_fuzzy_misspelling():
    entry, was_fuzzy = _match_drug("keitruda for 6 months")
    assert entry["generic"] == "pembrolizumab"
    assert was_fuzzy is True


def test_match_drug_no_match_for_vague_category():
    entry, _ = _match_drug("did chemo and immunotherapy")
    assert entry is None


def test_guess_subject_relative_keyword():
    assert _guess_subject("my mom has been sick") == "relative"


def test_guess_subject_defaults_to_self():
    assert _guess_subject("I have been feeling unwell") == "self"


def test_reconcile_overrides_drug_identity_from_ontology():
    profile = PatientProfile(
        subject="self",
        prior_treatments=[
            PriorTreatment(raw_mention="keitruda", drug_generic="pembrolizumab", confidence="low")
        ],
    )
    reconciled = _reconcile(profile, "I've been on keitruda")

    pt = reconciled.prior_treatments[0]
    assert pt.drug_brand == "Keytruda"
    assert pt.confidence == "high"
    assert any("fuzzy" in a for a in reconciled.assumptions)
    assert reconciled.treatment_line == 1


def test_reconcile_forces_low_confidence_when_unmatched():
    profile = PatientProfile(
        subject="self",
        prior_treatments=[PriorTreatment(raw_mention="some experimental drug X", confidence="high")],
    )
    reconciled = _reconcile(profile, "I took some experimental drug X")

    assert reconciled.prior_treatments[0].confidence == "low"


def test_reconcile_normalizes_bad_subject_value():
    profile = PatientProfile(subject="patient's mother", prior_treatments=[])
    reconciled = _reconcile(profile, "my mom is sick")

    assert reconciled.subject == "relative"
