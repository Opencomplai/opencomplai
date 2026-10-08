"""A scan detection is not a compliance verdict (fix for the false Met)."""

from __future__ import annotations

import pytest
from opencomplai_core.control_assessment import derive_controls
from opencomplai_core.control_catalog import get_catalog
from opencomplai_core.gap_report import (
    SCAN_NO_VERDICT,
    build_gap_report,
    load_gap_article_map,
)
from opencomplai_core.models import (
    ControlState,
    CorroborationReport,
    GapStatus,
    SignalCategory,
    SystemManifest,
)
from opencomplai_core.scanner.mapping import SIGNAL_TO_TAXONOMY


def _report(
    signal_category: str,
    mapped_taxonomy: list[str],
    *,
    declared: list[str],
    discrepancies: list[str] | None = None,
) -> CorroborationReport:
    discrepancies = discrepancies or []
    return CorroborationReport.model_validate(
        {
            "scan_id": "scan-1",
            "system_id": "test-sys",
            "commit_ref": "HEAD",
            "scanner_version": "0.1.0",
            "input_digest": "sha256:abc",
            "config_hash": "sha256:def",
            "detector_versions": {},
            "declared_purpose": "customer support chatbot",
            "declared_categories": declared,
            "evidence": [],
            "findings": [
                {
                    "finding_id": "find_1",
                    "signal_category": signal_category,
                    "evidence_ids": [],
                    "locations": ["src/model.py:1"],
                    "mapped_taxonomy": mapped_taxonomy,
                    "strength": 1.0,
                    "scope": "prod",
                    "reachability": "reachable_entrypoint",
                    "confidence_rationale": [],
                    "reviewer_prompt": "",
                }
            ],
            "detected_categories": mapped_taxonomy,
            "discrepancies": discrepancies,
            "score_breakdown": {},
            "severity": "none",
            "feature_summary": {},
            "cache_summary": {},
            "skipped_paths": [],
            "limits_hit": [],
            "warnings": [],
            "detector_errors": [],
            "baseline_ref": None,
            "generated_at": "2026-07-11T00:00:00Z",
            "report_hash": "sha256:ghi",
        }
    )


def _scan_only_requirements(*articles: str) -> dict:
    # Art. 14 also carries an artifact source that is always UNVERIFIED without a
    # repo root and outranks MET, which would mask a wrongly-MET scan row.
    return {
        a: {"sources": [s for s in cfg["sources"] if s["kind"] == "scan"]}
        for a, cfg in load_gap_article_map().items()
        if a in articles
    }


def _rows(report, requirements=None):
    gap = build_gap_report(
        "sys", "HEAD", corroboration_report=report, requirements=requirements
    )
    return {row.article: row for row in gap.articles}


def test_every_signal_category_has_an_explicit_taxonomy_entry():
    assert set(SIGNAL_TO_TAXONOMY) == set(SignalCategory)


@pytest.mark.parametrize(
    ("category", "mapped", "declared"),
    [
        ("agent_framework", [], []),
        ("mcp_server", [], []),
        ("agent_framework", ["employment"], ["employment"]),
    ],
)
def test_agent_and_mcp_findings_alone_are_unverified_for_art_14_and_15(
    category, mapped, declared
):
    rows = _rows(
        _report(category, mapped, declared=declared),
        _scan_only_requirements("Art. 14", "Art. 15"),
    )
    assert rows["Art. 14"].status == GapStatus.UNVERIFIED
    assert rows["Art. 14"].source.value == "scan"
    assert "no compliance verdict" in rows["Art. 14"].rationale
    if category == "agent_framework":
        assert rows["Art. 15"].status == GapStatus.UNVERIFIED
        assert "no compliance verdict" in rows["Art. 15"].rationale
    assert all(r.status != GapStatus.MET for r in rows.values())


def test_pii_dataflow_alone_is_unverified_for_art_10_even_when_declared():
    assert "pii_dataflow" in SCAN_NO_VERDICT
    rows = _rows(
        _report("pii_dataflow", ["essential_services"], declared=["essential_services"])
    )
    assert rows["Art. 10"].status == GapStatus.UNVERIFIED
    assert "no compliance verdict" in rows["Art. 10"].rationale


def test_scan_finding_with_empty_taxonomy_is_unverified():
    rows = _rows(_report("scoring_profiling", [], declared=["employment"]))
    assert rows["Art. 6"].status == GapStatus.UNVERIFIED


def test_scan_finding_partly_outside_declared_is_unverified():
    rows = _rows(
        _report(
            "scoring_profiling",
            ["employment", "essential_services"],
            declared=["employment"],
        ),
        _scan_only_requirements("Art. 6"),
    )
    assert rows["Art. 6"].status == GapStatus.UNVERIFIED


def test_unverified_scan_row_does_not_satisfy_a_control():
    report = build_gap_report(
        "sys-1",
        "abc123",
        corroboration_report=_report("agent_framework", [], declared=[]),
        requirements=_scan_only_requirements("Art. 14"),
    )
    manifest = SystemManifest(
        system_id="sys-1",
        intended_purpose="credit scoring",
        compliance_target="EU_AI_ACT",
        high_risk_presumption=True,
        commit_ref="abc123",
        training_data_description="internal loan applications 2018-2024",
        model_architecture="gradient boosted trees",
        operator_role="provider",
    )
    controls = derive_controls(
        report, manifest, get_catalog(), tenant_id="t", now="2026-08-17T00:00:00+00:00"
    )
    art14 = [c for c in controls if c.article_ref == "Art. 14"]
    assert art14
    assert all(c.state == ControlState.EVIDENCE_MISSING for c in art14)
