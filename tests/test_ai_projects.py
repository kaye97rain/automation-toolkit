"""Tests for the AI features. The Claude API is replaced with fakes, so these run free and offline."""

import random
from datetime import date
from email import policy
from email.parser import BytesParser

from core import ai
from projects.email_triage import main as triage_main
from projects.email_triage import make_sample_emails
from projects.invoice_processor import extractor, make_sample_invoices
from projects.invoice_processor import main as invoice_main


def unusual_invoice(tmp_path):
    inv = make_sample_invoices.make_invoice(random.Random(2), "Harbor Courier Services", days_ago=8)
    path = tmp_path / "harbor.pdf"
    make_sample_invoices.draw(path, inv)
    return path, inv


def test_unusual_layout_defeats_the_pattern_rules(tmp_path):
    path, _ = unusual_invoice(tmp_path)
    parsed = extractor.parse_invoice(extractor.read_pdf_text(path))
    assert parsed["vendor"] == "Harbor Courier Services"
    assert parsed["invoice_no"] is None and parsed["invoice_date"] is None and parsed["total"] is None


def test_invoice_falls_back_to_ai(tmp_path, monkeypatch):
    path, inv = unusual_invoice(tmp_path)
    fake = {"vendor": inv["vendor"], "invoice_no": inv["number"], "invoice_date": inv["date"],
            "due_date": inv["due"], "subtotal": inv["subtotal"], "tax": inv["tax"], "total": inv["total"]}
    monkeypatch.setattr(ai, "available", lambda: True)
    monkeypatch.setattr(extractor, "ai_extract", lambda p: fake)

    row = invoice_main.process(path, seen=set())
    assert row["extracted_by"] == "ai"
    assert row["invoice_no"] == inv["number"]
    assert row["status"] == "Needs review" and "Read by AI" in row["issues"]


def test_scanned_invoice_without_ai_goes_to_manual_review(tmp_path, monkeypatch):
    path = tmp_path / "scan.pdf"
    make_sample_invoices.draw_scanned(path, make_sample_invoices.make_invoice(random.Random(3), "CleanPro Distributors", 5))
    monkeypatch.setattr(ai, "available", lambda: False)

    assert extractor.read_pdf_text(path).strip() == ""  # an image only: no text layer
    row = invoice_main.process(path, seen=set())
    assert row["extracted_by"] == "none" and "No readable text" in row["issues"]


def test_read_eml_and_draft_reply(tmp_path):
    path = make_sample_emails.generate(tmp_path)[0]
    email = triage_main.read_eml(path)
    assert email["from_email"] == "maria.lopez@brightpath.example"
    assert "AC-20931" in email["body"]

    t = triage_main.Triage(category="Account access", urgency="High", sentiment="Negative", language="English",
                           customer_name="Maria Lopez", references=["AC-20931"], summary="Team locked out.",
                           needs_human=False, reason="Whole team blocked", suggested_reply="Hi Maria, ...")
    row = triage_main.make_row(email, t)
    assert row["team"] == "IT Support"

    draft = BytesParser(policy=policy.default).parse(triage_main.write_draft(row, tmp_path / "drafts").open("rb"))
    assert draft["Subject"].startswith("Re: ")
    assert draft["X-Unsent"] == "1"


def test_every_category_has_a_route():
    categories = triage_main.Triage.model_fields["category"].annotation.__args__
    assert set(categories) == set(triage_main.ROUTES)


def test_ai_usage_cost_estimate():
    ai.usage.update(requests=2, input_tokens=1_000_000, output_tokens=100_000)
    assert "$6.000" in ai.usage_summary()  # 1M x $4 + 0.1M x $20
    ai.usage.update(requests=0, input_tokens=0, output_tokens=0)


def test_iso_date_parsing():
    assert extractor._iso_date("2026-10-05") == date(2026, 10, 5)
    assert extractor._iso_date("not a date") is None
