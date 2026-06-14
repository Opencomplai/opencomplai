"""Render compliance checker results to JSON, Markdown, and PDF."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from opencomplai_core.compliance_checker.catalog import load_help_content
from opencomplai_core.compliance_checker.models import ComplianceCheckerResult

_DISCLAIMER = load_help_content()["disclaimer"]["body"]


def render_json(result: ComplianceCheckerResult, *, indent: int = 2) -> str:
    """Serialize a checker result to JSON."""
    return result.model_dump_json(indent=indent)


def render_markdown(result: ComplianceCheckerResult) -> str:
    """Render a checker result as Markdown using plain string templates."""
    lines: list[str] = [
        "# EU AI Act Compliance Checker Result",
        "",
        f"**Checker version:** {result.checker_version}",
        f"**In scope:** {'Yes' if result.in_scope else 'No'}",
        f"**High risk:** {'Yes' if result.is_high_risk else 'No'}",
        f"**Prohibited:** {'Yes' if result.is_prohibited else 'No'}",
    ]
    if result.effective_entity is not None:
        lines.append(f"**Effective operator role:** {result.effective_entity.value}")
    lines.extend(["", "## Status changes", ""])
    if result.status_changes:
        for item in result.status_changes:
            lines.extend([f"### {item.title}", "", item.body, ""])
    else:
        lines.extend(["None.", ""])

    lines.extend(["## Obligations", ""])
    if result.obligations:
        for item in result.obligations:
            lines.extend(
                [
                    f"### {item.title} ({item.article_ref})",
                    "",
                    item.body,
                    "",
                ]
            )
    else:
        lines.extend(["None.", ""])

    lines.extend(["## Determination path", ""])
    for step in result.determination_path:
        lines.append(f"- `{step}`")
    lines.extend(["", "## Disclaimer", "", _DISCLAIMER, ""])
    return "\n".join(lines)


def render_pdf(result: ComplianceCheckerResult) -> bytes:
    """Render a checker result to PDF bytes using fpdf2."""
    try:
        from fpdf import FPDF
    except ImportError as exc:
        msg = "PDF export requires the optional 'reports' dependency (fpdf2>=2.7)"
        raise ImportError(msg) from exc

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)

    def write_block(text: str, *, bold: bool = False) -> None:
        safe = text.encode("latin-1", errors="replace").decode("latin-1")
        pdf.set_font("Helvetica", style="B" if bold else "", size=11)
        pdf.multi_cell(0, 6, safe)
        pdf.ln(2)

    write_block("EU AI Act Compliance Checker Result", bold=True)
    write_block(f"Checker version: {result.checker_version}")
    write_block(f"In scope: {'Yes' if result.in_scope else 'No'}")
    write_block(f"High risk: {'Yes' if result.is_high_risk else 'No'}")
    write_block(f"Prohibited: {'Yes' if result.is_prohibited else 'No'}")
    if result.effective_entity is not None:
        write_block(f"Effective operator role: {result.effective_entity.value}")

    write_block("Status changes", bold=True)
    if result.status_changes:
        for item in result.status_changes:
            write_block(item.title, bold=True)
            write_block(item.body)
    else:
        write_block("None.")

    write_block("Obligations", bold=True)
    if result.obligations:
        for item in result.obligations:
            write_block(f"{item.title} ({item.article_ref})", bold=True)
            write_block(item.body)
    else:
        write_block("None.")

    write_block("Disclaimer", bold=True)
    write_block(_DISCLAIMER)

    out = pdf.output()
    if isinstance(out, bytes):
        return out
    if isinstance(out, bytearray):
        return bytes(out)
    return str(out).encode("latin-1")


def export_all(
    result: ComplianceCheckerResult,
    output_dir: Path | str,
    *,
    basename: str = "compliance-checker-result",
) -> dict[str, Path]:
    """Write JSON, Markdown, and PDF exports to output_dir."""
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)

    json_path = target / f"{basename}.json"
    md_path = target / f"{basename}.md"
    pdf_path = target / f"{basename}.pdf"

    json_path.write_text(render_json(result), encoding="utf-8")
    md_path.write_text(render_markdown(result), encoding="utf-8")
    pdf_path.write_bytes(render_pdf(result))

    return {
        "json": json_path,
        "markdown": md_path,
        "pdf": pdf_path,
    }


def result_to_dict(result: ComplianceCheckerResult) -> dict[str, Any]:
    """Return a plain dict representation of the result."""
    return json.loads(render_json(result))
