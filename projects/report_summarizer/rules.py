"""Per-report business rules from reports.yaml: calculated columns, breakdowns and alerts."""

import logging
from fnmatch import fnmatch
from pathlib import Path

import pandas as pd
import yaml

from projects.report_summarizer.profiler import breakdown

CONFIG = Path(__file__).with_name("reports.yaml")


def load_rules() -> dict:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8")).get("reports") or {}


def find_rule(filename: str, rules: dict) -> tuple[str, dict] | None:
    """First rule whose `match` pattern fits the file name (case-insensitive)."""
    for name, rule in rules.items():
        if fnmatch(filename.lower(), rule["match"].lower()):
            return name, rule
    return None


def apply_rule(df: pd.DataFrame, rule: dict, log: logging.Logger) -> dict:
    """A broken rule is logged and skipped so one typo doesn't stop the whole report."""
    df = df.copy()
    for col, expr in (rule.get("calculated") or {}).items():
        try:
            df[col] = df.eval(expr)
        except Exception as e:
            log.warning("Skipping calculated column %r: %s", col, e)

    sums = [c for c in rule.get("sum", []) if c in df.columns]
    breakdowns = {}
    for col in rule.get("group_by", []):
        if col not in df.columns:
            log.warning("Skipping group_by %r: no such column", col)
            continue
        breakdowns[f"By {col}"] = breakdown(df, col, sums)

    alerts = []
    for alert in rule.get("alerts", []):
        try:
            hits = df.query(alert["when"])
        except Exception as e:
            log.warning("Skipping alert %r: %s", alert["name"], e)
            continue
        if alert.get("sort_by") in hits.columns:
            hits = hits.sort_values(alert["sort_by"], ascending=alert.get("ascending", False))
        show = [c for c in alert.get("show", []) if c in hits.columns] or list(hits.columns)
        alerts.append({"name": alert["name"], "rows": hits[show]})

    return {"df": df, "breakdowns": breakdowns, "alerts": alerts}
