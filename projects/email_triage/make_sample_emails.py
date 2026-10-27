"""Generate realistic mock customer emails (.eml) in data/input/emails/ to try the triage on.

    python -m projects.email_triage.make_sample_emails

.eml is the standard email file format - Outlook, Gmail and Thunderbird can all save emails as .eml.
"""

from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from email.utils import format_datetime, make_msgid
from pathlib import Path

from core import config

INBOX = config.INPUT_DIR / "emails"
TO = "Acme Support <support@acme-ops.example>"

# (sender name, sender address, subject, body, hours ago)
EMAILS = [
    ("Maria Lopez", "maria.lopez@brightpath.example", "URGENT: whole team locked out of the portal",
     ("Hi,\n\nSince 8am none of our 14 staff can log in to the ordering portal - it says 'account suspended'. "
     "Our account number is AC-20931. We have a big order to place today before your 2pm cutoff.\n\n"
     "Please fix this ASAP.\n\nMaria Lopez\nOffice Manager, BrightPath Dental"), 1),
    ("Tom Becker", "t.becker@northfield-legal.example", "Refund for order ORD-55821 - damaged chairs",
     ("Hello,\n\nTwo of the four ergonomic chairs from order ORD-55821 arrived with cracked bases. "
     "I'd like a refund for those two ($370 each, $740 total). Photos attached.\n\n"
     "Thanks,\nTom Becker"), 5),
    ("Priya Nair", "priya@lumenstudio.example", "Charged twice for invoice INV-2026-0412?",
     ("Hi there,\n\nOur card statement shows two charges of $1,284.60 on Oct 20 for invoice INV-2026-0412. "
     "Could you check whether we were double charged and refund the duplicate?\n\nBest,\nPriya Nair\n"
     "Finance, Lumen Studio"), 20),
    ("Daniel Okafor", "dokafor@vertexcoworking.example", "Pricing for 200 standing desks",
     ("Good morning,\n\nWe're opening two new coworking floors in January and need around 200 standing desks "
     "plus chairs. Do you offer volume pricing, and what lead time should we expect?\n\nRegards,\n"
     "Daniel Okafor\nOperations Director, Vertex Coworking"), 26),
    ("Linda Park", "linda.park@crestview-realty.example", "THIRD time asking - where is my delivery??",
     ("This is the third email I've sent about order ORD-55102. It was due on the 14th. Nobody has replied. "
     "We have new hires starting Monday with no desks.\n\nIf I don't hear back today we will cancel our "
     "contract and leave reviews about this experience.\n\nLinda Park"), 3),
    ("Carlos Ruiz", "cruiz@ferreteria-ruiz.example", "Problema con mi factura",
     ("Hola,\n\nRecibí la factura INV-2026-0388 pero el monto no coincide con la cotización que me enviaron "
     "(cotizaron $820 y la factura dice $910). ¿Me pueden ayudar a revisarlo?\n\nGracias,\nCarlos Ruiz"), 30),
    ("Prize Center", "winner@claim-your-reward.example", "Congratulations! You've won a $1,000 gift card",
     ("Dear valued customer,\n\nYou have been selected to receive a $1,000 gift card! Click the link below "
     "and enter your login details within 24 hours to claim it.\n\nhttp://claim-your-reward.example/win"), 8),
    ("Sarah Kim", "sarah.kim@oakleaf-accounting.example", "Thank you!",
     ("Hi,\n\nJust wanted to say thanks to Jake on your support team - he sorted out our delivery address "
     "mix-up in five minutes and followed up the next day. Great service!\n\nSarah"), 48),
    ("TechSource Ltd Accounts", "accounts@techsource.example", "Invoice TS-48211 - due Nov 26",
     ("Dear Acme Operations,\n\nPlease find attached invoice TS-48211 for $2,630.88 covering the October "
     "monitor and headset order. Payment is due by November 26, 2026.\n\nKind regards,\n"
     "Accounts Receivable, TechSource Ltd"), 12),
    ("Ahmed Hassan", "ahmed.h@greenline-logistics.example", "Password reset link not working",
     ("Hello,\n\nI requested a password reset three times but the link in the email says 'expired' "
     "every time I click it. My username is ahassan. Can you help?\n\nThanks,\nAhmed"), 6),
    ("Grace Liu", "gliu@liu-partners-law.example", "Notice regarding breach of supply agreement",
     ("To whom it may concern,\n\nWe represent Harmon Interiors LLC regarding repeated failures to deliver "
     "under the supply agreement dated March 3, 2026. Please direct this letter to your legal department "
     "and respond within 10 business days.\n\nGrace Liu\nLiu & Partners"), 4),
    ("Ben Carter", "ben@carter-design.example", "Do you integrate with QuickBooks?",
     ("Hey team,\n\nQuick question - can your ordering portal sync invoices to QuickBooks Online? "
     "That would save our bookkeeper a lot of time.\n\nCheers,\nBen"), 52),
]


def generate(folder: Path = INBOX) -> list[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC)
    paths = []
    for i, (name, address, subject, body, hours_ago) in enumerate(EMAILS, start=1):
        msg = EmailMessage()
        msg["From"] = f"{name} <{address}>"
        msg["To"] = TO
        msg["Subject"] = subject
        msg["Date"] = format_datetime(now - timedelta(hours=hours_ago))
        msg["Message-ID"] = make_msgid(domain=address.split("@")[1])
        msg.set_content(body)
        path = folder / f"{i:02d}_{address.split('@')[0].replace('.', '_')}.eml"
        path.write_bytes(msg.as_bytes())
        paths.append(path)
    return paths


if __name__ == "__main__":
    created = generate()
    print(f"Created {len(created)} emails in {INBOX}")
