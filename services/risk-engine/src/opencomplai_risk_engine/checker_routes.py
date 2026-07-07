"""HTTP routes for the EU AI Act compliance checker."""

from __future__ import annotations

import re
import smtplib
import time
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request, Response
from opencomplai_core.compliance_checker import (
    CHECKER_VERSION,
    CheckerSession,
    evaluate,
    render_json,
    render_markdown,
    render_pdf,
)
from opencomplai_core.compliance_checker.catalog import load_help_content
from pydantic import BaseModel, Field

from opencomplai_risk_engine.mailer import MailerNotConfiguredError, send_pdf_email

router = APIRouter(prefix="/v1/checker", tags=["checker"])

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Minimal in-memory per-IP rate limit for the anonymous, unauthenticated
# email endpoint. Single-process/fixed-window — adequate as a baseline abuse
# guard, not a substitute for edge/WAF rate limiting in front of this service.
_EMAIL_RATE_LIMIT_WINDOW_SECONDS = 3600
_EMAIL_RATE_LIMIT_MAX_REQUESTS = 5
_email_rate_limit_hits: dict[str, list[float]] = {}


def _is_valid_email(value: str) -> bool:
    return bool(_EMAIL_RE.match(value)) and len(value) <= 254


def _check_email_rate_limit(client_ip: str) -> bool:
    now = time.time()
    hits = _email_rate_limit_hits.setdefault(client_ip, [])
    cutoff = now - _EMAIL_RATE_LIMIT_WINDOW_SECONDS
    while hits and hits[0] < cutoff:
        hits.pop(0)
    if len(hits) >= _EMAIL_RATE_LIMIT_MAX_REQUESTS:
        return False
    hits.append(now)
    return True


class EvaluateRequest(BaseModel):
    answers: dict[str, Any] = Field(default_factory=dict)


class ExportRequest(BaseModel):
    answers: dict[str, Any] = Field(default_factory=dict)
    format: Literal["json", "md", "pdf"] = "json"


class EmailRequest(BaseModel):
    answers: dict[str, Any] = Field(default_factory=dict)
    to_email: str


@router.post("/evaluate")
def checker_evaluate(body: EvaluateRequest) -> dict[str, Any]:
    """Evaluate checker answers and return a ComplianceCheckerResult dict."""
    session = CheckerSession(answers=body.answers)
    result = evaluate(session)
    result.answers = dict(body.answers)
    return result.model_dump(mode="json")


@router.get("/help")
def checker_help() -> dict[str, Any]:
    """Return educational help content for the checker UI."""
    content = load_help_content()
    return {
        "checker_version": CHECKER_VERSION,
        "sections": content,
        "disclaimer": content.get("disclaimer", {}).get("body", ""),
    }


@router.post("/export")
def checker_export(body: ExportRequest) -> Response:
    """Export checker result as JSON, Markdown, or PDF bytes."""
    session = CheckerSession(answers=body.answers)
    result = evaluate(session)
    result.answers = dict(body.answers)

    if body.format == "json":
        return Response(
            content=render_json(result),
            media_type="application/json",
        )
    if body.format == "md":
        return Response(
            content=render_markdown(result),
            media_type="text/markdown; charset=utf-8",
        )
    try:
        pdf_bytes = render_pdf(result)
    except ImportError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    return Response(content=pdf_bytes, media_type="application/pdf")


@router.post("/email")
def checker_email(body: EmailRequest, request: Request) -> dict[str, Any]:
    """Evaluate checker answers, render a PDF, and email it to the caller.

    Anonymous and unauthenticated (called from the public docs widget), so
    this re-evaluates server-side rather than trusting a client-supplied
    result, and applies a baseline per-IP rate limit and email validation.
    """
    client_ip = request.client.host if request.client else "unknown"
    if not _check_email_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail={
                "error_code": "RATE_LIMITED",
                "message": "Too many email requests from this address — try again later.",
                "category": "client",
                "retryable": True,
            },
        )
    if not _is_valid_email(body.to_email):
        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "VALIDATION_ERROR",
                "message": "to_email is not a valid email address",
                "category": "client",
                "retryable": False,
            },
        )

    session = CheckerSession(answers=body.answers)
    result = evaluate(session)
    result.answers = dict(body.answers)

    try:
        pdf_bytes = render_pdf(result)
    except ImportError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc

    try:
        send_pdf_email(
            to_email=body.to_email,
            subject="Your EU AI Act Checker result",
            body=(
                "Attached is a PDF copy of your EU AI Act Checker result, "
                "including the answers you gave. This is not legal advice — "
                "see the disclaimer in the attached PDF."
            ),
            pdf_bytes=pdf_bytes,
        )
    except MailerNotConfiguredError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "error_code": "MAILER_NOT_CONFIGURED",
                "message": str(exc),
                "category": "server",
                "retryable": False,
            },
        ) from exc
    except (smtplib.SMTPException, OSError) as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "error_code": "EMAIL_DELIVERY_FAILED",
                "message": "Could not send the email — try downloading the PDF instead.",
                "category": "server",
                "retryable": True,
            },
        ) from exc

    return {"sent": True}
