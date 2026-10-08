from __future__ import annotations

from opencomplai_core.control_assessment import derive_controls
from opencomplai_core.control_catalog import get_catalog
from opencomplai_core.control_identity import make_control_id
from opencomplai_core.models import (
    ArticleGapSource,
    ArticleGapStatus,
    ConfidenceLabel,
    ControlState,
    GapReport,
    GapStatus,
    SystemManifest,
)

TENANT_ID = "tenant-a"
NOW = "2026-08-17T00:00:00+00:00"


def _manifest() -> SystemManifest:
    return SystemManifest(
        system_id="sys-1",
        intended_purpose="credit scoring",
        compliance_target="EU_AI_ACT",
        high_risk_presumption=True,
        commit_ref="abc123",
        operator_role="provider",
    )


def _row(article: str, status: GapStatus) -> ArticleGapStatus:
    return ArticleGapStatus(
        article=article,
        status=status,
        source=ArticleGapSource.RULE,
        evidence_ref="RULE_X",
        rationale="fixture",
        confidence=0.9 if status == GapStatus.MET else None,
        confidence_label=(
            ConfidenceLabel.MEASURED
            if status == GapStatus.MET
            else ConfidenceLabel.NOT_ASSESSED
        ),
    )


MET_ROW = _row("Art. 9", GapStatus.MET)
MISSING_ROW = _row("Art. 10", GapStatus.MISSING)


def _report(rows, na=None) -> GapReport:
    kw = {"not_applicable": na} if na is not None else {}
    return GapReport(
        system_id="sys-1", commit_ref="abc123", generated_at=NOW, articles=rows, **kw
    )


def _derive(report, manifest: SystemManifest, existing=()):
    return derive_controls(
        report,
        manifest,
        get_catalog(),
        existing,
        tenant_id=TENANT_ID,
        now=NOW,
    )


def test_not_applicable_article_gets_no_control():
    out = _derive(_report([MET_ROW, MISSING_ROW], {"Art. 10": "no"}), _manifest())
    assert [c.obligation_id for c in out] == ["Art. 9"]


def test_existing_control_for_na_article_is_not_returned_waived():
    manifest = _manifest()
    first = _derive(_report([MET_ROW]), manifest)
    assert first[0].state == ControlState.SATISFIED
    out = _derive(_report([], {"Art. 9": "no"}), manifest, first)
    cid = make_control_id(TENANT_ID, manifest.system_id, "Art. 9")
    assert all(c.control_id != cid for c in out)
    assert all(c.state != ControlState.WAIVED for c in out)


def test_no_not_applicable_output_identical():
    manifest = _manifest()
    rows = [MET_ROW, MISSING_ROW]
    assert _derive(_report(rows), manifest) == _derive(_report(rows, {}), manifest)
