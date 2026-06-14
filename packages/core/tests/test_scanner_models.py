"""Scanner model contracts — JSON round-trip and enum values."""

from __future__ import annotations

from opencomplai_core.models import (
    CorroborationReport,
    DetectionFinding,
    DiscrepancySeverity,
    EvidenceItem,
    EvidenceKind,
    EvidenceScope,
    Reachability,
    ScanSummary,
    ScoreBreakdown,
    SignalCategory,
)


def test_evidence_kind_enum_values():
    assert EvidenceKind.DEPENDENCY.value == "dependency"
    assert EvidenceKind.IMPORT.value == "import"


def test_signal_category_enum_values():
    assert SignalCategory.AI_SDK.value == "ai_sdk"
    assert SignalCategory.BIOMETRIC.value == "biometric"


def test_discrepancy_severity_enum_values():
    assert DiscrepancySeverity.NONE.value == "none"
    assert DiscrepancySeverity.MAJOR.value == "major"
    assert DiscrepancySeverity.CRITICAL.value == "critical"


def test_evidence_item_json_round_trip():
    item = EvidenceItem(
        evidence_id="ev-1",
        evidence_kind=EvidenceKind.IMPORT,
        category=SignalCategory.AI_SDK,
        token_hash="sha256:abc",
        token_label="openai",
        locations=["src/app.py:3"],
        scope=EvidenceScope.PROD,
        reachability=Reachability.IMPORT_ONLY,
        detector_id="DET_AST_V1",
        detector_version="1.0.0",
        redaction_level="hash_only",
        rationale_code="import_detected",
        confidence=0.8,
    )
    restored = EvidenceItem.model_validate_json(item.model_dump_json())
    assert restored.evidence_id == "ev-1"
    assert restored.category == SignalCategory.AI_SDK


def test_corroboration_report_json_round_trip():
    report = CorroborationReport(
        scan_id="scan-1",
        system_id="sys-1",
        commit_ref="HEAD",
        scanner_version="1.0.0",
        input_digest="sha256:input",
        config_hash="sha256:config",
        detector_versions={"DET_AI_DEP_V1": "1.0.0"},
        declared_purpose="customer support chatbot",
        declared_categories=[],
        evidence=[],
        findings=[],
        detected_categories=[],
        discrepancies=[],
        score_breakdown={},
        severity=DiscrepancySeverity.NONE,
        feature_summary={},
        cache_summary={},
        skipped_paths=[],
        limits_hit=[],
        warnings=[],
        detector_errors=[],
        baseline_ref=None,
        generated_at="2026-06-09T00:00:00+00:00",
        report_hash="sha256:report",
    )
    restored = CorroborationReport.model_validate_json(report.model_dump_json())
    assert restored.scan_id == "scan-1"
    assert restored.severity == DiscrepancySeverity.NONE


def test_scan_summary_json_round_trip():
    summary = ScanSummary(
        scan_id="scan-1",
        scanner_version="1.0.0",
        severity=DiscrepancySeverity.MINOR,
        detected_categories=["biometric"],
        discrepancies=["biometric"],
        report_hash="sha256:report",
        evidence_hashes=["sha256:ev1"],
    )
    restored = ScanSummary.model_validate_json(summary.model_dump_json())
    assert restored.discrepancies == ["biometric"]


def test_detection_finding_and_score_breakdown():
    finding = DetectionFinding(
        finding_id="f-1",
        signal_category=SignalCategory.BIOMETRIC,
        evidence_ids=["ev-1"],
        locations=["src/face.py:42"],
        mapped_taxonomy=["biometric"],
        strength=0.9,
        scope=EvidenceScope.PROD,
        reachability=Reachability.REACHABLE_ENTRYPOINT,
        confidence_rationale=["prod_callsite"],
        reviewer_prompt="Verify biometric usage in production paths.",
    )
    score = ScoreBreakdown(
        detector_confidence=0.8,
        evidence_strength=0.9,
        scope_weight=1.0,
        reachability_weight=1.0,
        taxonomy_weight=1.0,
        final_score=0.85,
        rationale_codes=["prod_callsite"],
    )
    assert finding.mapped_taxonomy == ["biometric"]
    assert score.final_score == 0.85
