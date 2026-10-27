"""Format values for people: $ for money columns, thousands separators, readable dates."""

from datetime import date

import pandas as pd
from pandas.api.types import is_numeric_dtype, is_scalar

MONEY_HINTS = ("amount", "cost", "price", "revenue", "value", "total", "spend", "sales", "salary", "tax")


def is_money(col) -> bool:
    return any(h in str(col).lower() for h in MONEY_HINTS)


def fmt(col, v) -> str:
    """Format one value, using the column name to decide whether it's money."""
    if v is None or (is_scalar(v) and pd.isna(v)):
        return ""
    if isinstance(v, date):  # also covers datetime and pandas Timestamp
        return f"{v:%b %d, %Y}"
    if isinstance(v, (int, float)) or is_numeric_dtype(type(v)):
        if isinstance(v, bool):
            return str(v)
        v = float(v)
        if is_money(col):
            return f"-${-v:,.2f}" if v < 0 else f"${v:,.2f}"
        return f"{v:,.0f}" if v.is_integer() else f"{v:,.2f}"
    return str(v)
