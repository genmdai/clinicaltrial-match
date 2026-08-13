"""Eval harness — prints a pass/fail table. Run after every rule-engine change."""

import json
from pathlib import Path

CASES_PATH = Path(__file__).parent / "cases.json"


def main() -> None:
    cases = json.loads(CASES_PATH.read_text())
    if not cases:
        print("0/0 — no cases yet")
        return
    passed = 0
    for case in cases:
        # Real evaluation logic lands in Phase 2/3 alongside extract_profile / check_eligibility.
        pass
    print(f"{passed}/{len(cases)}")


if __name__ == "__main__":
    main()
