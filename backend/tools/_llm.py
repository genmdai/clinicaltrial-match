"""Shared Bedrock model client, reused by extract_profile.py, parse_criteria.py,
and agent.py.

CLAUDE.md §3: region and model ID were resolved live in Phase 0 and are read from
env (.env) — never hardcoded. Loads .env here (once, on first import) so every
entry point (uvicorn, agent.py, evals/run_evals.py, pytest) gets it automatically
— no manual `source .env` step to remember or forget.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from strands.models import BedrockModel

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

_model: BedrockModel | None = None


def get_model() -> BedrockModel:
    global _model
    if _model is None:
        region = os.environ.get("BEDROCK_REGION")
        model_id = os.environ.get("BEDROCK_MODEL_ID")
        if not region or not model_id:
            raise RuntimeError(
                "BEDROCK_REGION and BEDROCK_MODEL_ID must be set — copy .env.example to "
                ".env in the repo root and fill in both values (see CLAUDE.md §3)."
            )
        _model = BedrockModel(region_name=region, model_id=model_id)
    return _model
