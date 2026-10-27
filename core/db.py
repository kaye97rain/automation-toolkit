"""Database connection shared by all projects. SQLite file by default (DATABASE_URL in .env)."""

from sqlalchemy import create_engine, inspect
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
