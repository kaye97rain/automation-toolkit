"""Report summarizer: summarize every Excel/CSV file in data/input/ and email the results.

Files matching a rule in reports.yaml get business-specific breakdowns and alerts;
any other file gets an automatic summary based on detected column types.

Run from the toolkit root:
    python -m projects.report_summarizer.main --dry-run   # build only, save an email preview
    python -m projects.report_summarizer.main             # build and send

Needs in .env: SMTP_USER, SMTP_PASSWORD, REPORT_RECIPIENTS.
"""

import argparse
import re
from datetime import date
from html import escape
from pathlib import Path

import pandas as pd

from core import config, notify
from core.excel import write_sheets
from core.logger import get_logger
from core.runner import run_job
from projects.report_summarizer import profiler, rules

NAME = "report_summarizer"
SUPPORTED = {".csv", ".xlsx"}
SUMMARY_DIR = config.OUTPUT_DIR / "summaries"
log = get_logger(NAME)


def find_inputs() -> list[Path]:
    return sorted(p for p in config.INPUT_DIR.iterdir()
                  if p.suffix.lower() in SUPPORTED and not p.name.startswith("~$"))  # ~$ = Excel lock file


def read_table(path: Path) -> pd.DataFrame:
    return pd.read_csv(path) if path.suffix.lower() == ".csv" else pd.read_excel(path)  # first sheet


def sheet_name(name: str) -> str:
    return re.sub(r"[\[\]:*?/\\]", "", name)[:31]  # Excel's sheet name limits


def summarize_file(path: Path, all_rules: dict) -> dict:
    df, types = profiler.prepare(read_table(path))
    result = {"file": path.name, "title": path.stem.replace("_", " ").title(),
              "mode": "auto-detected", "alerts": []}

    match = rules.find_rule(path.name, all_rules)
    if match:
        rule_name, rule = match
        applied = rules.apply_rule(df, rule, log)
        df = applied["df"]
        for col in df.columns:
            types.setdefault(col, profiler.detect_type(df[col]))  # calculated columns
        result.update(title=rule.get("title", result["title"]), mode=f"rules: {rule_name}",
                      alerts=applied["alerts"], breakdowns=applied["breakdowns"])
    else:
        result["breakdowns"] = profiler.auto_breakdowns(df, types)

    result["notes"], result["issues"] = profiler.highlights(df, types)
    result["excel"] = write_summary_excel(path, df, types, result)
    log.info("Summarized %s (%s) -> %s", path.name, result["mode"], result["excel"].name)
    return result


def write_summary_excel(path: Path, df: pd.DataFrame, types: dict, r: dict) -> Path:
    overview = pd.DataFrame(
        [("Highlight", n) for n in r["notes"]]
        + [("Alert", f"{a['name']}: {len(a['rows'])}") for a in r["alerts"]]
        + [("Data quality", i) for i in r["issues"]],
        columns=["Section", "Note"],
    )
    sheets = {"Overview": overview}
    for a in r["alerts"]:
        if len(a["rows"]):
            sheets[sheet_name(f"Alert - {a['name']}")] = a["rows"]
    for name, table in r["breakdowns"].items():
        sheets[sheet_name(name)] = table
    trend = profiler.monthly_trend(df, types)
    if trend is not None:
        sheets["Monthly Trend"] = trend
    sheets["Column Profile"] = profiler.profile(df, types)

    SUMMARY_DIR.mkdir(exist_ok=True)
    return write_sheets(SUMMARY_DIR / f"{path.stem}_summary.xlsx", sheets)


# --- Email ---

TH = "text-align:left;padding:4px 10px;background:#1F4E78;color:#fff;font-weight:600"
TD = "padding:4px 10px;border-bottom:1px solid #e5e5e5"


def html_table(df: pd.DataFrame, max_rows: int = 5) -> str:
    head = "".join(f'<th style="{TH}">{escape(str(c))}</th>' for c in df.columns)
    body = "".join(
        "<tr>" + "".join(f'<td style="{TD}">{escape(profiler.fmt(c, v))}</td>' for c, v in row.items()) + "</tr>"
        for _, row in df.head(max_rows).iterrows()
    )
    more = (f'<p style="color:#777;font-size:12px;margin:4px 0">...and {len(df) - max_rows} more '
            f"in the attachment</p>") if len(df) > max_rows else ""
    return f'<table style="border-collapse:collapse;font-size:13px"><tr>{head}</tr>{body}</table>{more}'


def bullets(items: list[str], color: str = "#222") -> str:
    return f'<ul style="margin:4px 0;color:{color}">' + "".join(f"<li>{escape(i)}</li>" for i in items) + "</ul>"


def section_html(r: dict) -> str:
    parts = [f'<h3 style="color:#1F4E78;margin:28px 0 2px">{escape(r["title"])}</h3>']
    if "error" in r:
        parts.append(f'<p style="color:#cf222e">Could not read {escape(r["file"])}: {escape(r["error"])}</p>')
        return "".join(parts)

    parts.append(f'<p style="color:#777;margin:0 0 8px;font-size:12px">{escape(r["file"])} &middot; '
                 f'{escape(r["mode"])}</p>')
    for a in r["alerts"]:
        if len(a["rows"]):
            parts.append(f'<p style="margin:10px 0 4px;color:#cf222e;font-weight:600">&#9888; '
                         f'{escape(a["name"])}: {len(a["rows"])}</p>' + html_table(a["rows"]))
        else:
            parts.append(f'<p style="margin:10px 0 4px;color:#1a7f37">&#10003; {escape(a["name"])}: none</p>')
    parts.append(bullets(r["notes"]))
    if r["issues"]:
        parts.append('<p style="margin:8px 0 0;color:#9a6700;font-weight:600">Data quality</p>'
                     + bullets(r["issues"], "#9a6700"))
    if r["breakdowns"]:
        name, table = next(iter(r["breakdowns"].items()))
        parts.append(f'<p style="margin:10px 0 4px;font-weight:600">{escape(name)}</p>' + html_table(table))
    return "".join(parts)


def build_email(results: list[dict]) -> str:
    return f"""\
<div style="font-family:Segoe UI,Arial,sans-serif;font-size:14px;color:#222;max-width:820px">
  <h2 style="color:#1F4E78;margin-bottom:4px">Report Summary</h2>
  <p style="color:#777;margin-top:0">{date.today():%A, %B %d, %Y} &middot; {len(results)} file(s).
     Full details are in the attached Excel summaries.</p>
  {"".join(section_html(r) for r in results)}
  <p style="color:#999;font-size:12px;margin-top:28px">Sent automatically by the automation toolkit.</p>
</div>"""


def main(dry_run: bool) -> None:
    files = find_inputs()
    if not files:
        log.warning("No .csv or .xlsx files in %s - nothing to summarize", config.INPUT_DIR)
        return

    all_rules = rules.load_rules()
    results = []
    for path in files:
        try:
            results.append(summarize_file(path, all_rules))
        except Exception as e:  # one bad file shouldn't stop the others
            log.exception("Failed to summarize %s", path.name)
            results.append({"file": path.name, "title": path.stem.replace("_", " ").title(), "error": str(e)})

    html = build_email(results)
    alert_count = sum(1 for r in results for a in r.get("alerts", []) if len(a["rows"]))
    subject = f"Report Summary - {date.today():%b %d, %Y} ({len(results)} files, {alert_count} alerts)"

    if dry_run:
        preview = config.OUTPUT_DIR / f"{NAME}_preview.html"
        preview.write_text(html, encoding="utf-8")
        log.info("Dry run - email not sent. Preview saved to %s", preview)
        return

    recipients = [r.strip() for r in config.get("REPORT_RECIPIENTS", required=True).split(",")]
    attachments = [r["excel"] for r in results if "excel" in r]
    notify.send_email(recipients, subject, html, attachments=attachments, html=True)
    log.info("Email sent to %s with %d attachment(s)", ", ".join(recipients), len(attachments))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="build the summaries but don't send")
    args = parser.parse_args()
    run_job(NAME, lambda: main(args.dry_run), alert_on_failure=True)
