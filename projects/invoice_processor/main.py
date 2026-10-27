"""Invoice processor: PDF invoices in data/input/invoices/ -> checked, logged, filed and reported.

For each PDF: extract the fields, check for problems, save it to the invoice register
(database), then move the file to processed/ (OK) or needs_review/ (anything flagged).
Fields are read with patterns first (free, instant); if that fails - an unfamiliar layout or a
scanned image - Claude reads the invoice instead (needs ANTHROPIC_API_KEY in .env).

Run from the toolkit root:
    python -m projects.invoice_processor.main --dry-run   # check only: no database, no moving, no email
    python -m projects.invoice_processor.main             # process, file and email the summary
"""

import argparse
import shutil
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from core import ai, config, db, notify
from core.excel import write_sheets
from core.html_email import AMBER, RED, bullets, heading, html_table, page
from core.logger import get_logger
from core.runner import run_job
from projects.invoice_processor import extractor

NAME = "invoice_processor"
INBOX = config.INPUT_DIR / "invoices"
PROCESSED = INBOX / "processed"
NEEDS_REVIEW = INBOX / "needs_review"
REGISTER = config.OUTPUT_DIR / "invoice_register.xlsx"
TABLE = "invoices"

REQUIRED = ["vendor", "invoice_no", "invoice_date", "total"]
APPROVAL_LIMIT = 10_000  # invoices above this need manager sign-off
REVIEW_AI_EXTRACTIONS = True  # a person checks AI-read invoices before payment (human in the loop)
DATE_COLS = ["invoice_date", "due_date"]
log = get_logger(NAME)


def dup_key(inv: dict) -> tuple | None:
    vendor, number = inv.get("vendor"), inv.get("invoice_no")
    if isinstance(vendor, str) and isinstance(number, str):
        return vendor.strip().lower(), number.strip().upper()
    return None


def validate(inv: dict, is_duplicate: bool) -> list[str]:
    """Business checks. Returns a list of problems (empty = OK to pay)."""
    issues = ["Duplicate of an invoice already processed"] if is_duplicate else []
    issues += [f"Missing {f.replace('_', ' ')}" for f in REQUIRED if inv.get(f) is None]

    if inv.get("subtotal") is not None and inv.get("total") is not None:
        expected = inv["subtotal"] + (inv.get("tax") or 0)
        if abs(expected - inv["total"]) > 0.01:
            issues.append(f"Total doesn't add up: subtotal + tax = ${expected:,.2f}, "
                          f"invoice says ${inv['total']:,.2f}")

    if inv.get("due_date") is None:
        issues.append("No due date or payment terms")
    elif inv.get("invoice_date") and inv["due_date"] < inv["invoice_date"]:
        issues.append("Due date is before invoice date")

    if (inv.get("total") or 0) > APPROVAL_LIMIT:
        issues.append(f"Over ${APPROVAL_LIMIT:,} - needs manager approval")
    return issues


def make_row(path: Path, inv: dict, method: str, issues: list[str], is_dup: bool = False) -> dict:
    status = "Duplicate" if is_dup else "Needs review" if issues else "OK"
    return {"file": path.name, **inv, "extracted_by": method, "status": status,
            "issues": "; ".join(issues), "processed_at": datetime.now()}


def process(path: Path, seen: set) -> dict:
    text = extractor.read_pdf_text(path)
    inv = extractor.parse_invoice(text) if text.strip() else dict.fromkeys(extractor.FIELDS)
    method, notes = "rules", []

    if any(inv.get(f) is None for f in REQUIRED) and ai.available():
        try:
            inv, method = extractor.ai_extract(path), "ai"
            if REVIEW_AI_EXTRACTIONS:
                notes.append("Read by AI - verify before paying")
        except ai.AIError as e:
            notes.append(f"AI extraction failed: {e}")

    if method != "ai" and not text.strip():
        return make_row(path, inv, "none", [*notes, ("No readable text (scanned image?) - needs AI "
                                                    "(add ANTHROPIC_API_KEY) or manual entry")])

    key = dup_key(inv)
    is_dup = key in seen
    if key and not is_dup:
        seen.add(key)
    return make_row(path, inv, method, validate(inv, is_dup) + notes, is_dup)


def load_register(engine) -> pd.DataFrame:
    if not db.table_exists(engine, TABLE):
        return pd.DataFrame(columns=["file", *extractor.FIELDS, "extracted_by", "status", "issues", "processed_at"])
    return pd.read_sql_table(TABLE, engine, parse_dates=[*DATE_COLS, "processed_at"])


def move_file(path: Path, folder: Path) -> Path:
    folder.mkdir(exist_ok=True)
    dest, n = folder / path.name, 1
    while dest.exists():  # never overwrite a file already filed
        dest = folder / f"{path.stem}_{n}{path.suffix}"
        n += 1
    return Path(shutil.move(path, dest))


def dates_only(df: pd.DataFrame) -> pd.DataFrame:
    """Show dates without a 00:00:00 time in Excel."""
    df = df.copy()
    for col in DATE_COLS:
        if col in df.columns:
            df[col] = df[col].dt.date
    return df


def payment_schedule(register: pd.DataFrame) -> pd.DataFrame:
    """Approved invoices by due date (assumes unpaid - payment tracking is a future upgrade)."""
    ok = register[register["status"] == "OK"].copy()
    ok["days_until_due"] = (ok["due_date"] - pd.Timestamp(date.today())).dt.days
    return ok.sort_values("due_date")[["due_date", "days_until_due", "vendor", "invoice_no", "total"]]


def write_register(register: pd.DataFrame, path: Path) -> Path:
    ok = register[register["status"] == "OK"]
    by_vendor = (ok.groupby("vendor").agg(invoices=("invoice_no", "size"), total=("total", "sum"))
                   .sort_values("total", ascending=False).reset_index())
    review = register[register["status"] != "OK"][["file", "vendor", "invoice_no", "total", "status", "issues"]]
    return write_sheets(path, {
        "Payment Schedule": dates_only(payment_schedule(register)),
        "Needs Review": review,
        "By Vendor": by_vendor,
        "All Invoices": dates_only(register.sort_values("processed_at", ascending=False)),
    })


def build_email(batch: pd.DataFrame, register: pd.DataFrame) -> tuple[str, str]:
    ok, review = batch[batch["status"] == "OK"], batch[batch["status"] != "OK"]
    schedule = payment_schedule(register)
    overdue = schedule[schedule["days_until_due"] < 0]
    due_soon = schedule[schedule["days_until_due"].between(0, 7)]

    notes = [
        f"{len(batch)} new invoice(s): {len(ok)} OK, {len(review)} need review",
        f"Value of new OK invoices: ${ok['total'].sum():,.2f}",
        f"Overdue: {len(overdue)} (${overdue['total'].sum():,.2f})",
        f"Due in the next 7 days: {len(due_soon)} (${due_soon['total'].sum():,.2f})",
    ]
    read_by_ai = int((batch["extracted_by"] == "ai").sum())
    if read_by_ai:
        notes.append(f"Read by AI (layouts the rules couldn't handle): {read_by_ai}")
    body = bullets(notes)
    if len(review):
        body += heading(f"Needs review ({len(review)})", RED)
        body += html_table(review[["file", "vendor", "invoice_no", "total", "issues"]], max_rows=10)
    if len(overdue):
        body += heading(f"Overdue ({len(overdue)})", AMBER) + html_table(overdue, max_rows=10)
    if len(due_soon):
        body += heading(f"Due in the next 7 days ({len(due_soon)})") + html_table(due_soon, max_rows=10)

    subject = f"Invoices processed - {date.today():%b %d, %Y}: {len(batch)} new, {len(review)} need review"
    note = "Payment dates assume invoices are unpaid. The full register is attached."
    return subject, page("Invoice Processing Summary", note, body)


def main(dry_run: bool) -> None:
    INBOX.mkdir(parents=True, exist_ok=True)
    files = sorted(INBOX.glob("*.pdf"))
    if not files:
        log.info("No new invoices in %s", INBOX)
        return

    engine = db.get_engine()
    register = load_register(engine)
    seen = {k for k in map(dup_key, register[register["status"] != "Duplicate"].to_dict("records")) if k}

    rows = []
    for path in files:
        try:
            row = process(path, seen)
        except Exception as e:  # a corrupt PDF goes to review instead of stopping the batch
            log.exception("Could not process %s", path.name)
            row = make_row(path, dict.fromkeys(extractor.FIELDS), "none", [f"Could not read PDF: {e}"])
        log.info("%-45s %-5s %-12s %s", path.name, row["extracted_by"], row["status"], row["issues"])
        rows.append(row)
    if ai.usage["requests"]:
        log.info("AI usage: %s", ai.usage_summary())

    batch = pd.DataFrame(rows)
    for col in DATE_COLS:
        batch[col] = pd.to_datetime(batch[col])

    if dry_run:
        out = write_register(batch, config.OUTPUT_DIR / f"{NAME}_dry_run.xlsx")
        _, html = build_email(batch, batch)
        preview = config.OUTPUT_DIR / f"{NAME}_preview.html"
        preview.write_text(html, encoding="utf-8")
        log.info("Dry run - nothing saved, moved or sent. Results: %s, preview: %s", out, preview)
        return

    db.add_missing_columns(engine, TABLE, batch)  # e.g. extracted_by, added after the first runs
    batch.to_sql(TABLE, engine, if_exists="append", index=False)
    for path, row in zip(files, rows):
        move_file(path, PROCESSED if row["status"] == "OK" else NEEDS_REVIEW)

    register = load_register(engine)
    report = write_register(register, REGISTER)
    subject, html = build_email(batch, register)
    log.info("Register updated: %s (%d invoices total)", report, len(register))

    recipients = config.get("REPORT_RECIPIENTS")
    if recipients:
        notify.send_email([r.strip() for r in recipients.split(",")], subject, html,
                          attachments=[report], html=True)
        log.info("Summary emailed to %s", recipients)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="check invoices without saving, moving or emailing")
    args = parser.parse_args()
    run_job(NAME, lambda: main(args.dry_run), alert_on_failure=True)
