"""Central config: project paths and settings loaded from .env."""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
INPUT_DIR = DATA_DIR / "input"
OUTPUT_DIR = DATA_DIR / "output"
LOG_DIR = ROOT / "logs"

load_dotenv(ROOT / ".env")

for _d in (INPUT_DIR, OUTPUT_DIR, LOG_DIR):
    _d.mkdir(parents=True, exist_ok=True)


def get(name: str, default: str | None = None, required: bool = False) -> str | None:
    """Read a setting from the environment. Raise if required and missing."""
    value = os.getenv(name, default)
    if required and not value:
        raise RuntimeError(f"Missing required setting {name!r} - add it to your .env file")
    return value
