"""SMTP mailer for emailing checker PDF exports.

Config is env-var driven (no credentials are bundled) so any SMTP-speaking
provider works — SES, SendGrid, Postmark, Resend, or a corporate relay.
"""

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage


class MailerNotConfiguredError(RuntimeError):
    """Raised when OPENCOMPLAI_SMTP_HOST is unset — no attempt to send is made."""


def _truthy(value: str) -> bool:
    return value.strip().lower() not in ("0", "false", "no", "")


def _smtp_config() -> dict[str, str | int | bool]:
    host = os.environ.get("OPENCOMPLAI_SMTP_HOST", "")
    if not host:
        msg = (
            "Email delivery is not configured on this server — set "
            "OPENCOMPLAI_SMTP_HOST (and related OPENCOMPLAI_SMTP_* env vars) to enable it."
        )
        raise MailerNotConfiguredError(msg)
    return {
        "host": host,
        "port": int(os.environ.get("OPENCOMPLAI_SMTP_PORT", "587")),
        "username": os.environ.get("OPENCOMPLAI_SMTP_USERNAME", ""),
        "password": os.environ.get("OPENCOMPLAI_SMTP_PASSWORD", ""),
        "from_address": os.environ.get(
            "OPENCOMPLAI_SMTP_FROM_ADDRESS", "noreply@opencomplai.com"
        ),
        "use_tls": _truthy(os.environ.get("OPENCOMPLAI_SMTP_USE_TLS", "true")),
    }


def send_pdf_email(
    *,
    to_email: str,
    subject: str,
    body: str,
    pdf_bytes: bytes,
    pdf_filename: str = "eu-ai-act-checker-result.pdf",
) -> None:
    """Email `pdf_bytes` as an attachment to `to_email`.

    Raises MailerNotConfiguredError if SMTP env vars are unset, or
    smtplib.SMTPException (or OSError) on a delivery failure.
    """
    config = _smtp_config()

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = str(config["from_address"])
    message["To"] = to_email
    message.set_content(body)
    message.add_attachment(
        pdf_bytes, maintype="application", subtype="pdf", filename=pdf_filename
    )

    with smtplib.SMTP(str(config["host"]), int(config["port"]), timeout=10) as smtp:
        if config["use_tls"]:
            smtp.starttls()
        if config["username"]:
            smtp.login(str(config["username"]), str(config["password"]))
        smtp.send_message(message)
