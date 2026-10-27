"""Pull invoice fields out of PDF text using label patterns that cover common layouts.

Vendors label the same thing differently ("Invoice No", "Invoice #", "Invoice Number";
"Total", "Amount Due", "TOTAL DUE"), so each field has a pattern with the usual variants.
"""

import re
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pdfplumber

FIELDS = ["vendor", "invoice_no", "invoice_date", "due_date", "subtotal", "tax", "total"]

DATE = r"(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4}|[A-Za-z]{3,9}\.? \d{1,2},? \d{4}|\d{1,2} [A-Za-z]{3,9},? \d{4})"
MONEY = r"-?[\d,]*\d\.\d{2}"

NOT_VENDOR = re.compile(r"^((tax\s+)?invoice|bill\s+from:?|from:?)$", re.IGNORECASE)
INVOICE_NO = re.compile(r"invoice\s*(?:no\.?|number|num\.?|#)\s*[:#]?\s*([A-Z0-9][A-Z0-9\-/]*)", re.IGNORECASE)
# "date" not preceded by "due" so "Due Date" isn't taken as the invoice date
INVOICE_DATE = re.compile(r"(?<!due )\b(?:invoice date|date issued|issue date|issued|date)\s*:?\s*" + DATE, re.IGNORECASE)
DUE_DATE = re.compile(r"\b(?:due date|payment due|due by|due)\s*:?\s*" + DATE, re.IGNORECASE)
TERMS = re.compile(r"\bnet\s*(\d{1,3})\b", re.IGNORECASE)

SUBTOTAL = r"\bsub\s*-?\s*total\b"
TAX = r"\b(?:tax|vat|gst)\b"
TOTALS = [r"\b(?:amount|total|balance)\s+due\b", r"\bgrand\s+total\b", r"(?<!sub )(?<!sub-)\btotal\b"]


def read_pdf_text(path: Path) -> str:
    with pdfplumber.open(path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def parse_date(match: re.Match | None) -> date | None:
    if not match:
        return None
    try:
        return pd.to_datetime(match.group(1), format="mixed").date()
    except (ValueError, OverflowError):
        return None


def amount_on_line(text: str, label: str, last: bool = False) -> float | None:
    """The last money value on the first (or last) line containing `label`."""
    lines = [ln for ln in text.splitlines() if re.search(label, ln, re.IGNORECASE)]
    for line in reversed(lines) if last else lines:
        values = re.findall(MONEY, line)
        if values:
            return float(values[-1].replace(",", ""))
    return None


def parse_invoice(text: str) -> dict:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    number = INVOICE_NO.search(text)
    invoice_date = parse_date(INVOICE_DATE.search(text))
    due_date = parse_date(DUE_DATE.search(text))

    terms = TERMS.search(text)
    if due_date is None and invoice_date and terms:
        due_date = invoice_date + timedelta(days=int(terms.group(1)))  # "Net 30" = due 30 days after

    total = None
    for label in TOTALS:  # most specific label first; totals sit at the bottom, so take the last line
        total = amount_on_line(text, label, last=True)
        if total is not None:
            break

    return {
        "vendor": next((ln for ln in lines if not NOT_VENDOR.match(ln)), None),
        "invoice_no": number.group(1) if number else None,
        "invoice_date": invoice_date,
        "due_date": due_date,
        "subtotal": amount_on_line(text, SUBTOTAL),
        "tax": amount_on_line(text, TAX),
        "total": total,
    }
