"""Report export tests for compliance checker."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from opencomplai_core.compliance_checker import (
    CheckerSession,
    evaluate,
    render_json,
    render_markdown,
)
from opencomplai_core.compliance_checker.report import export_all

FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "fli_golden"
    / "06_high_risk_provider.json"
)


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
