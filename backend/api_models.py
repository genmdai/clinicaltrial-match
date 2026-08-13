"""HTTP API request shapes for main.py's endpoints — wire contracts only, not
part of CLAUDE.md §5's core domain schemas.
"""

from pydantic import BaseModel


class ExtractRequest(BaseModel):
    narrative: str


class MatchRequest(BaseModel):
    profile: dict
    radius_mi: float = 50.0


class AnswerPatch(BaseModel):
    rule_id: str
    text: str


class RecomputeRequest(BaseModel):
    profile: dict
    rules: list[dict]
    nct_id: str
    study: dict
    patient_lat: float | None = None
    patient_lon: float | None = None
    answer: AnswerPatch | None = None


class ComposeRequest(BaseModel):
    variant: str  # "email" | "doctor_note"
    profile: dict
    nct_id: str
    verdicts: list[dict]
    contact: dict
    trial_title: str | None = None
    study: dict | None = None
    nearest_site: dict | None = None
