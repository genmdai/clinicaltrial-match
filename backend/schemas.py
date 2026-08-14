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
    relation: str | None = None  # "mother" | "father" | "sister" | ... — only set
    # when subject=="relative"; added Phase 4 for compose.py's "on behalf of my
    # mother" voice (CLAUDE.md Phase 4 demo script line)
    age: int | None = None
    sex: str | None = None
    condition: str | None = None
    condition_raw: str | None = None
    condition_code: str | None = None
    condition_needs_clarification: bool = False  # true when condition_raw names only
    # a broad category with clinically distinct subtypes (e.g. "diabetes" with no
    # type) that would make a trial search meaningless until resolved
    condition_clarifying_question: str | None = None  # set together with the above
    biomarkers: list[str] = []
    prior_treatments: list[PriorTreatment] = []
    treatment_line: int | None = None
    ecog: int | None = None
    comorbidities: list[str] = []
    location_zip: str | None = None
    assumptions: list[str] = []
    other_facts: dict[str, str] = {}  # topic slug -> "yes" | "no" | "unclear",
    # e.g. {"brain_metastases": "no"} — patient-reported answers to dynamically
    # extracted field="other" criteria (see EligibilityRule.topic)


class NearestSite(BaseModel):
    facility: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    distance_mi: float | None = None  # None when the patient's own location isn't
    # known yet — the trial's site is still shown, just without a computed distance


class TrialSummary(BaseModel):
    nct_id: str
    title: str
    phase: list[str] = []
    status: str
    interventions: list[str] = []
    site_count: int = 0
    nearest_site: NearestSite | None = None
    has_central_contact: bool = False
    nearest_recruiting_distance_mi: float | None = None  # None when patient location
    # unknown, or no site is both geo-located and individually RECRUITING — drives
    # the adaptive-screening travel-radius filter (next_question.py)


class EligibilityRule(BaseModel):
    rule_id: str
    kind: str  # "inclusion" | "exclusion"
    field: str  # "age" | "prior_therapy_class" | "condition" | "biomarker"
    # | "treatment_naive" | "ecog" | "other"
    operator: str  # "gte" | "lte" | "eq" | "contains" | "not_had" | "must_have"
    value: str | int
    source_quote: str
    parse_confidence: str  # "high" | "low"
    topic: str | None = None  # only set when field=="other" AND the LLM found a
    # concrete, reusable, patient-answerable fact (e.g. "brain_metastases") —
    # normalized snake_case, shared across trials that phrase the same fact
    # differently. None means this "other" rule stays free-text/per-trial-only.
    topic_question: str | None = None  # a yes/no question for `topic`, set
    # together with it — the follow-up shown to the patient instead of the
    # generic "confirm with the trial team" catch-all.


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
