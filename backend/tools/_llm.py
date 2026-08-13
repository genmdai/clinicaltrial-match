"""Shared Bedrock model client, reused by extract_profile.py and parse_criteria.py.

CLAUDE.md §3: region and model ID were resolved live in Phase 0 and are read from
env (.env) — never hardcoded.
"""

import os

from strands.models import BedrockModel

_model: BedrockModel | None = None


def get_model() -> BedrockModel:
    global _model
    if _model is None:
        _model = BedrockModel(
            region_name=os.environ["BEDROCK_REGION"],
            model_id=os.environ["BEDROCK_MODEL_ID"],
        )
    return _model
