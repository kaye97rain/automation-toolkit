"""Send results and alerts by email or Slack."""

import smtplib
from email.message import EmailMessage
from pathlib import Path

import requests

from core import config


def send_email(to: str | list[str], subject: str, body: str,
               attachments: list[Path] | None = None, html: bool = False) -> None:
    msg = EmailMessage()
    msg["From"] = config.get("EMAIL_FROM") or config.get("SMTP_USER", required=True)
    msg["To"] = ", ".join(to) if isinstance(to, list) else to
    msg["Subject"] = subject
    msg.set_content(body, subtype="html" if html else "plain")

    for path in attachments or []:
        msg.add_attachment(path.read_bytes(), maintype="application",
                           subtype="octet-stream", filename=path.name)

    with smtplib.SMTP(config.get("SMTP_HOST", required=True),
                      int(config.get("SMTP_PORT", "587"))) as smtp:
        smtp.starttls()
        smtp.login(config.get("SMTP_USER", required=True), config.get("SMTP_PASSWORD", required=True))
        smtp.send_message(msg)


def send_slack(text: str) -> None:
    """Post a message through a Slack incoming webhook."""
    url = config.get("SLACK_WEBHOOK_URL", required=True)
    requests.post(url, json={"text": text}, timeout=15).raise_for_status()
