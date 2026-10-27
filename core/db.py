"""Database connection shared by all projects. SQLite file by default (DATABASE_URL in .env)."""

import pandas as pd
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

from core import config


def get_engine() -> Engine:
    url = config.get("DATABASE_URL", "sqlite:///data/automation.db")
    path = url.removeprefix("sqlite:///")
    if url.startswith("sqlite:///") and ":" not in path[:3] and not path.startswith("/"):
        url = f"sqlite:///{(config.ROOT / path).as_posix()}"  # relative path -> inside the toolkit
    return create_engine(url)


def table_exists(engine: Engine, name: str) -> bool:
    return inspect(engine).has_table(name)


def add_missing_columns(engine: Engine, table: str, df: pd.DataFrame) -> None:
    """Add any new DataFrame columns to an existing table - a simple schema migration
    so a project can gain fields without losing the history already stored."""
    if not table_exists(engine, table):
        return
    existing = {c["name"] for c in inspect(engine).get_columns(table)}
    with engine.begin() as conn:
        for col in df.columns:
            if col not in existing:
                conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN "{col}"'))
