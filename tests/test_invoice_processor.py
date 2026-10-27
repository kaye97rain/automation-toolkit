import random
from datetime import date

import pytest

from projects.invoice_processor import extractor, make_sample_invoices
from projects.invoice_processor.main import validate

CLASSIC = """TechSource Ltd
48 Circuit Ave
INVOICE
Invoice No: TS-1043
Invoice Date: 2026-10-02
Due Date: 2026-11-01
Description Qty Unit Price Amount
Wireless Mouse 4 $18.00 $72.00
Subtotal $72.00
Tax (8%) $5.76
Total $77.76"""

MODERN = """INVOICE
Bill From:
PaperWorks Co
Invoice # 88213
Date: Oct 05, 2026
Payment Due: Nov 04, 2026
Subtotal $1,200.00
Tax (8%) $96.00
Amount Due $1,296.00"""

SIMPLE = """CleanPro Distributors
Invoice Number: CP-2026-077
Issued: 10/07/2026
Terms: Net 30
Subtotal $50.00
Tax (8%) $4.00
TOTAL DUE $54.00"""


@pytest.mark.parametrize("text, expected", [
    (CLASSIC, {"vendor": "TechSource Ltd", "invoice_no": "TS-1043", "invoice_date": date(2026, 10, 2),
               "due_date": date(2026, 11, 1), "subtotal": 72.0, "tax": 5.76, "total": 77.76}),
    (MODERN, {"vendor": "PaperWorks Co", "invoice_no": "88213", "invoice_date": date(2026, 10, 5),
              "due_date": date(2026, 11, 4), "subtotal": 1200.0, "tax": 96.0, "total": 1296.0}),
    (SIMPLE, {"vendor": "CleanPro Distributors", "invoice_no": "CP-2026-077", "invoice_date": date(2026, 10, 7),
              "due_date": date(2026, 11, 6), "subtotal": 50.0, "tax": 4.0, "total": 54.0}),  # due from Net 30
])
def test_parse_invoice_layouts(text, expected):
    assert extractor.parse_invoice(text) == expected


def test_validate_flags_problems():
    good = extractor.parse_invoice(CLASSIC)
    assert validate(good, is_duplicate=False) == []

    wrong = {**good, "total": 100.0}
    assert "doesn't add up" in validate(wrong, False)[0]

    big = {**good, "subtotal": 20000.0, "tax": 0.0, "total": 20000.0}
    assert any("approval" in i for i in validate(big, False))

    assert validate(good, is_duplicate=True)[0].startswith("Duplicate")
    assert "Missing invoice no" in validate({**good, "invoice_no": None}, False)


def test_generated_pdf_round_trip(tmp_path):
    inv = make_sample_invoices.make_invoice(random.Random(1), "CleanPro Distributors", days_ago=10)
    path = tmp_path / "invoice.pdf"
    make_sample_invoices.draw(path, inv)

    parsed = extractor.parse_invoice(extractor.read_pdf_text(path))
    assert parsed["vendor"] == "CleanPro Distributors"
    assert parsed["invoice_no"] == inv["number"]
    assert parsed["invoice_date"] == inv["date"]
    assert parsed["due_date"] == inv["due"]
    assert parsed["total"] == inv["total"]
