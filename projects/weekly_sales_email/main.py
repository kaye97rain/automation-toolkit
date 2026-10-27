"""Weekly sales email: build the sales report and email it with a KPI summary.

Run from the toolkit root:
    python -m projects.weekly_sales_email.main --dry-run   # build only, save an email preview
    python -m projects.weekly_sales_email.main             # build and send

Needs in .env: SMTP_USER, SMTP_PASSWORD (Gmail App Password), REPORT_RECIPIENTS.
"""

import argparse
from datetime import date

import pandas as pd

from core import config, notify
from core.logger import get_logger
from core.runner import run_job
from projects.sales_report import main as sales_report

NAME = "weekly_sales_email"
log = get_logger(NAME)


def summarize(sheets: dict[str, pd.DataFrame]) -> dict:
    """Pull the headline numbers a manager wants to see without opening the file."""
    raw = sheets["Raw Data"]
    by_month = sheets["By Month"].sort_values("month")
    latest, previous = by_month.iloc[-1], by_month.iloc[-2] if len(by_month) > 1 else None
    change = None
    if previous is not None and previous["revenue"]:
        change = (latest["revenue"] - previous["revenue"]) / previous["revenue"] * 100

    return {
        "total_revenue": raw["revenue"].sum(),
        "orders": len(raw),
        "avg_order": raw["revenue"].mean(),
        "top_region": sheets["By Region"].iloc[0]["region"],
        "top_rep": sheets["By Rep"].iloc[0]["rep"],
        "latest_month": latest["month"],
        "latest_month_revenue": latest["revenue"],
        "month_change_pct": change,
    }


def build_html(s: dict) -> str:
    if s["month_change_pct"] is None:
        change = "n/a"
    else:
        color = "#1a7f37" if s["month_change_pct"] >= 0 else "#cf222e"
        change = f'<span style="color:{color}">{s["month_change_pct"]:+.1f}% vs previous month</span>'

    rows = [
        ("Total revenue", f"${s['total_revenue']:,.0f}"),
        ("Orders", f"{s['orders']:,}"),
        ("Average order value", f"${s['avg_order']:,.0f}"),
        (f"Revenue in {s['latest_month']}", f"${s['latest_month_revenue']:,.0f} &nbsp; {change}"),
        ("Top region", s["top_region"]),
        ("Top sales rep", s["top_rep"]),
    ]
    table = "".join(
        f'<tr><td style="padding:6px 16px 6px 0;color:#555">{k}</td>'
        f'<td style="padding:6px 0;font-weight:600">{v}</td></tr>'
        for k, v in rows
    )
    return f"""\
<div style="font-family:Segoe UI,Arial,sans-serif;font-size:14px;color:#222">
  <h2 style="color:#1F4E78;margin-bottom:4px">Weekly Sales Report</h2>
  <p style="color:#777;margin-top:0">Generated {date.today():%A, %B %d, %Y}</p>
  <table style="border-collapse:collapse">{table}</table>
  <p>The full breakdown (by month, region, rep and product) is in the attached Excel file.</p>
  <p style="color:#999;font-size:12px">Sent automatically by the automation toolkit.</p>
</div>"""


def main(dry_run: bool) -> None:
    sheets = sales_report.transform(sales_report.extract())
    report = sales_report.load(sheets)
    html = build_html(summarize(sheets))
    subject = f"Weekly Sales Report - {date.today():%b %d, %Y}"

    if dry_run:
        preview = config.OUTPUT_DIR / f"{NAME}_preview.html"
        preview.write_text(html, encoding="utf-8")
        log.info("Dry run - email not sent. Preview saved to %s", preview)
        return

    recipients = [r.strip() for r in config.get("REPORT_RECIPIENTS", required=True).split(",")]
    notify.send_email(recipients, subject, html, attachments=[report], html=True)
    log.info("Email sent to %s", ", ".join(recipients))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="build the report but don't send")
    args = parser.parse_args()
    run_job(NAME, lambda: main(args.dry_run), alert_on_failure=True)
