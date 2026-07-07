"""Report export tests for compliance checker."""

from __future__ import annotations

import json
import re
import zlib
from pathlib import Path

import pytest
from opencomplai_core.compliance_checker import (
    CheckerSession,
    evaluate,
    render_json,
    render_markdown,
)
from opencomplai_core.compliance_checker.report import export_all, render_pdf

FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "checker_golden"
    / "06_high_risk_provider.json"
)


def _decoded_pdf_text(pdf_bytes: bytes) -> str:
    """Inflate fpdf2's FlateDecode content streams so plain substring checks work."""
    chunks: list[str] = []
    for match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", pdf_bytes, re.DOTALL):
        try:
            chunks.append(zlib.decompress(match.group(1)).decode("latin-1", errors="ignore"))
        except zlib.error:
            chunks.append(match.group(1).decode("latin-1", errors="ignore"))
    return "\n".join(chunks)


def test_render_json_round_trip() -> None:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    result = evaluate(CheckerSession(answers=data["session"]["answers"]))
    parsed = json.loads(render_json(result))
    assert parsed["is_high_risk"] is True


def test_render_markdown_structure() -> None:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    result = evaluate(CheckerSession(answers=data["session"]["answers"]))
    md = render_markdown(result)
    assert "# EU AI Act Compliance Checker Result" in md
    assert "## Obligations" in md
    assert "Disclaimer" in md


def test_render_markdown_includes_answers_and_determination_path() -> None:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    result = evaluate(CheckerSession(answers=data["session"]["answers"]))
    result.answers = dict(data["session"]["answers"])
    md = render_markdown(result)
    assert "## Your answers" in md
    # Raw keys never appear unlabeled; the human-readable question is shown.
    assert "Which kind of entity is your organisation?" in md
    # Select-type answers resolve to their option label, not the raw value.
    assert "Provider" in md
    assert "gate:yes" in md  # from result.determination_path


def test_render_pdf_includes_answers_and_determination_path() -> None:
    pytest.importorskip("fpdf")
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    result = evaluate(CheckerSession(answers=data["session"]["answers"]))
    result.answers = dict(data["session"]["answers"])
    pdf_bytes = render_pdf(result)
    assert len(pdf_bytes) > 100
    # fpdf2's content streams are FlateDecode-compressed; inflate them so the
    # rendered text (question labels, option labels, determination path) can
    # be checked without a full PDF parser.
    text = _decoded_pdf_text(pdf_bytes)
    assert "Your answers" in text
    assert "Provider" in text
    assert "Determination path" in text
    assert "gate:yes" in text


def test_export_all_writes_files(tmp_path: Path) -> None:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    result = evaluate(CheckerSession(answers=data["session"]["answers"]))
    fpdf = pytest.importorskip("fpdf")
    _ = fpdf
    paths = export_all(result, tmp_path, basename="report")
    assert paths["json"].exists()
    assert paths["markdown"].exists()
    assert paths["pdf"].exists()
    assert paths["pdf"].stat().st_size > 100
