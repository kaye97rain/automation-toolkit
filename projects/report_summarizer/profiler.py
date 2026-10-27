"""Auto-detect column types in any table and summarize it without configuration."""

import re

import pandas as pd
from pandas.api.types import is_bool_dtype, is_datetime64_any_dtype, is_numeric_dtype

from core.formatting import fmt, is_money

ID_HINTS = {"id", "sku", "code", "number", "no", "#"}
# Per-unit columns where a total is meaningless (show the average instead)
UNIT_HINTS = {"unit", "price", "rate", "level", "pct", "percent", "%"}


def _words(col) -> set[str]:
    return set(re.split(r"[^a-z#%]+", str(col).lower()))


def is_unit_like(col) -> bool:
    return bool(_words(col) & UNIT_HINTS)


def _numbers_from_text(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.astype(str).str.replace(r"[$,\s]", "", regex=True), errors="coerce")


def detect_type(s: pd.Series) -> str:
    """Classify a column as: date, number, category, id or text."""
    values = s.dropna()
    if is_bool_dtype(s):
        return "category"
    if is_datetime64_any_dtype(s):
        return "date"
    if is_numeric_dtype(s):
        return "id" if _words(s.name) & ID_HINTS and values.is_unique else "number"
    if values.empty:
        return "text"
    if _numbers_from_text(values).notna().mean() >= 0.95:
        return "number"  # numbers stored as text, e.g. "$1,200.00"
    if pd.to_datetime(values.astype(str), errors="coerce", format="mixed").notna().mean() >= 0.95:
        return "date"  # dates stored as text, e.g. "07/03/2026"
    if len(values) > 20 and values.nunique() / len(values) >= 0.95:
        return "id"
    if values.nunique() <= 50 or values.nunique() / len(values) <= 0.2:
        return "category"
    return "text"


def prepare(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str]]:
    """Tidy a raw table and convert text numbers/dates to real types. Returns (df, {column: type})."""
    df = df.dropna(how="all").dropna(axis=1, how="all").copy()
    df.columns = [str(c).strip() for c in df.columns]
    types = {}
    for col in df.columns:
        t = detect_type(df[col])
        if t == "number" and not is_numeric_dtype(df[col]):
            df[col] = _numbers_from_text(df[col])
        elif t == "date" and not is_datetime64_any_dtype(df[col]):
            df[col] = pd.to_datetime(df[col], errors="coerce", format="mixed")
        types[col] = t
    return df, types


def cols_of(types: dict, kind: str) -> list[str]:
    return [c for c, t in types.items() if t == kind]


def summable(types: dict) -> list[str]:
    """Number columns worth totalling, money columns first."""
    cols = [c for c in cols_of(types, "number") if not is_unit_like(c)]
    return sorted(cols, key=lambda c: not is_money(c))


def breakdown(df: pd.DataFrame, by: str, sums: list[str]) -> pd.DataFrame:
    """Row count plus totals per group, largest first."""
    g = df.groupby(by)
    out = g[sums].sum() if sums else pd.DataFrame(index=g.size().index)
    out.insert(0, "Rows", g.size())
    return out.sort_values(sums[0] if sums else "Rows", ascending=False).reset_index()


def auto_breakdowns(df: pd.DataFrame, types: dict) -> dict[str, pd.DataFrame]:
    """Group by the first two low-cardinality category columns."""
    cats = [c for c in cols_of(types, "category") if 2 <= df[c].nunique() <= 15][:2]
    return {f"By {c}": breakdown(df, c, summable(types)) for c in cats}


def monthly_trend(df: pd.DataFrame, types: dict) -> pd.DataFrame | None:
    dates = cols_of(types, "date")
    if not dates:
        return None
    d = df[df[dates[0]].notna()]
    month = d[dates[0]].dt.to_period("M").astype(str).rename("Month")
    sums = summable(types)
    g = d.groupby(month)
    out = g[sums].sum() if sums else pd.DataFrame(index=g.size().index)
    out.insert(0, "Rows", g.size())
    return out.reset_index()


def profile(df: pd.DataFrame, types: dict) -> pd.DataFrame:
    """One row per column: detected type, blanks, uniques and key stats."""
    rows = []
    for col, t in types.items():
        s = df[col]
        row = {"Column": col, "Type": t, "Blank": int(s.isna().sum()), "Unique": int(s.nunique())}
        if t == "number":
            row.update(Total=s.sum(), Average=s.mean(), Min=s.min(), Max=s.max())
        elif t == "date":
            row.update(Min=s.min(), Max=s.max())
        elif t == "category" and s.notna().any():
            top = s.value_counts()
            row["Most common"] = f"{top.index[0]} ({top.iloc[0]})"
        rows.append(row)
    return pd.DataFrame(rows)


def highlights(df: pd.DataFrame, types: dict) -> tuple[list[str], list[str]]:
    """Plain-English headline notes and data quality issues."""
    notes, issues = [f"{len(df):,} rows, {len(df.columns)} columns"], []

    dates = cols_of(types, "date")
    if dates and df[dates[0]].notna().any():
        s = df[dates[0]].dropna()
        notes.append(f"{dates[0]}: {s.min():%b %d, %Y} to {s.max():%b %d, %Y}")

    numbers = sorted(cols_of(types, "number"), key=lambda c: (not is_money(c), is_unit_like(c)))
    for col in numbers[:3]:
        if is_unit_like(col):
            notes.append(f"Average {col}: {fmt(col, df[col].mean())}")
        else:
            notes.append(f"Total {col}: {fmt(col, df[col].sum())} (average {fmt(col, df[col].mean())})")

    for col in [c for c in cols_of(types, "category") if 2 <= df[c].nunique() <= 15][:3]:
        top = df[col].value_counts(normalize=True)
        notes.append(f"Most common {col}: {top.index[0]} ({top.iloc[0]:.0%} of rows)")

    dupes = int(df.duplicated().sum())
    if dupes:
        issues.append(f"{dupes} duplicate row(s)")
    for col in df.columns:
        blank = int(df[col].isna().sum())
        if blank:
            issues.append(f"{col}: {blank} blank ({blank / len(df):.0%})")
    for col in cols_of(types, "number"):
        neg = int((df[col] < 0).sum())
        if neg:
            issues.append(f"{col}: {neg} negative value(s)")
    return notes, issues
