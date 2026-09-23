"""The checker's result mail: branded HTML alongside the plain text, PDF attached."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from opencomplai_risk_engine import mailer


def test_render_branded_html_escapes_every_value() -> None:
    html = mailer.render_branded_html(
        heading="<b>Result</b>",
        paragraphs=['Hi <script>alert("x")</script>'],
        note="a & b",
        reason="because <i>",
    )
    assert html.startswith("<!DOCTYPE html>")
    assert "<script>" not in html
    assert "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;" in html
    assert "&lt;b&gt;Result&lt;/b&gt;" in html
    assert "a &amp; b" in html
    assert "because &lt;i&gt;" in html
    assert ">OpenComplAI</span>" in html


@pytest.fixture
def smtp_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENCOMPLAI_SMTP_HOST", "smtp.test")
    monkeypatch.setenv("OPENCOMPLAI_SMTP_USE_TLS", "false")


def _sent_message(send_kwargs: dict) -> object:
    smtp = MagicMock()
    with patch.object(mailer.smtplib, "SMTP") as smtp_cls:
        smtp_cls.return_value.__enter__.return_value = smtp
        mailer.send_pdf_email(**send_kwargs)
    return smtp.send_message.call_args.args[0]


def test_send_pdf_email_carries_text_html_and_the_pdf(smtp_env: None) -> None:
    message = _sent_message(
        {
            "to_email": "a@b.test",
            "subject": "Your result",
            "body": "Plain body",
            "html_body": mailer.render_branded_html(
                heading="Your result", paragraphs=["Branded body"], reason="why"
            ),
            "pdf_bytes": b"%PDF-1.4 fixture",
        }
    )
    assert message.get_content_type() == "multipart/mixed"
    assert (
        message.get_body(preferencelist=("plain",)).get_content().strip()
        == "Plain body"
    )
    assert "Branded body" in message.get_body(preferencelist=("html",)).get_content()
    attachments = list(message.iter_attachments())
    assert [a.get_filename() for a in attachments] == ["eu-ai-act-checker-result.pdf"]
    assert attachments[0].get_content() == b"%PDF-1.4 fixture"


def test_send_pdf_email_without_html_stays_plain(smtp_env: None) -> None:
    message = _sent_message(
        {
            "to_email": "a@b.test",
            "subject": "Your result",
            "body": "Plain body",
            "pdf_bytes": b"%PDF-1.4 fixture",
        }
    )
    assert message.get_body(preferencelist=("html",)) is None
    assert (
        message.get_body(preferencelist=("plain",)).get_content().strip()
        == "Plain body"
    )
