from backend.schemas import EligibilityRule, PatientProfile, PriorTreatment
from backend.tools.check_eligibility import evaluate


def _rule(**kwargs) -> EligibilityRule:
    defaults = {
        "rule_id": "r1",
        "kind": "inclusion",
        "field": "age",
        "operator": "gte",
        "value": 18,
        "source_quote": "Age 18 years or older",
        "parse_confidence": "high",
    }
    defaults.update(kwargs)
    return EligibilityRule(**defaults)


def _profile(**kwargs) -> PatientProfile:
    defaults = {"subject": "self"}
    defaults.update(kwargs)
    return PatientProfile(**defaults)


# --- age ---

def test_age_gte_pass():
    verdicts, rollup = evaluate([_rule(field="age", operator="gte", value=18)], _profile(age=68))
    assert verdicts[0].verdict == "PASS"
    assert rollup == "Looks eligible (confirm with team)"


def test_age_lte_fail():
    verdicts, _ = evaluate([_rule(field="age", operator="lte", value=65)], _profile(age=68))
    assert verdicts[0].verdict == "FAIL"


def test_age_unknown_when_missing():
    verdicts, _ = evaluate([_rule(field="age", operator="gte", value=18)], _profile(age=None))
    assert verdicts[0].verdict == "UNKNOWN"
    assert verdicts[0].follow_up_question


# --- ecog ---

def test_ecog_lte_pass_and_fail():
    ok, _ = evaluate([_rule(field="ecog", operator="lte", value=1)], _profile(ecog=1))
    assert ok[0].verdict == "PASS"
    bad, _ = evaluate([_rule(field="ecog", operator="lte", value=1)], _profile(ecog=2))
    assert bad[0].verdict == "FAIL"


def test_ecog_unknown_when_missing():
    verdicts, _ = evaluate([_rule(field="ecog", operator="lte", value=1)], _profile())
    assert verdicts[0].verdict == "UNKNOWN"


# --- condition ---

def test_condition_contains_pass():
    verdicts, _ = evaluate(
        [_rule(field="condition", operator="contains", value="non-small cell lung cancer")],
        _profile(condition="non-small cell lung cancer"),
    )
    assert verdicts[0].verdict == "PASS"


def test_condition_mismatch_fails():
    verdicts, _ = evaluate(
        [_rule(field="condition", operator="contains", value="breast cancer")],
        _profile(condition="non-small cell lung cancer"),
    )
    assert verdicts[0].verdict == "FAIL"


def test_condition_unknown_when_missing():
    verdicts, _ = evaluate([_rule(field="condition", operator="contains", value="lung cancer")], _profile())
    assert verdicts[0].verdict == "UNKNOWN"


# --- biomarker ---

def test_biomarker_unknown_when_absent():
    verdicts, _ = evaluate([_rule(field="biomarker", operator="must_have", value="EGFR")], _profile(biomarkers=[]))
    assert verdicts[0].verdict == "UNKNOWN"
    assert "EGFR" in verdicts[0].follow_up_question


def test_biomarker_explicit_unknown_stays_unknown():
    verdicts, _ = evaluate(
        [_rule(field="biomarker", operator="must_have", value="EGFR")],
        _profile(biomarkers=["EGFR unknown"]),
    )
    assert verdicts[0].verdict == "UNKNOWN"


def test_biomarker_positive_passes_must_have():
    verdicts, _ = evaluate(
        [_rule(field="biomarker", operator="must_have", value="EGFR")],
        _profile(biomarkers=["EGFR positive"]),
    )
    assert verdicts[0].verdict == "PASS"


def test_biomarker_negative_fails_must_have():
    verdicts, _ = evaluate(
        [_rule(field="biomarker", operator="must_have", value="EGFR")],
        _profile(biomarkers=["EGFR negative"]),
    )
    assert verdicts[0].verdict == "FAIL"


# --- treatment_naive: THE demo beat ---

def test_treatment_naive_fails_with_prior_anti_pd1():
    profile = _profile(
        prior_treatments=[
            PriorTreatment(raw_mention="Keytruda", drug_brand="Keytruda", drug_generic="pembrolizumab",
                           drug_class="anti-PD-1 checkpoint inhibitor", outcome="progression", inferred=True,
                           confidence="high")
        ],
        treatment_line=1,
    )
    verdicts, rollup = evaluate(
        [_rule(field="treatment_naive", operator="must_have", value="true",
               source_quote="No prior systemic therapy for advanced or metastatic disease")],
        profile,
    )
    assert verdicts[0].verdict == "FAIL"
    assert verdicts[0].source_quote == "No prior systemic therapy for advanced or metastatic disease"
    assert rollup == "Likely not eligible"


def test_treatment_naive_passes_when_confirmed_naive():
    verdicts, _ = evaluate(
        [_rule(field="treatment_naive", operator="must_have", value="true")],
        _profile(prior_treatments=[], treatment_line=0),
    )
    assert verdicts[0].verdict == "PASS"


def test_treatment_naive_unknown_when_history_unrecorded():
    verdicts, _ = evaluate(
        [_rule(field="treatment_naive", operator="must_have", value="true")],
        _profile(prior_treatments=[], treatment_line=None),
    )
    assert verdicts[0].verdict == "UNKNOWN"


# --- prior_therapy_class not_had ---

def test_not_had_anti_pd1_fails_with_keytruda_history():
    profile = _profile(
        prior_treatments=[
            PriorTreatment(raw_mention="Keytruda", drug_brand="Keytruda", drug_generic="pembrolizumab",
                           drug_class="anti-PD-1 checkpoint inhibitor", outcome="progression", inferred=True,
                           confidence="high")
        ],
    )
    verdicts, _ = evaluate(
        [_rule(field="prior_therapy_class", operator="not_had", value="anti-PD-1",
               source_quote="Prior treatment with any anti-PD-1 agent")],
        profile,
    )
    assert verdicts[0].verdict == "FAIL"
    assert verdicts[0].source_quote == "Prior treatment with any anti-PD-1 agent"


def test_not_had_passes_when_prior_treatment_is_different_class():
    profile = _profile(
        prior_treatments=[
            PriorTreatment(raw_mention="carboplatin", drug_generic="carboplatin",
                           drug_class="platinum chemotherapy", confidence="high")
        ],
    )
    verdicts, _ = evaluate(
        [_rule(field="prior_therapy_class", operator="not_had", value="anti-PD-1")],
        profile,
    )
    assert verdicts[0].verdict == "PASS"


def test_not_had_unknown_when_history_unrecorded():
    verdicts, _ = evaluate(
        [_rule(field="prior_therapy_class", operator="not_had", value="anti-PD-1")],
        _profile(prior_treatments=[], treatment_line=None),
    )
    assert verdicts[0].verdict == "UNKNOWN"


# --- P2/P3: low confidence and unmapped fields never produce a guessed FAIL/PASS ---

def test_low_parse_confidence_caps_to_unknown_even_if_evaluable():
    verdicts, _ = evaluate(
        [_rule(field="age", operator="gte", value=18, parse_confidence="low")],
        _profile(age=68),  # would otherwise PASS
    )
    assert verdicts[0].verdict == "UNKNOWN"


def test_unmapped_field_other_is_always_unknown():
    verdicts, _ = evaluate([_rule(field="other", operator="contains", value="brain metastases")], _profile(age=68))
    assert verdicts[0].verdict == "UNKNOWN"
    assert verdicts[0].follow_up_question


# --- rollup ---

def test_rollup_possibly_eligible_counts_open_questions():
    _, rollup = evaluate(
        [
            _rule(field="age", operator="gte", value=18),
            _rule(rule_id="r2", field="biomarker", operator="must_have", value="EGFR"),
            _rule(rule_id="r3", field="ecog", operator="lte", value=1),
        ],
        _profile(age=68, biomarkers=[], ecog=None),
    )
    assert rollup == "Possibly eligible — 2 open questions"


def test_rollup_fail_wins_over_unknown():
    _, rollup = evaluate(
        [
            _rule(field="age", operator="gte", value=90),  # FAIL
            _rule(rule_id="r2", field="biomarker", operator="must_have", value="EGFR"),  # UNKNOWN
        ],
        _profile(age=68, biomarkers=[]),
    )
    assert rollup == "Likely not eligible"
