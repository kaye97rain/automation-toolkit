"""Generate mock PDF invoices in data/input/invoices/ to try the invoice processor on.

    python -m projects.invoice_processor.make_sample_invoices

Six vendors using four different layouts, plus deliberate problems to catch:
a duplicate, a total that doesn't add up, one over the approval limit, a vendor whose wording
the pattern rules don't know, and a scanned (image-only) invoice. The last two need the AI fallback.
Invoice numbers are random, so you can generate a fresh batch any time.
"""

import random
from datetime import date, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from core import config

INBOX = config.INPUT_DIR / "invoices"
TODAY = date.today()
TAX_RATE = 0.08
CUSTOMER = ["Bill To:", "Acme Operations Inc.", "200 Commerce Way, Suite 4"]

VENDORS = {
    "TechSource Ltd": {"layout": "classic", "prefix": "TS-", "address": "48 Circuit Ave, Tech Park",
                       "items": {"USB-C Cable": 6.50, "Wireless Mouse": 18.00, "27in Monitor": 210.00,
                                 "Noise-Cancelling Headset": 120.00}},
    "PaperWorks Co": {"layout": "modern", "prefix": "", "address": "9 Mill Road, Riverside",
                      "items": {"Printer Paper (Ream)": 4.80, "Ballpoint Pens (Box of 12)": 3.20,
                                "File Folders (Box)": 11.00, "Sticky Notes (Pack)": 2.90}},
    "CleanPro Distributors": {"layout": "simple", "prefix": "CP-2026-", "address": "Unit 3, Harbor Industrial Estate",
                              "items": {"Hand Sanitizer 500ml": 3.50, "Disinfectant Wipes": 4.20,
                                        "Paper Towels (6 Rolls)": 7.80, "Trash Bags (50ct)": 9.00}},
    "Workspace Interiors": {"layout": "classic", "prefix": "WI-", "address": "120 Design District Blvd",
                            "items": {"Ergonomic Chair": 185.00, "Standing Desk": 340.00, "Filing Cabinet": 150.00}},
    "Daily Grind Foods": {"layout": "modern", "prefix": "DG-", "address": "77 Roastery Lane",
                          "items": {"Coffee Beans 1kg": 16.00, "Paper Cups (100ct)": 5.50, "Tea Assortment": 8.00}},
    "Harbor Courier Services": {"layout": "unusual", "prefix": "HC/", "address": "Pier 12, Harbor Road",
                                "items": {"Same-day courier (zone 2)": 45.00, "Document pouch delivery": 12.00,
                                          "Pallet freight (per pallet)": 180.00}},
}


def ordinal(n: int) -> str:
    return f"{n}{'th' if 11 <= n % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def money(v: float) -> str:
    return f"${v:,.2f}"


def make_invoice(rng: random.Random, vendor: str, days_ago: int, qty: tuple[int, int] = (2, 12)) -> dict:
    v = VENDORS[vendor]
    chosen = rng.sample(list(v["items"].items()), rng.randint(2, min(4, len(v["items"]))))
    items = [(name, rng.randint(*qty), price) for name, price in chosen]
    subtotal = round(sum(q * p for _, q, p in items), 2)
    tax = round(subtotal * TAX_RATE, 2)
    invoice_date = TODAY - timedelta(days=days_ago)
    return {"vendor": vendor, "number": f"{v['prefix']}{rng.randint(1000, 99999)}", "date": invoice_date,
            "due": invoice_date + timedelta(days=30), "items": items,
            "subtotal": subtotal, "tax": tax, "total": round(subtotal + tax, 2)}


def draw(path: Path, inv: dict) -> None:
    v = VENDORS[inv["vendor"]]
    c = canvas.Canvas(str(path), pagesize=LETTER)
    y = LETTER[1] - 60

    def line(text: str, size: int = 10, bold: bool = False, gap: int = 16) -> None:
        nonlocal y
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        c.drawString(50, y, text)
        y -= gap

    subtotal_label, tax_label = "Subtotal", f"Tax ({TAX_RATE:.0%})"
    if v["layout"] == "classic":
        line(inv["vendor"], 20, True, 18)
        line(v["address"], 9, gap=34)
        line("INVOICE", 16, True, 24)
        line(f"Invoice No: {inv['number']}")
        line(f"Invoice Date: {inv['date']:%Y-%m-%d}")
        line(f"Due Date: {inv['due']:%Y-%m-%d}", gap=28)
        total_label = "Total"
    elif v["layout"] == "modern":
        line("INVOICE", 24, True, 30)
        line("Bill From:", 9, gap=14)
        line(inv["vendor"], 13, True, 14)
        line(v["address"], 9, gap=26)
        line(f"Invoice # {inv['number']}")
        line(f"Date: {inv['date']:%b %d, %Y}")
        line(f"Payment Due: {inv['due']:%b %d, %Y}", gap=28)
        total_label = "Amount Due"
    elif v["layout"] == "unusual":  # wording the pattern rules don't recognize
        line(inv["vendor"], 16, True, 16)
        line(v["address"], 9, gap=30)
        line("STATEMENT OF CHARGES", 14, True, 22)
        line(f"Document Ref.  {inv['number']}")
        line(f"Billing date: {ordinal(inv['date'].day)} of {inv['date']:%B %Y}")
        line(f"Please remit by {inv['due']:%d %B %Y}", gap=28)
        subtotal_label, tax_label, total_label = "Charges before tax", f"Sales tax {TAX_RATE:.0%}", "Grand sum payable"
    else:  # simple: no due date, only payment terms
        line(inv["vendor"], 14, True, 14)
        line(v["address"], 9, gap=26)
        line(f"Invoice Number: {inv['number']}")
        line(f"Issued: {inv['date']:%m/%d/%Y}")
        line("Terms: Net 30", gap=28)
        total_label = "TOTAL DUE"

    for i, text in enumerate(CUSTOMER):
        line(text, 10, i == 0, 14)
    y -= 20

    c.setFont("Helvetica-Bold", 10)
    for x, label in ((50, "Description"), (330, "Qty"), (400, "Unit Price"), (500, "Amount")):
        c.drawString(x, y, label)
    c.line(50, y - 5, 562, y - 5)
    y -= 22
    c.setFont("Helvetica", 10)
    for name, qty, price in inv["items"]:
        for x, text in ((50, name), (330, str(qty)), (400, money(price)), (500, money(qty * price))):
            c.drawString(x, y, text)
        y -= 16
    c.line(50, y + 6, 562, y + 6)
    y -= 14

    for label, value, bold in ((subtotal_label, inv["subtotal"], False),
                               (tax_label, inv["tax"], False),
                               (total_label, inv["total"], True)):
        c.setFont("Helvetica-Bold" if bold else "Helvetica", 11 if bold else 10)
        c.drawString(360, y, label)
        c.drawRightString(562, y, money(value))
        y -= 18

    c.setFont("Helvetica-Oblique", 8)
    c.drawString(50, 50, "Thank you for your business.")
    c.save()


def draw_scanned(path: Path, inv: dict) -> None:
    """An invoice that was printed and scanned: a slightly tilted, blurry image with no text layer.
    PDF text extraction finds nothing - only AI (vision) can read it."""
    w, h = 1275, 1650  # letter size at 150 dpi
    img = Image.new("L", (w, h), 248)
    d = ImageDraw.Draw(img)
    big, normal = ImageFont.load_default(size=44), ImageFont.load_default(size=26)
    y = 100

    def text(s: str, font=normal, gap: int = 40, x: int = 110) -> None:
        nonlocal y
        d.text((x, y), s, fill=35, font=font)
        y += gap

    text(inv["vendor"], big, 60)
    text(VENDORS[inv["vendor"]]["address"], gap=80)
    text(f"INVOICE   {inv['number']}", big, 64)
    text(f"Date: {inv['date']:%d %b %Y}")
    text(f"Due:  {inv['due']:%d %b %Y}", gap=70)
    for name, qty, price in inv["items"]:
        d.text((950, y), money(qty * price), fill=35, font=normal)
        text(f"{qty} x {name} @ {money(price)}")
    y += 30
    for label, value in (("Subtotal", inv["subtotal"]), ("Tax 8%", inv["tax"]), ("TOTAL", inv["total"])):
        d.text((950, y), money(value), fill=35, font=normal)
        text(label, x=700)

    img = img.rotate(0.8, fillcolor=248).filter(ImageFilter.GaussianBlur(0.7))
    rng = random.Random(3)
    for _ in range(2500):  # scanner speckles
        img.putpixel((rng.randrange(w), rng.randrange(h)), rng.randint(110, 200))

    c = canvas.Canvas(str(path), pagesize=LETTER)
    c.drawImage(ImageReader(img), 0, 0, width=LETTER[0], height=LETTER[1])
    c.save()


def slug(text: str) -> str:
    return text.lower().replace(" ", "_")


def generate() -> list[Path]:
    rng = random.Random()
    INBOX.mkdir(parents=True, exist_ok=True)
    regular = [("TechSource Ltd", 40), ("TechSource Ltd", 12), ("PaperWorks Co", 33), ("PaperWorks Co", 5),
               ("CleanPro Distributors", 26), ("CleanPro Distributors", 9), ("Workspace Interiors", 18),
               ("Daily Grind Foods", 35), ("Daily Grind Foods", 24), ("Daily Grind Foods", 2)]
    invoices = [make_invoice(rng, vendor, days) for vendor, days in regular]

    wrong_total = make_invoice(rng, "PaperWorks Co", 15)
    wrong_total["total"] = round(wrong_total["total"] + 50, 2)  # vendor's math is off by $50
    big_order = make_invoice(rng, "Workspace Interiors", 6, qty=(35, 50))  # over the approval limit
    unusual = make_invoice(rng, "Harbor Courier Services", 8, qty=(1, 6))  # needs the AI fallback
    invoices += [wrong_total, big_order, unusual]

    paths = []
    for inv in invoices:
        path = INBOX / f"{slug(inv['vendor'])}_{inv['number'].replace('/', '-')}.pdf"
        draw(path, inv)
        paths.append(path)

    resent = invoices[1]  # vendor emailed the same invoice twice
    paths.append(INBOX / f"{slug(resent['vendor'])}_{resent['number']}_resent.pdf")
    draw(paths[-1], resent)

    paths.append(INBOX / f"scan_{TODAY:%Y%m%d}_0007.pdf")
    draw_scanned(paths[-1], make_invoice(rng, "CleanPro Distributors", 20))
    return paths


if __name__ == "__main__":
    created = generate()
    print(f"Created {len(created)} invoices in {INBOX}")
