"""Tests for the combined scan+eval+manifest+gap-report renderer (opencomplai report)."""

from opencomplai_core.engine import assess
from opencomplai_core.gap_report import build_gap_report
from opencomplai_core.models import AssessmentInput, ModelMetadata, SystemManifest
from opencomplai_core.report_engine import render_report


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
    try:
        render_report(manifest, fmt="docx")
    except ValueError as e:
        assert "docx" in str(e)
    else:
        raise AssertionError("expected ValueError for unsupported format")


def test_report_does_not_import_networking_modules():
    """Air-gap compatibility: report_engine.py must not call out to services."""
    import opencomplai_core.report_engine as mod

    source = open(mod.__file__, encoding="utf-8").read()
    assert "_call_service" not in source
    assert "urllib" not in source
    assert "requests" not in source
