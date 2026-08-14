"""HTTP API request shapes for main.py's endpoints — wire contracts only, not
part of CLAUDE.md §5's core domain schemas.
"""

from pydantic import BaseModel


class ExtractRequest(BaseModel):
    narrative: str


class MatchRequest(BaseModel):
    profile: dict
    radius_mi: float = 50.0


class GapAnswer(BaseModel):
    gap_id: str
    field: str
    text: str


class PatchProfileRequest(BaseModel):
    profile: dict  # the full profile as already extracted — never overwritten
    answers: list[GapAnswer]  # one or more answers to specific open gaps


class ScreenTrial(BaseModel):
    """One candidate trial's data as already cached client-side from `/match`'s
    `trial_ready` event — resent on every `/screen` call since the backend is
    stateless (CLAUDE.md P7). Trimmed to just what check_eligibility/access_outlook
    actually consume, not the full raw CT.gov study record.
    """
    nct_id: str
    rules: list[dict]
    status_module: dict
    locations: list[dict]
    contact: dict
    nearest_recruiting_distance_mi: float | None = None


class ScreenAnswer(BaseModel):
    cluster_key: str
    field: str
    rule_id: str | None = None
    text: str
    ledger_label: str


class ScreenRequest(BaseModel):
    base_profile: dict  # unmodified extract_profile() output — never overwritten
    answers: list[ScreenAnswer]  # full ordered ledger every time, not a delta
    trials: list[ScreenTrial]
    patient_lat: float | None = None
    patient_lon: float | None = None


class PublicAccessLinksRequest(BaseModel):
    nct_id: str
    facility_name: str | None = None
    sponsor_name: str | None = None


class ComposeRequest(BaseModel):
    variant: str  # "email" | "doctor_note"
    profile: dict
    nct_id: str
    verdicts: list[dict]
    contact: dict
    trial_title: str | None = None
    study: dict | None = None
    nearest_site: dict | None = None
