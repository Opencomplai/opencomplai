"""HTTP routes for the EU AI Act compliance checker."""

from __future__ import annotations

import os
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

from opencomplai_risk_engine.mailer import (
    MailerNotConfiguredError,
    render_branded_html,
    send_pdf_email,
)

router = APIRouter(prefix="/v1/checker", tags=["checker"])

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Trusted reverse-proxy hop count for X-Forwarded-For resolution (DOS-LIMITS).
# The docs-widget browser calls this service directly (see the CORS comment
# on _CheckerScopedCORSMiddleware in main.py) — there is no gateway-api in
# this path — but a deployment may still sit behind a reverse proxy/load
# balancer/CDN that appends to X-Forwarded-For. Defaults to 0 (trust nothing,
# use the immediate socket peer — request.client.host) so an unconfigured
# deployment can't have its rate limit trivially bypassed by a spoofed
# X-Forwarded-For header; an operator running behind N trusted proxies sets
# this to N so the resolver reads the Nth-from-the-right entry (the address
# each trusted hop actually observed), mirroring the standard
# trust-proxy-depth convention (e.g. nginx real_ip / Fastify trustProxy).
_TRUSTED_PROXY_HOPS = int(os.environ.get("OPENCOMPLAI_TRUSTED_PROXY_HOPS", "0"))


def _resolve_client_ip(request: Request) -> str:
    """Best-effort client identity for per-IP rate limiting.

    With no trusted proxies configured, this is the immediate socket peer —
    safe by default since X-Forwarded-For is otherwise fully client-supplied
    and trivially spoofed to defeat the limiter. With N trusted hops
    configured, reads the Nth-from-the-right entry in X-Forwarded-For (the
    address the outermost trusted proxy actually observed); falls back to the
    socket peer if the header has fewer entries than configured hops.
    """
    if _TRUSTED_PROXY_HOPS > 0:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            hops = [h.strip() for h in forwarded.split(",") if h.strip()]
            if len(hops) >= _TRUSTED_PROXY_HOPS:
                return hops[-_TRUSTED_PROXY_HOPS]
    return request.client.host if request.client else "unknown"


class _RateLimiter:
    """Shared-store, fixed-window per-key rate limiter (DOS-LIMITS).

    In-process/single-instance by design — risk-engine holds no other state
    of its own since PERSIST-RISK moved everything durable to evidence-vault,
    and this is a baseline abuse guard, not the primary control (edge/WAF
    rate limiting is expected in front of a production deployment). A single
    module-level store shared across all three checker routes (previously
    /email had its own private dict) so a caller can't dodge one endpoint's
    limit by hitting another.
    """

    def __init__(self, window_seconds: int, max_requests: int) -> None:
        self._window_seconds = window_seconds
        self._max_requests = max_requests
        self._hits: dict[str, list[float]] = {}

    def check(self, key: str) -> bool:
        now = time.time()
        hits = self._hits.setdefault(key, [])
        cutoff = now - self._window_seconds
        while hits and hits[0] < cutoff:
            hits.pop(0)
        if len(hits) >= self._max_requests:
            return False
        hits.append(now)
        return True

    def clear(self) -> None:
        self._hits.clear()


# Anonymous, unauthenticated checker endpoints reachable directly from the
# public docs widget — each gets its own budget so a burst against one
# (e.g. cheap /evaluate) doesn't consume another's (e.g. PDF-rendering
# /export). /email keeps its original, stricter budget since it also drives
# outbound SMTP sends, not just local computation.
_EMAIL_RATE_LIMITER = _RateLimiter(window_seconds=3600, max_requests=5)
_EXPORT_RATE_LIMITER = _RateLimiter(window_seconds=3600, max_requests=30)
_EVALUATE_RATE_LIMITER = _RateLimiter(window_seconds=3600, max_requests=60)


def _is_valid_email(value: str) -> bool:
    return bool(_EMAIL_RE.match(value)) and len(value) <= 254


def _rate_limited_response() -> HTTPException:
    return HTTPException(
        status_code=429,
        detail={
            "error_code": "RATE_LIMITED",
            "message": "Too many requests from this address — try again later.",
            "category": "client",
            "retryable": True,
        },
    )


# The real question catalog has ~20 entries (data/questions.json); this caps
# well above that for headroom while still bounding the O(answers) rendering
# work in render_pdf/render_markdown on an unauthenticated endpoint.
_MAX_ANSWERS = 100


class EvaluateRequest(BaseModel):
    answers: dict[str, Any] = Field(default_factory=dict, max_length=_MAX_ANSWERS)


class ExportRequest(BaseModel):
    answers: dict[str, Any] = Field(default_factory=dict, max_length=_MAX_ANSWERS)
    format: Literal["json", "md", "pdf"] = "json"


class EmailRequest(BaseModel):
    answers: dict[str, Any] = Field(default_factory=dict, max_length=_MAX_ANSWERS)
    to_email: str


@router.post("/evaluate")
def checker_evaluate(body: EvaluateRequest, request: Request) -> dict[str, Any]:
    """Evaluate checker answers and return a ComplianceCheckerResult dict.

    Anonymous and unauthenticated (called from the public docs widget), so
    this carries the same baseline per-IP rate limit as /export and /email.
    """
    if not _EVALUATE_RATE_LIMITER.check(_resolve_client_ip(request)):
        raise _rate_limited_response()
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
def checker_export(body: ExportRequest, request: Request) -> Response:
    """Export checker result as JSON, Markdown, or PDF bytes.

    Anonymous and unauthenticated (called from the public docs widget), so
    this carries the same baseline per-IP rate limit as /evaluate and /email
    — PDF rendering in particular is the most expensive of the three formats.
    """
    if not _EXPORT_RATE_LIMITER.check(_resolve_client_ip(request)):
        raise _rate_limited_response()
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
    if not _EMAIL_RATE_LIMITER.check(_resolve_client_ip(request)):
        raise _rate_limited_response()
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
        reason = (
            "You received this because this address was entered in the "
            "OpenComplAI EU AI Act checker."
        )
        send_pdf_email(
            to_email=body.to_email,
            subject="Your EU AI Act Checker result",
            body=(
                "Attached is a PDF copy of your EU AI Act Checker result, "
                "including the answers you gave. This is not legal advice — "
                "see the disclaimer in the attached PDF.\n\n"
                f"--\n{reason}\n"
                "OpenComplAI - EU AI Act evidence, generated from your CI"
            ),
            html_body=render_branded_html(
                heading="Your EU AI Act Checker result",
                paragraphs=[
                    "Attached is a PDF copy of your EU AI Act Checker result, "
                    "including the answers you gave."
                ],
                note=(
                    "This is not legal advice. See the disclaimer in the attached PDF."
                ),
                reason=reason,
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
