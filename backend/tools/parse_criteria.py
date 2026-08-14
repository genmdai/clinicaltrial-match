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
import os
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

# Bounds concurrent Bedrock calls across a batch. Raised 6 -> 16 alongside the
# 15 -> 50 MAX_CANDIDATES bump (search_trials.py) to keep the "Comparing
# eligibility criteria…" stage from taking ~3x longer — trades a higher risk of
# Bedrock throttling (no backoff anywhere in this module) for less wall-clock
# time. Env-configurable so a demo can tune it back down without a code change.
_PARSE_SEMAPHORE = asyncio.Semaphore(int(os.environ.get("PARSE_CRITERIA_CONCURRENCY", "16")))

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
- topic / topic_question (ONLY when field="other"): if the criterion describes a \
concrete, current fact about the patient's own health or history that the patient \
could confirm with a single yes/no answer (e.g. brain/CNS metastases, pregnancy or \
breastfeeding, HIV or Hepatitis B/C infection, measurable disease, autoimmune \
disease, major surgery) — as opposed to administrative/procedural criteria with no \
such fact (informed consent, willingness to comply, site logistics, contraception \
commitments) — also set:
  - topic: a short, normalized snake_case identifier for the underlying fact, the \
SAME identifier every time this fact recurs even if a trial's wording differs (e.g. \
always "brain_metastases", never "cns_involvement" one time and "brain_mets" the \
next).
  - topic_question: one natural yes/no question a patient could answer to resolve \
it, e.g. "Does the patient currently have brain metastases?".
  Leave both null when field != "other", or when no such reusable, \
patient-answerable fact applies.
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
    topic: str | None = None
    topic_question: str | None = None


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
    async with _PARSE_SEMAPHORE:
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


def _normalize_topic(raw_topic: str | None) -> str | None:
    """Defensive normalization of the LLM's free-text topic into a stable
    clustering key — never trust model output verbatim as a dict/cluster key.
    """
    if not raw_topic:
        return None
    slug = re.sub(r"[^a-z0-9]+", "_", raw_topic.strip().lower()).strip("_")
    return slug or None


def _reconcile_rule(raw: _ParsedRuleLLM, known_kind: str | None, nct_id: str, index: int, full_text: str) -> EligibilityRule:
    kind = known_kind if known_kind in ("inclusion", "exclusion") else (
        raw.kind if raw.kind in ("inclusion", "exclusion") else "inclusion"
    )
    field = raw.field if raw.field in _VALID_FIELDS else "other"
    operator = raw.operator if raw.operator in _VALID_OPERATORS else "contains"
    topic = _normalize_topic(raw.topic) if field == "other" else None
    topic_question = raw.topic_question.strip() if (topic and raw.topic_question) else None

    confidence = "high"
    if raw.field not in _VALID_FIELDS or raw.operator not in _VALID_OPERATORS:
        confidence = "low"
    elif field == "other" and topic is None:
        # Free-text "other" with no extractable reusable fact — same "can't
        # automatically judge this" bucket as before topic/topic_question existed.
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
        topic=topic,
        topic_question=topic_question,
    )


async def _parse_one_async(nct_id: str, criteria_text: str) -> list[EligibilityRule]:
    # Inclusion and exclusion chunks don't depend on each other's output, so
    # gather them instead of awaiting in sequence — halves a trial's own
    # completion latency without raising peak concurrent Bedrock calls (each
    # chunk still acquires _PARSE_SEMAPHORE independently).
    chunks = list(split_criteria(criteria_text).items())
    results = await asyncio.gather(
        *(_extract_chunk_with_retry_async(chunk_text, criteria_text) for _, chunk_text in chunks)
    )

    all_rules: list[EligibilityRule] = []
    index = 0
    for (chunk_kind, _), raw_rules in zip(chunks, results, strict=True):
        known_kind = chunk_kind if chunk_kind in ("inclusion", "exclusion") else None
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
    """Parse a batch of trials concurrently — caller controls how many (the
    per-chunk `_PARSE_SEMAPHORE` bounds actual simultaneous Bedrock calls
    regardless of batch size, CLAUDE.md Phase 3/§6).

    Args:
        trials: list of {"nct_id": str, "criteria_text": str}.

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

    results = await asyncio.gather(*(_one(t) for t in trials))
    return dict(results)


async def parse_criteria_stream(trials: list[dict]):
    """Like parse_criteria_batch, but an async generator yielding (nct_id, result)
    as each trial finishes — for progressive UI progress ("Checking eligibility
    for NCT0512… ✓") instead of waiting for the whole batch at once.

    Args:
        trials: list of {"nct_id": str, "criteria_text": str}. Caller controls
            how many; `_PARSE_SEMAPHORE` bounds simultaneous Bedrock calls.

    Yields:
        (nct_id, {"rules": [...]}) or (nct_id, {"error": "<message>"}), in
        completion order (not necessarily input order).
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
        except Exception as e:  # noqa: BLE001 — per-trial isolation: one bad trial must not sink the stream
            return nct_id, {"error": str(e)}

    for coro in asyncio.as_completed([_one(t) for t in trials]):
        yield await coro
