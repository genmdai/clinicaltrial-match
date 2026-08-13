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
    ecog: int | None = None
    comorbidities: list[str] = []
    location_zip: str | None = None
    assumptions: list[str] = []


class NearestSite(BaseModel):
    facility: str | None = None
    city: str | None = None
    state: str | None = None
    distance_mi: float


class TrialSummary(BaseModel):
    nct_id: str
    title: str
    phase: list[str] = []
    status: str
    interventions: list[str] = []
    site_count: int = 0
    nearest_site: NearestSite | None = None
    has_central_contact: bool = False


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


# --- Bright Data enrichment (trial/site identity only — never PatientProfile
# or any other patient data crosses this boundary) ---


class TrialEnrichmentInput(BaseModel):
    nct_id: str
    title: str
    sponsor: str | None = None


class SiteEnrichmentInput(BaseModel):
    facility: str
    city: str | None = None
    state: str | None = None
    hospital_domain: str | None = None


class HospitalTrialPage(BaseModel):
    url: str | None = None
    title: str | None = None


class TrialOfficeContact(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    contact_form: str | None = None


class ReferralInfo(BaseModel):
    instructions: str | None = None
    physician_referral_required: bool | None = None
    url: str | None = None


class EnrichmentSource(BaseModel):
    url: str
    title: str | None = None
    domain_type: str  # "hospital" | "sponsor" | "other"


class TrialAccessEnrichment(BaseModel):
    trial_id: str
    site: str | None = None
    hospital_trial_page: HospitalTrialPage = HospitalTrialPage()
    trial_office: TrialOfficeContact = TrialOfficeContact()
    referral: ReferralInfo = ReferralInfo()
    documents_mentioned: list[str] = []
    sponsor_study_page: str | None = None
    patient_resources: list[str] = []
    sources: list[EnrichmentSource] = []
