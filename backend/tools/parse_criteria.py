"""eligibilityCriteria free text -> EligibilityRule[] (CLAUDE.md §4: LLM parses,
check_eligibility.py judges).

Text is chunked by the conventional "Inclusion Criteria:" / "Exclusion Criteria:"
headers BEFORE calling the LLM, so `kind` is assigned deterministically by Python
rather than trusted from model output (falls back to letting the model decide only
when no headers are found at all). Every rule's source_quote is validated as a
verbatim substring of the original text (P1) — a chunk with any non-verbatim quote
is re-asked once; anything still unverified, or outside the field/operator vocab,
is forced to parse_confidence="low" (never dropped — check_eligibility.py caps
low-confidence rules at UNKNOWN per P2/P3, it doesn't need them discarded).
"""

import asyncio
import json
import re
from pathlib import Path

from pydantic import BaseModel
from strands import Agent, tool

from ..schemas import EligibilityRule
from ._llm import get_model

CACHE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "cache"

_INCLUSION_RE = re.compile(r"inclusion criteria:?", re.IGNORECASE)
_EXCLUSION_RE = re.compile(r"exclusion criteria:?", re.IGNORECASE)

_VALID_FIELDS = {"age", "prior_therapy_class", "condition", "biomarker", "treatment_naive", "ecog", "other"}
_VALID_OPERATORS = {"gte", "lte", "eq", "contains", "not_had", "must_have"}

SYSTEM_PROMPT = """You extract structured eligibility rules from one section (either \
INCLUSION or EXCLUSION, occasionally unlabeled) of a clinical trial's eligibility \
criteria text.

For EVERY distinct criterion/bullet point in the input, produce exactly one rule — \
including administrative ones (map those to field="other" rather than skipping them):

- kind: "inclusion" or "exclusion" — match the section this text came from; if \
genuinely unlabeled, use your best judgment.
- field: exactly one of "age", "prior_therapy_class", "condition", "biomarker", \
"treatment_naive", "ecog", "other". Use "other" for anything that doesn't fit \
(brain metastases, organ function, informed consent, pregnancy, prior therapy line \
counts, etc.) — do not force a bad fit.
- operator: exactly one of "gte", "lte", "eq", "contains", "not_had", "must_have".
  - age / ecog: "gte"/"lte"/"eq" with a numeric value.
  - condition: "contains", value = the key diagnosis phrase.
  - biomarker: "must_have" (a specific marker/status is required) or "contains".
  - treatment_naive: "must_have" when the criterion requires no prior systemic therapy.
  - prior_therapy_class: "not_had" for excluding a specific prior drug class — value \
is a short class keyword like "anti-PD-1", "anti-PD-L1", "EGFR TKI", "platinum \
chemotherapy" (not a full sentence).
  - other: default to "contains".
- value: the number or short keyword the operator compares against.
- source_quote: copy the EXACT verbatim substring of the input text this rule comes \
from — must be an exact character-for-character substring, never paraphrased or \
corrected for typos.

If one bullet combines multiple independent requirements, split them into separate \
rules, each still quoting its own verbatim substring.
"""


class _ParsedRuleLLM(BaseModel):
    kind: str
    field: str
    operator: str
    value: str | int
    source_quote: str


class _ParsedRules(BaseModel):
    rules: list[_ParsedRuleLLM]


def split_criteria(text: str) -> dict[str, str]:
    """Split eligibilityCriteria free text into named chunks by the conventional
    headers. Falls back to a single "unspecified" chunk (kind determined by the
    LLM itself) when neither header is found.
    """
    inc = _INCLUSION_RE.search(text)
    exc = _EXCLUSION_RE.search(text)
    if not inc and not exc:
        return {"unspecified": text.strip()}

    chunks = {}
    if inc and exc:
        if inc.start() < exc.start():
            chunks["inclusion"] = text[inc.end():exc.start()].strip()
            chunks["exclusion"] = text[exc.end():].strip()
        else:
            chunks["exclusion"] = text[exc.end():inc.start()].strip()
            chunks["inclusion"] = text[inc.end():].strip()
    elif inc:
        chunks["inclusion"] = text[inc.end():].strip()
    else:
        chunks["exclusion"] = text[exc.end():].strip()
    return {k: v for k, v in chunks.items() if v}


async def _extract_chunk_async(chunk_text: str) -> list[_ParsedRuleLLM]:
    agent = Agent(model=get_model(), system_prompt=SYSTEM_PROMPT)
    result = await agent.invoke_async(chunk_text, structured_output_model=_ParsedRules)
    if result.structured_output is None:
        raise ValueError("model returned no structured output")
    return result.structured_output.rules


async def _extract_chunk_with_retry_async(chunk_text: str, full_text: str) -> list[_ParsedRuleLLM]:
    rules = await _extract_chunk_async(chunk_text)
    if not all(r.source_quote in full_text for r in rules):
        rules = await _extract_chunk_async(chunk_text)  # one re-ask, per P1
    return rules


def _reconcile_rule(raw: _ParsedRuleLLM, known_kind: str | None, nct_id: str, index: int, full_text: str) -> EligibilityRule:
    kind = known_kind if known_kind in ("inclusion", "exclusion") else (
        raw.kind if raw.kind in ("inclusion", "exclusion") else "inclusion"
    )
    field = raw.field if raw.field in _VALID_FIELDS else "other"
    operator = raw.operator if raw.operator in _VALID_OPERATORS else "contains"

    confidence = "high"
    if field == "other" or raw.field not in _VALID_FIELDS or raw.operator not in _VALID_OPERATORS:
        confidence = "low"
    if raw.source_quote not in full_text:
        confidence = "low"  # quote still didn't validate after the retry (P1)

    return EligibilityRule(
        rule_id=f"{nct_id}-{index}",
        kind=kind,
        field=field,
        operator=operator,
        value=raw.value,
        source_quote=raw.source_quote,
        parse_confidence=confidence,
    )


async def _parse_one_async(nct_id: str, criteria_text: str) -> list[EligibilityRule]:
    chunks = split_criteria(criteria_text)
    all_rules: list[EligibilityRule] = []
    index = 0
    for chunk_kind, chunk_text in chunks.items():
        known_kind = chunk_kind if chunk_kind in ("inclusion", "exclusion") else None
        raw_rules = await _extract_chunk_with_retry_async(chunk_text, criteria_text)
        for raw in raw_rules:
            all_rules.append(_reconcile_rule(raw, known_kind, nct_id, index, criteria_text))
            index += 1
    return all_rules


def _cache_path(nct_id: str) -> Path:
    return CACHE_DIR / f"criteria_{nct_id}.json"


def _read_cache(nct_id: str) -> list[dict] | None:
    path = _cache_path(nct_id)
    return json.loads(path.read_text()) if path.exists() else None


def _write_cache(nct_id: str, rules: list[EligibilityRule]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(nct_id).write_text(json.dumps([r.model_dump() for r in rules]))


@tool
def parse_criteria(nct_id: str, criteria_text: str) -> dict:
    """Parse a trial's free-text eligibility criteria into structured rules.

    Args:
        nct_id: The trial's NCT identifier — used as the cache key (criteria
            text rarely changes intraday, per CLAUDE.md §6).
        criteria_text: The trial's protocolSection.eligibilityModule
            .eligibilityCriteria free text.

    Returns:
        {"rules": [EligibilityRule, ...]} on success, or {"error": "<message>"}
        on failure — never raises into the agent loop.
    """
    try:
        cached = _read_cache(nct_id)
        if cached is not None:
            return {"rules": cached}

        rules = asyncio.run(_parse_one_async(nct_id, criteria_text))
        _write_cache(nct_id, rules)
        return {"rules": [r.model_dump() for r in rules]}
    except Exception as e:  # noqa: BLE001 — tool boundary: must never raise into the agent loop (CLAUDE.md §6)
        return {"error": str(e)}


async def parse_criteria_batch(trials: list[dict]) -> dict[str, dict]:
    """Parse up to 5 trials concurrently (latency budget, CLAUDE.md Phase 3).

    Args:
        trials: list of {"nct_id": str, "criteria_text": str}, capped at 5.

    Returns:
        {nct_id: {"rules": [...]}} or {nct_id: {"error": "<message>"}} per trial.
    """
    async def _one(trial: dict) -> tuple[str, dict]:
        nct_id = trial["nct_id"]
        cached = _read_cache(nct_id)
        if cached is not None:
            return nct_id, {"rules": cached}
        try:
            rules = await _parse_one_async(nct_id, trial["criteria_text"])
            _write_cache(nct_id, rules)
            return nct_id, {"rules": [r.model_dump() for r in rules]}
        except Exception as e:  # noqa: BLE001 — per-trial isolation: one bad trial must not sink the batch
            return nct_id, {"error": str(e)}

    results = await asyncio.gather(*(_one(t) for t in trials[:5]))
    return dict(results)
