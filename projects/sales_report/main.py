"""Sample automation: raw sales CSV -> formatted Excel summary report.

Run from the toolkit root:  python -m projects.sales_report.main
Drop your own CSV at data/input/sales.csv (columns: date, region, rep, product, units, unit_price)
or let it generate sample data on first run.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from core import config
from core.excel import write_sheets
from core.logger import get_logger
from core.runner import run_job

NAME = "sales_report"
INPUT = config.INPUT_DIR / "sales.csv"
log = get_logger(NAME)


def make_sample_data() -> None:
    rng = np.random.default_rng(42)
    n = 500
    df = pd.DataFrame({
        "date": pd.to_datetime("2026-01-01") + pd.to_timedelta(rng.integers(0, 270, n), unit="D"),
        "region": rng.choice(["North", "South", "East", "West"], n),
        "rep": rng.choice(["Ana", "Ben", "Chen", "Dara", "Eli", "Fay"], n),
        "product": rng.choice(["Basic Plan", "Pro Plan", "Enterprise", "Add-on"], n),
        "units": rng.integers(1, 20, n),
    })
    prices = {"Basic Plan": 49, "Pro Plan": 129, "Enterprise": 499, "Add-on": 19}
    df["unit_price"] = df["product"].map(prices)
    df.to_csv(INPUT, index=False)
    log.info("No input found - generated sample data at %s", INPUT)


def extract() -> pd.DataFrame:
    if not INPUT.exists():
        make_sample_data()
    return pd.read_csv(INPUT, parse_dates=["date"])


def transform(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    df = df.dropna().copy()
    df["revenue"] = df["units"] * df["unit_price"]
    df["month"] = df["date"].dt.to_period("M").astype(str)

    by_month = df.groupby("month", as_index=False)["revenue"].sum()
    by_region = (df.groupby("region", as_index=False)
                   .agg(revenue=("revenue", "sum"), orders=("revenue", "size"))
                   .sort_values("revenue", ascending=False))
    by_rep = (df.groupby("rep", as_index=False)["revenue"].sum()
                .sort_values("revenue", ascending=False))
    by_product = df.pivot_table(index="product", columns="region", values="revenue",
                                aggfunc="sum", fill_value=0).reset_index()

    return {"By Month": by_month, "By Region": by_region, "By Rep": by_rep,
            "Product x Region": by_product, "Raw Data": df}


def load(sheets: dict[str, pd.DataFrame]) -> Path:
    out = write_sheets(config.OUTPUT_DIR / "sales_report.xlsx", sheets)
    total = sheets["Raw Data"]["revenue"].sum()
    log.info("Report written to %s (total revenue: $%s)", out, f"{total:,.0f}")
    return out


def main() -> None:
    load(transform(extract()))


if __name__ == "__main__":
    run_job(NAME, main)
