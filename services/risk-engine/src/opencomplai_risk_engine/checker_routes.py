"""HTTP routes for the EU AI Act compliance checker."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Response
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

router = APIRouter(prefix="/v1/checker", tags=["checker"])


class EvaluateRequest(BaseModel):
    answers: dict[str, Any] = Field(default_factory=dict)


class ExportRequest(BaseModel):
    answers: dict[str, Any] = Field(default_factory=dict)
    format: Literal["json", "md", "pdf"] = "json"


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
