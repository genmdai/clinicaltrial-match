from backend.schemas import EligibilityRule, PatientProfile
from backend.tools.check_eligibility import evaluate
from backend.tools.next_question import (
    _apply_single_answer,
    cluster_key,
    find_clusters,
    fold_ledger,
    is_open,
    pick_next_question,
)

BASE_PROFILE = PatientProfile(subject="self")


def _rule(nct_id, idx, **kwargs):
    defaults = {
        "kind": "inclusion",
        "field": "other",
        "operator": "contains",
        "value": "x",
        "source_quote": "x",
        "parse_confidence": "high",
    }
    defaults.update(kwargs)
    return EligibilityRule(rule_id=f"{nct_id}-{idx}", **defaults)


def _open_trial(nct_id, rules, profile=BASE_PROFILE, nearest_recruiting_distance_mi=None):
    verdicts, _ = evaluate(rules, profile)
    return {
        "nct_id": nct_id,
        "rules": rules,
        "verdicts": verdicts,
        "nearest_recruiting_distance_mi": nearest_recruiting_distance_mi,
    }


def _bundle(nct_id, rules, nearest_recruiting_distance_mi=None):
    return {
        "nct_id": nct_id,
        "rules": rules,
        "status_module": {"overallStatus": "RECRUITING"},
        "locations": [],
        "contact": {"name": "Sponsor"},
        "nearest_recruiting_distance_mi": nearest_recruiting_distance_mi,
    }


# --- clustering ---

def test_age_clusters_by_field_not_value_across_differing_cutoffs():
    rule_a = _rule("A", 0, field="age", operator="gte", value=18, source_quote="18 years or older")
    rule_b = _rule("B", 0, field="age", operator="gte", value=65, source_quote="65 years or older")
    trials = [_open_trial("A", [rule_a]), _open_trial("B", [rule_b])]

    clusters = find_clusters(trials)

    assert set(clusters.keys()) == {"age"}
    assert {e[0] for e in clusters["age"]} == {"A", "B"}


def test_biomarker_clusters_by_marker_name_despite_different_wording():
    rule_a = _rule("A", 0, field="biomarker", operator="must_have", value="EGFR exon 20 insertion", source_quote="EGFR exon 20 insertion")
    rule_b = _rule("B", 0, field="biomarker", operator="must_have", value="EGFR positive", source_quote="EGFR positive")
    trials = [_open_trial("A", [rule_a]), _open_trial("B", [rule_b])]

    clusters = find_clusters(trials)

    assert list(clusters.keys()) == ["biomarker:EGFR"]
    assert {e[0] for e in clusters["biomarker:EGFR"]} == {"A", "B"}


def test_field_other_never_clusters_even_when_two_trials_share_it():
    rule_a = _rule("A", 0, field="other", operator="contains", value="informed consent", source_quote="informed consent", parse_confidence="low")
    rule_b = _rule("B", 0, field="other", operator="contains", value="informed consent", source_quote="informed consent", parse_confidence="low")
    trials = [_open_trial("A", [rule_a]), _open_trial("B", [rule_b])]

    assert find_clusters(trials) == {}
    assert pick_next_question(trials, asked_cluster_keys=set()) is None


def test_other_with_topic_clusters_dynamically_across_trials():
    # No hardcoded field for "brain metastases" — it clusters purely because
    # parse_criteria.py extracted a matching topic on both trials' rules.
    rule_a = _rule("A", 0, field="other", operator="not_had", value="brain metastases", kind="exclusion",
                   topic="brain_metastases", topic_question="Does the patient have brain metastases?",
                   source_quote="No untreated brain metastases")
    rule_b = _rule("B", 0, field="other", operator="not_had", value="CNS metastases", kind="exclusion",
                   topic="brain_metastases", topic_question="Does the patient have brain metastases?",
                   source_quote="Active CNS metastases excludes patient")
    trials = [_open_trial("A", [rule_a]), _open_trial("B", [rule_b])]

    question = pick_next_question(trials, asked_cluster_keys=set())

    assert question["cluster_key"] == "other:brain_metastases"
    assert question["answer_mode"] == "yes_no_notsure"
    assert question["decides_count"] == 2
    assert question["label"] == "Does the patient have brain metastases?"


def test_other_topic_answer_resolves_via_other_facts():
    rule = _rule("A", 0, field="other", operator="not_had", value="brain metastases", kind="exclusion",
                 topic="brain_metastases", topic_question="Does the patient have brain metastases?")
    updated = _apply_single_answer(BASE_PROFILE, rule, "No, none")
    verdicts, _ = evaluate([rule], updated)
    assert verdicts[0].verdict == "PASS"
    assert updated.other_facts == {"brain_metastases": "no"}


def test_low_confidence_rule_of_a_clusterable_field_still_excluded():
    # A field that WOULD be clusterable, but the parser wasn't confident about
    # it — check_eligibility caps it at UNKNOWN with the generic follow-up, so
    # it must not enter the ranked mechanism either.
    rule = _rule("A", 0, field="age", operator="gte", value=18, source_quote="18 years", parse_confidence="low")
    verdict = evaluate([rule], BASE_PROFILE)[0][0]
    assert cluster_key(rule, verdict) is None


# --- treatment_naive / prior_therapy_class asymmetry ---

def test_prior_therapy_class_cluster_is_no_or_specify_mode():
    rule_a = _rule("A", 0, field="prior_therapy_class", operator="not_had", value="anti-PD-1", source_quote="no prior anti-PD-1 therapy")
    rule_b = _rule("B", 0, field="prior_therapy_class", operator="not_had", value="anti-PD-1", source_quote="no prior anti-PD-1 therapy")
    trials = [_open_trial("A", [rule_a]), _open_trial("B", [rule_b])]

    question = pick_next_question(trials, asked_cluster_keys=set())

    assert question["cluster_key"] == "prior_therapy_class"
    assert question["answer_mode"] == "no_or_specify"
    assert question["decides_count"] == 2


def test_yes_answer_does_not_resolve_prior_therapy_class():
    rule = _rule("A", 0, field="prior_therapy_class", operator="not_had", value="anti-PD-1", source_quote="no prior anti-PD-1 therapy")
    result = _apply_single_answer(BASE_PROFILE, rule, "Yes, confirmed")
    assert result == BASE_PROFILE  # no-op: a bare "yes" doesn't say which drug


def test_no_answer_resolves_prior_therapy_class_to_pass():
    rule = _rule("A", 0, field="prior_therapy_class", operator="not_had", value="anti-PD-1", source_quote="no prior anti-PD-1 therapy")
    updated = _apply_single_answer(BASE_PROFILE, rule, "No, never treated")
    verdicts, _ = evaluate([rule], updated)
    assert verdicts[0].verdict == "PASS"


# --- stop condition ---

def test_stop_condition_when_max_decides_count_below_two():
    # Each trial's UNKNOWN is on a different field — nothing shared by >=2.
    rule_a = _rule("A", 0, field="age", operator="gte", value=18, source_quote="18 years")
    rule_b = _rule("B", 0, field="biomarker", operator="must_have", value="PD-L1", source_quote="PD-L1")
    trials = [_open_trial("A", [rule_a]), _open_trial("B", [rule_b])]

    assert pick_next_question(trials, asked_cluster_keys=set()) is None


# --- fold_ledger: retraction-replay correctness ---

def test_retracting_an_answer_matches_refolding_without_it():
    age_rule = _rule("A", 0, field="age", operator="gte", value=18, source_quote="18 years")
    biomarker_rule = _rule("B", 0, field="biomarker", operator="must_have", value="EGFR positive", source_quote="EGFR positive")
    far_rule = _rule("C", 0, field="age", operator="gte", value=18, source_quote="18 years")

    trials = [
        _bundle("A", [age_rule]),
        _bundle("B", [biomarker_rule]),
        _bundle("C", [far_rule], nearest_recruiting_distance_mi=200.0),
    ]

    answer_age = {"cluster_key": "age", "field": "age", "rule_id": "A-0", "text": "45", "ledger_label": "Age"}
    answer_biomarker = {
        "cluster_key": "biomarker:EGFR", "field": "biomarker", "rule_id": "B-0",
        "text": "negative", "ledger_label": "EGFR status",
    }
    answer_radius = {
        "cluster_key": "__travel_radius__", "field": "__travel_radius__", "rule_id": None,
        "text": "Up to 50 miles", "ledger_label": "Travel radius",
    }

    full = fold_ledger(BASE_PROFILE, [answer_age, answer_biomarker, answer_radius], trials, 39.9612, -82.9988)
    retracted = fold_ledger(BASE_PROFILE, [answer_age, answer_radius], trials, 39.9612, -82.9988)
    direct = fold_ledger(BASE_PROFILE, [answer_age, answer_radius], trials, 39.9612, -82.9988)

    assert retracted["profile"] == direct["profile"]
    assert retracted["open_trial_ids"] == direct["open_trial_ids"]
    assert retracted["trials"].keys() == direct["trials"].keys()
    for nct_id in retracted["trials"]:
        assert retracted["trials"][nct_id]["outlook"].tier == direct["trials"][nct_id]["outlook"].tier

    # Sanity: the biomarker answer (EGFR negative) actually removed trial B in
    # the full run, and trial C is excluded by the 50mi radius in both.
    assert "B" not in full["open_trial_ids"]
    assert "C" not in retracted["open_trial_ids"]
    assert "C" not in direct["open_trial_ids"]


def test_is_open_ignores_unknown_distance():
    assert is_open("Moderate", None, 50.0) is True
    assert is_open("Moderate", 40.0, 50.0) is True
    assert is_open("Moderate", 60.0, 50.0) is False
    assert is_open("Blocked", 10.0, 50.0) is False
    assert is_open("Moderate", 200.0, None) is True
