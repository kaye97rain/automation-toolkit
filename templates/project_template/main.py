"""__PROJECT__ automation.

Trigger -> Get data -> Transform/decide -> Act -> Log/notify
Run from the toolkit root:  python -m projects.__PROJECT__.main
"""

import pandas as pd

from core import config
from core.excel import write_sheets
from core.logger import get_logger
from core.runner import run_job

NAME = "__PROJECT__"
log = get_logger(NAME)


def extract() -> pd.DataFrame:
    """Get data: read a file, call an API, query a database..."""
    raise NotImplementedError


def transform(df: pd.DataFrame) -> pd.DataFrame:
    """Clean, filter, apply business rules."""
    return df


def load(df: pd.DataFrame) -> None:
    """Act: write a report, update a system, send a notification."""
    out = write_sheets(config.OUTPUT_DIR / f"{NAME}.xlsx", {"Result": df})
    log.info("Wrote %s", out)


def main() -> None:
    df = extract()
    df = transform(df)
    load(df)


if __name__ == "__main__":
    run_job(NAME, main)
