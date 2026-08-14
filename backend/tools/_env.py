"""Loads the repo-root .env once, on first import — shared by every module that
needs an env var (Bedrock, Bright Data, ...) so .env loading isn't implicitly
coupled to whichever module happens to get imported first. Previously this was
only a side effect of importing _llm.py; anything imported before it (e.g. a
future tool needing its own env var) couldn't rely on .env already being
loaded.
"""

from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
