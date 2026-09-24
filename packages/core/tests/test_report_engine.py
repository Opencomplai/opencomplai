"""Tests for the combined scan+eval+manifest+gap-report renderer (opencomplai report)."""

import html
import json
import re
import zlib
from pathlib import Path

import pytest
from opencomplai_core.engine import assess
from opencomplai_core.frameworks import FRAMEWORKS, FrameworkPack
from opencomplai_core.gap_report import build_gap_report
from opencomplai_core.models import (
    DISCLAIMER_V1,
    DISCLAIMER_V2,
    ArticleGapSource,
    ArticleGapStatus,
    AssessmentInput,
    FrameworkReport,
    GapReport,
    GapStatus,
    ModelMetadata,
    ScanResult,
    ScanStatusArtifact,
    SystemManifest,
)
from opencomplai_core.report_engine import render_report

FIXTURE_PACK = FrameworkPack(
    "FIXTURE",
    "Fixture framework",
    requirements=Path(__file__).parent
    / "fixtures"
    / "framework_pack"
    / "requirements.json",
)


def _make_manifest() -> SystemManifest:
    return SystemManifest(
        system_id="test-sys",
        intended_purpose="rule-based scoring",
        compliance_target="EU_AI_ACT",
        high_risk_presumption=False,
        commit_ref="HEAD",
    )


def _make_risk_result():
    return assess(
        AssessmentInput(
            model=ModelMetadata(
                name="test-sys",
                version="HEAD",
                modality="text",
                use_case="rule-based scoring",
                deployment_context="local",
            )
        )
    )


def test_html_report_contains_system_id_and_rule_table():
    manifest = _make_manifest()
    risk_result = _make_risk_result()
    html_doc = render_report(manifest, risk_result=risk_result, fmt="html")
    assert isinstance(html_doc, str)
    assert "test-sys" in html_doc
    assert "<table>" in html_doc
    assert "EU AI Act, Article 6" in html_doc


def test_html_report_contains_gap_report_table_when_supplied():
    manifest = _make_manifest()
    risk_result = _make_risk_result()
    gap_report = build_gap_report("test-sys", "HEAD", risk_result=risk_result)
    html_doc = render_report(
        manifest, risk_result=risk_result, gap_report=gap_report, fmt="html"
    )
    assert "MISSING" in html_doc or "MET" in html_doc


def test_html_report_handles_missing_optional_inputs_gracefully():
    manifest = _make_manifest()
    html_doc = render_report(manifest, fmt="html")
    assert "test-sys" in html_doc
    assert "No rule-engine result supplied" in html_doc
    assert "No gap report supplied" in html_doc


def test_pdf_report_produces_valid_pdf_bytes():
    manifest = _make_manifest()
    risk_result = _make_risk_result()
    gap_report = build_gap_report("test-sys", "HEAD", risk_result=risk_result)
    pdf_bytes = render_report(
        manifest, risk_result=risk_result, gap_report=gap_report, fmt="pdf"
    )
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes[:4] == b"%PDF"


def test_unsupported_format_raises():
    manifest = _make_manifest()
    with pytest.raises(ValueError, match="docx"):
        render_report(manifest, fmt="docx")


def test_report_does_not_import_networking_modules():
    """Air-gap compatibility: report_engine.py must not call out to services."""
    import opencomplai_core.report_engine as mod

    source = open(mod.__file__, encoding="utf-8").read()
    assert "_call_service" not in source
    assert "urllib" not in source
    assert "requests" not in source


def _framework_reports(gap_report: GapReport) -> dict[str, FrameworkReport]:
    fixture = GapReport(
        system_id="test-sys",
        commit_ref="HEAD",
        generated_at=gap_report.generated_at,
        articles=[
            ArticleGapStatus(
                article="FIXTURE:REQ-1",
                status=GapStatus.PARTIAL,
                source=ArticleGapSource.ARTIFACT,
                evidence_ref="docs/risk_register.md",
                rationale="<b>thin</b> risk register",
            )
        ],
    )
    return {
        "EU_AI_ACT": FrameworkReport(
            framework="EU_AI_ACT",
            label="EU AI Act (Regulation (EU) 2024/1689)",
            data_version="aaaaaaaaaaaa",
            disclaimer_ref="DISCLAIMER_V1",
            report=gap_report,
        ),
        "FIXTURE": FrameworkReport(
            framework="FIXTURE",
            label="Fixture framework",
            data_version="bbbbbbbbbbbb",
            disclaimer_ref="DISCLAIMER_V2",
            excluded={"FIXTURE:REQ-3": "No deployers: internal tool only."},
            report=fixture,
        ),
    }


def _envelope(html_doc: str) -> dict:
    match = re.search(
        r'<script id="oc-envelope" type="application/json">(.*?)</script>', html_doc
    )
    assert match is not None
    return json.loads(html.unescape(match[1]))


def test_framework_reports_add_one_section_per_non_eu_framework(monkeypatch):
    monkeypatch.setitem(FRAMEWORKS, "FIXTURE", FIXTURE_PACK)
    manifest = _make_manifest()
    gap_report = build_gap_report("test-sys", "HEAD", risk_result=_make_risk_result())
    html_doc = render_report(
        manifest,
        gap_report=gap_report,
        framework_reports=_framework_reports(gap_report),
        fmt="html",
    )

    section = html_doc[
        html_doc.index('<table id="gap-table">') : html_doc.index(
            "<h2>Eval summary</h2>"
        )
    ]
    assert section.count("<h2>") == 1
    assert "<h2>Fixture framework</h2>" in section
    assert "Data version bbbbbbbbbbbb" in section
    assert "<td>FIXTURE:REQ-1</td><td>Risk register maintained</td>" in section
    assert "&lt;b&gt;thin&lt;/b&gt; risk register" in section
    assert "<li>FIXTURE:REQ-3: No deployers: internal tool only.</li>" in section
    assert DISCLAIMER_V2 in section

    envelope = _envelope(html_doc)
    assert envelope["disclaimer"] == DISCLAIMER_V2
    reports = envelope["payload"]["framework_reports"]
    assert list(reports) == ["EU_AI_ACT", "FIXTURE"]
    assert reports["FIXTURE"]["excluded"] == {
        "FIXTURE:REQ-3": "No deployers: internal tool only."
    }


def test_framework_reports_default_to_the_artifacts(monkeypatch):
    monkeypatch.setitem(FRAMEWORKS, "FIXTURE", FIXTURE_PACK)
    gap_report = build_gap_report("test-sys", "HEAD", risk_result=_make_risk_result())
    artifact = ScanStatusArtifact(
        install_id="install-1",
        system_id="test-sys",
        commit_ref="HEAD",
        result=ScanResult.PASS,
        rationale_hash="sha256:" + "c" * 64,
        duration_ms=1,
        gap_report=gap_report,
        framework_reports=_framework_reports(gap_report),
    )
    html_doc = render_report(_make_manifest(), artifact=artifact, fmt="html")

    assert "<h2>Fixture framework</h2>" in html_doc
    envelope = _envelope(html_doc)
    assert envelope["disclaimer"] == DISCLAIMER_V2
    assert list(envelope["payload"]["framework_reports"]) == ["EU_AI_ACT", "FIXTURE"]


def test_no_framework_reports_leaves_the_report_as_before():
    manifest = _make_manifest()
    gap_report = build_gap_report("test-sys", "HEAD", risk_result=_make_risk_result())
    for framework_reports in (None, {}):
        html_doc = render_report(
            manifest,
            gap_report=gap_report,
            framework_reports=framework_reports,
            fmt="html",
        )
        assert "{{framework_reports_section}}" not in html_doc
        assert "</table>\n\n<h2>Eval summary</h2>" in html_doc
        envelope = _envelope(html_doc)
        assert envelope["disclaimer"] == DISCLAIMER_V1
        assert "framework_reports" not in envelope["payload"]


def test_pdf_report_lists_framework_rows():
    manifest = _make_manifest()
    gap_report = build_gap_report("test-sys", "HEAD", risk_result=_make_risk_result())
    pdf_bytes = render_report(
        manifest,
        gap_report=gap_report,
        framework_reports=_framework_reports(gap_report),
        fmt="pdf",
    )
    text = b"".join(
        zlib.decompress(stream)
        for stream in re.findall(rb"stream\r?\n(.*?)\r?\nendstream", pdf_bytes, re.S)
    ).decode("latin-1")
    assert "Fixture framework:" in text
    assert "FIXTURE:REQ-1: PARTIAL" in text
