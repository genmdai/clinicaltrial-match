"""Pydantic data shapes shared across backend tools (CLAUDE.md §5)."""

from pydantic import BaseModel


class PriorTreatment(BaseModel):
    raw_mention: str
    drug_brand: str | None = None
    drug_generic: str | None = None
    drug_class: str | None = None
    outcome: str | None = None  # "progression" | "toxicity" | "ongoing" | None
    inferred: bool = False
    confidence: str = "high"  # "high" | "low"
    rxnorm_ingredient: str | None = None


class PatientProfile(BaseModel):
    subject: str  # "self" | "relative"
    age: int | None = None
    sex: str | None = None
    condition: str | None = None
    condition_raw: str | None = None
    condition_code: str | None = None
    biomarkers: list[str] = []
    prior_treatments: list[PriorTreatment] = []
    treatment_line: int | None = None
    location_zip: str | None = None
    assumptions: list[str] = []


class EligibilityRule(BaseModel):
    rule_id: str
    kind: str  # "inclusion" | "exclusion"
    field: str  # "age" | "prior_therapy_class" | "condition" | "biomarker"
    # | "treatment_naive" | "ecog" | "other"
    operator: str  # "gte" | "lte" | "eq" | "contains" | "not_had" | "must_have"
    value: str | int
    source_quote: str
    parse_confidence: str  # "high" | "low"


class CriterionVerdict(BaseModel):
    rule_id: str
    verdict: str  # "PASS" | "FAIL" | "UNKNOWN"
    reason: str
    source_quote: str
    follow_up_question: str | None = None


class OutlookComponent(BaseModel):
    name: str  # "eligibility_fit" | "recruitment_momentum"
    # | "geographic_access" | "contactability"
    score: float
    band: str  # "strong" | "fair" | "weak"
    evidence: list[str] = []


class AccessOutlook(BaseModel):
    trial_nct_id: str
    tier: str  # "High" | "Moderate" | "Low" | "Blocked" | "Unclear"
    components: list[OutlookComponent]
    blocking_rule_id: str | None = None
    open_questions: int = 0
    caveat: str = (
        "Heuristic estimate from registry signals — not a probability. "
        "Final say is the trial team's."
    )
