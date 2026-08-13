"""Eval harness — prints a pass/fail table. Run after every rule-engine change.

Usage: python evals/run_evals.py [--stage extraction]
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.tools.check_eligibility import check_eligibility
from backend.tools.extract_profile import extract_profile
from backend.tools.parse_criteria import parse_criteria

CASES_PATH = Path(__file__).parent / "cases.json"


def _icontains(haystack: str | None, needle: str) -> bool:
    return needle.lower() in (haystack or "").lower()


def _check_prior_treatment_contains(profile: dict, expect: dict) -> bool:
    for pt in profile.get("prior_treatments", []):
        ok = True
        if "drug_generic" in expect and not _icontains(pt.get("drug_generic"), expect["drug_generic"]):
            ok = False
        if "drug_class_keyword" in expect and not _icontains(pt.get("drug_class"), expect["drug_class_keyword"]):
            ok = False
        if "drug_class_any" in expect and not any(_icontains(pt.get("drug_class"), kw) for kw in expect["drug_class_any"]):
            ok = False
        if "outcome" in expect and pt.get("outcome") != expect["outcome"]:
            ok = False
        if "inferred" in expect and pt.get("inferred") != expect["inferred"]:
            ok = False
        if "confidence" in expect and pt.get("confidence") != expect["confidence"]:
            ok = False
        if ok:
            return True
    return False


def check_extraction_case(profile: dict, expect: dict) -> list[str]:
    """Returns a list of failure reasons; empty list means the case passed."""
    failures = []

    if "subject" in expect and profile.get("subject") != expect["subject"]:
        failures.append(f"subject={profile.get('subject')!r}, expected {expect['subject']!r}")
    if "age" in expect and profile.get("age") != expect["age"]:
        failures.append(f"age={profile.get('age')!r}, expected {expect['age']!r}")
    if expect.get("age_null") and profile.get("age") is not None:
        failures.append(f"age={profile.get('age')!r}, expected null")
    if "sex_prefix" in expect:
        sex = (profile.get("sex") or "").lower()
        if not sex.startswith(expect["sex_prefix"].lower()):
            failures.append(f"sex={profile.get('sex')!r}, expected prefix {expect['sex_prefix']!r}")
    if "ecog" in expect and profile.get("ecog") != expect["ecog"]:
        failures.append(f"ecog={profile.get('ecog')!r}, expected {expect['ecog']!r}")
    if "treatment_line" in expect and profile.get("treatment_line") != expect["treatment_line"]:
        failures.append(f"treatment_line={profile.get('treatment_line')!r}, expected {expect['treatment_line']!r}")
    if "treatment_line_min" in expect and (profile.get("treatment_line") or 0) < expect["treatment_line_min"]:
        failures.append(f"treatment_line={profile.get('treatment_line')!r}, expected >= {expect['treatment_line_min']}")
    if expect.get("prior_treatments_empty") and profile.get("prior_treatments"):
        failures.append(f"prior_treatments non-empty: {profile.get('prior_treatments')}")
    if "prior_treatments_count" in expect and len(profile.get("prior_treatments", [])) != expect["prior_treatments_count"]:
        failures.append(f"prior_treatments count={len(profile.get('prior_treatments', []))}, expected {expect['prior_treatments_count']}")
    if "biomarker_keyword" in expect and not any(_icontains(b, expect["biomarker_keyword"]) for b in profile.get("biomarkers", [])):
        failures.append(f"biomarkers={profile.get('biomarkers')!r} missing keyword {expect['biomarker_keyword']!r}")
    if "comorbidities_keyword" in expect and not any(_icontains(c, expect["comorbidities_keyword"]) for c in profile.get("comorbidities", [])):
        failures.append(f"comorbidities={profile.get('comorbidities')!r} missing keyword {expect['comorbidities_keyword']!r}")
    if expect.get("condition_null") and profile.get("condition") is not None:
        failures.append(f"condition={profile.get('condition')!r}, expected null")
    if expect.get("assumptions_nonempty") and not profile.get("assumptions"):
        failures.append("assumptions is empty, expected non-empty")
    if "class_keywords_present" in expect:
        all_classes = " ".join(pt.get("drug_class") or "" for pt in profile.get("prior_treatments", []))
        for kw in expect["class_keywords_present"]:
            alternatives = kw if isinstance(kw, list) else [kw]
            if not any(_icontains(all_classes, alt) for alt in alternatives):
                failures.append(f"no prior_treatment drug_class contains any of {alternatives!r} (classes: {all_classes!r})")
    if "prior_treatment_contains" in expect and not _check_prior_treatment_contains(profile, expect["prior_treatment_contains"]):
        failures.append(f"no prior_treatment matches {expect['prior_treatment_contains']!r} (got {profile.get('prior_treatments')!r})")

    return failures


def check_verdicts_case(verdicts: list[dict], rollup: str, expect: dict) -> list[str]:
    failures = []

    if "rollup_prefix" in expect and not rollup.startswith(expect["rollup_prefix"]):
        failures.append(f"rollup={rollup!r}, expected prefix {expect['rollup_prefix']!r}")
    if "rollup_prefix_any" in expect and not any(rollup.startswith(p) for p in expect["rollup_prefix_any"]):
        failures.append(f"rollup={rollup!r}, expected one of prefixes {expect['rollup_prefix_any']!r}")
    if expect.get("no_fail") and any(v["verdict"] == "FAIL" for v in verdicts):
        fails = [v for v in verdicts if v["verdict"] == "FAIL"]
        failures.append(f"expected no FAIL verdicts, got: {fails}")
    if "fail_reason_contains" in expect:
        needle = expect["fail_reason_contains"]
        if not any(v["verdict"] == "FAIL" and _icontains(v["reason"], needle) for v in verdicts):
            failures.append(f"no FAIL verdict has reason containing {needle!r}")
    if "fail_quote_contains" in expect:
        needle = expect["fail_quote_contains"]
        if not any(v["verdict"] == "FAIL" and _icontains(v["source_quote"], needle) for v in verdicts):
            failures.append(f"no FAIL verdict has source_quote containing {needle!r}")

    return failures


def run_verdicts_stage(cases: list[dict]) -> tuple[int, int]:
    passed = 0
    for case in cases:
        profile_result = extract_profile(case["narrative"])
        if "error" in profile_result:
            print(f"FAIL #{case['id']}: extraction errored: {profile_result['error']}")
            continue

        rules_result = parse_criteria(case["trial_nct_id"], case["criteria_text"])
        if "error" in rules_result:
            print(f"FAIL #{case['id']}: parse_criteria errored: {rules_result['error']}")
            continue

        check_result = check_eligibility(rules_result["rules"], profile_result["profile"])
        if "error" in check_result:
            print(f"FAIL #{case['id']}: check_eligibility errored: {check_result['error']}")
            continue

        failures = check_verdicts_case(check_result["verdicts"], check_result["rollup"], case["expect"])
        if failures:
            print(f"FAIL #{case['id']}: {case['trial_nct_id']} — rollup={check_result['rollup']!r}")
            for f in failures:
                print(f"       - {f}")
        else:
            print(f"PASS #{case['id']}: {case['trial_nct_id']} — rollup={check_result['rollup']!r}")
            passed += 1
    return passed, len(cases)


def run_extraction_stage(cases: list[dict]) -> tuple[int, int]:
    passed = 0
    for case in cases:
        result = extract_profile(case["narrative"])
        if "error" in result:
            print(f"FAIL #{case['id']}: extraction errored: {result['error']}")
            continue
        failures = check_extraction_case(result["profile"], case["expect"])
        if failures:
            print(f"FAIL #{case['id']}: {case['narrative']!r}")
            for f in failures:
                print(f"       - {f}")
        else:
            print(f"PASS #{case['id']}: {case['narrative']!r}")
            passed += 1
    return passed, len(cases)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["extraction", "verdicts"], default=None)
    args = parser.parse_args()

    cases = json.loads(CASES_PATH.read_text())
    if not cases:
        print("0/0 — no cases yet")
        return

    stages = [args.stage] if args.stage else sorted({c["stage"] for c in cases})
    for stage in stages:
        stage_cases = [c for c in cases if c["stage"] == stage]
        if stage == "extraction":
            passed, total = run_extraction_stage(stage_cases)
        elif stage == "verdicts":
            passed, total = run_verdicts_stage(stage_cases)
        else:
            print(f"no runner for stage {stage!r} yet")
            continue
        print(f"{stage}: {passed}/{total}")


if __name__ == "__main__":
    main()
