"""SMTP mailer for emailing checker PDF exports.

Config is env-var driven (no credentials are bundled) so any SMTP-speaking
provider works — SES, SendGrid, Postmark, Resend, or a corporate relay.
"""

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from html import escape


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


# Brand values mirrored from the dashboard's mail templates
# (dashboard-saas/services/web/src/lib/mail/provider.ts): inline styles on a
# table layout, the only structure every mail client renders the same way.
_FONT = "Inter,-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
_INK = "#21283b"
_MUTED = "#4b5563"
_QUIET = "#5b6472"
_BORDER = "#e5e7eb"
_PAGE = "#f4f5f7"


def _text_style(size: int, line: int, color: str, extra: str = "") -> str:
    return f"font-family:{_FONT};font-size:{size}px;line-height:{line}px;color:{color};{extra}"


def render_branded_html(
    *, heading: str, paragraphs: list[str], reason: str, note: str | None = None
) -> str:
    """The branded HTML body for a checker mail. All text is escaped."""
    body = "".join(
        f'<p style="margin:0 0 16px;{_text_style(15, 24, _MUTED)}">{escape(p)}</p>'
        for p in paragraphs
    )
    if note:
        body += (
            f'<p style="margin:24px 0 0;padding-top:20px;border-top:1px solid {_BORDER};'
            f'{_text_style(13, 20, _QUIET)}">{escape(note)}</p>'
        )
    wordmark = _text_style(20, 28, _INK, "font-weight:700;letter-spacing:-0.2px")
    title = _text_style(20, 28, _INK, "font-weight:600;letter-spacing:-0.2px")
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="color-scheme" content="light">'
        f"<title>{escape(heading)}</title></head>"
        f'<body style="margin:0;padding:0;background:{_PAGE}">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{_PAGE}">'
        '<tr><td align="center" style="padding:32px 16px">'
        # Outlook's Word engine ignores max-width: a fixed-width table for mso only.
        '<!--[if mso]><table role="presentation" width="520" align="center" '
        'cellpadding="0" cellspacing="0" border="0"><tr><td><![endif]-->'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:520px">'
        f'<tr><td style="padding:0 4px 20px"><span style="{wordmark}">OpenComplAI</span></td></tr>'
        f'<tr><td style="background:#ffffff;border:1px solid {_BORDER};border-radius:12px;padding:32px">'
        f'<h1 style="margin:0 0 12px;{title}">{escape(heading)}</h1>{body}'
        "</td></tr>"
        f'<tr><td align="center" style="padding:20px 8px 0;{_text_style(12, 18, _QUIET)}">'
        f"{escape(reason)}<br>OpenComplAI &middot; EU AI Act evidence, generated from your CI"
        "</td></tr></table>"
        "<!--[if mso]></td></tr></table><![endif]-->"
        "</td></tr></table></body></html>"
    )


def send_pdf_email(
    *,
    to_email: str,
    subject: str,
    body: str,
    pdf_bytes: bytes,
    pdf_filename: str = "eu-ai-act-checker-result.pdf",
    html_body: str | None = None,
) -> None:
    """Email `pdf_bytes` as an attachment to `to_email`.

    `body` is the plain-text part; `html_body`, when given, is sent alongside
    it as the HTML alternative (clients show whichever they support).

    Raises MailerNotConfiguredError if SMTP env vars are unset, or
    smtplib.SMTPException (or OSError) on a delivery failure.
    """
    config = _smtp_config()

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = str(config["from_address"])
    message["To"] = to_email
    message.set_content(body)
    if html_body is not None:
        message.add_alternative(html_body, subtype="html")
    message.add_attachment(
        pdf_bytes, maintype="application", subtype="pdf", filename=pdf_filename
    )

    with smtplib.SMTP(str(config["host"]), int(config["port"]), timeout=10) as smtp:
        if config["use_tls"]:
            smtp.starttls()
        if config["username"]:
            smtp.login(str(config["username"]), str(config["password"]))
        smtp.send_message(message)
