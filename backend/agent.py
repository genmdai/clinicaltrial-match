"""Strands Agent assembly (CLAUDE.md §4).

Bedrock region/model ID are read from env (set in .env, see .env.example) —
resolved live against the human's AWS account in Phase 0, not hardcoded here.
"""

import os

from strands import Agent, tool
from strands.models import BedrockModel


@tool
def echo(text: str) -> str:
    """Echo the given text back. Smoke-test tool for Phase 0 wiring."""
    return text


def build_agent() -> Agent:
    model = BedrockModel(
        region_name=os.environ["BEDROCK_REGION"],
        model_id=os.environ["BEDROCK_MODEL_ID"],
    )
    return Agent(model=model, tools=[echo], system_prompt="You are a smoke-test echo agent.")


if __name__ == "__main__":
    agent = build_agent()
    print(agent("Say hello and then call the echo tool with the word 'ping'."))
