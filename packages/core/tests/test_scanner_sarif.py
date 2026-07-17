"""Tests for the SARIF 2.1.0 export (opencomplai scan --sarif-output)."""

from __future__ import annotations

from pathlib import Path

from opencomplai_core.scan_engine import run_scan
from opencomplai_core.scanner.feature_types import ScanConfig
from opencomplai_core.scanner.sarif import report_to_sarif


def _biometric_repo(tmp_path: Path) -> Path:
    (tmp_path / "requirements.txt").write_text("face_recognition\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "face.py").write_text(
        "import face_recognition\n", encoding="utf-8"
    )
    return tmp_path


def test_report_to_sarif_has_required_top_level_fields(tmp_path):
    repo = _biometric_repo(tmp_path)
    report = run_scan("test-sys", "HEAD", repo, "customer support chatbot", config=ScanConfig())
    sarif = report_to_sarif(report)
    assert sarif["version"] == "2.1.0"
    assert "$schema" in sarif
    assert "runs" in sarif
    assert len(sarif["runs"]) == 1


def test_report_to_sarif_run_has_tool_driver_and_results(tmp_path):
    repo = _biometric_repo(tmp_path)
    report = run_scan("test-sys", "HEAD", repo, "customer support chatbot", config=ScanConfig())
    sarif = report_to_sarif(report)
    run = sarif["runs"][0]
    assert run["tool"]["driver"]["name"] == "opencomplai"
    assert len(run["results"]) == len(report.evidence)
    assert len(run["results"]) > 0


def test_sarif_result_has_location_with_line_number(tmp_path):
    repo = _biometric_repo(tmp_path)
    report = run_scan("test-sys", "HEAD", repo, "customer support chatbot", config=ScanConfig())
    sarif = report_to_sarif(report)
    result = sarif["runs"][0]["results"][0]
    location = result["locations"][0]["physicalLocation"]
    assert "uri" in location["artifactLocation"]
    assert isinstance(location["region"]["startLine"], int)
    assert location["region"]["startLine"] >= 1


def test_sarif_rule_ids_are_unique_per_detector_category():
    from opencomplai_core.models import (
        EvidenceItem,
        EvidenceKind,
        EvidenceScope,
        Reachability,
        SignalCategory,
    )
    from opencomplai_core.scanner.sarif import _rule_definitions

    items = [
        EvidenceItem(
            evidence_id="e1",
            evidence_kind=EvidenceKind.IMPORT,
            category=SignalCategory.BIOMETRIC,
            token_hash="h1",
            token_label="face_recognition",
            locations=["src/face.py:1"],
            scope=EvidenceScope.PROD,
            reachability=Reachability.REACHABLE_ENTRYPOINT,
            detector_id="DET_BIOMETRIC_V1",
            detector_version="1.0.0",
            redaction_level="hash_only",
            rationale_code="biometric_import",
            confidence=0.85,
        ),
        EvidenceItem(
            evidence_id="e2",
            evidence_kind=EvidenceKind.IMPORT,
            category=SignalCategory.BIOMETRIC,
            token_hash="h2",
            token_label="deepface",
            locations=["src/face.py:2"],
            scope=EvidenceScope.PROD,
            reachability=Reachability.REACHABLE_ENTRYPOINT,
            detector_id="DET_BIOMETRIC_V1",
            detector_version="1.0.0",
            redaction_level="hash_only",
            rationale_code="biometric_import",
            confidence=0.85,
        ),
    ]
    rules = _rule_definitions(items)
    assert len(rules) == 1  # same detector+category collapses to one rule definition
    assert rules[0]["id"] == "DET_BIOMETRIC_V1/biometric"


def test_sarif_output_is_valid_json_serializable(tmp_path):
    import json

    repo = _biometric_repo(tmp_path)
    report = run_scan("test-sys", "HEAD", repo, "customer support chatbot", config=ScanConfig())
    sarif = report_to_sarif(report)
    serialized = json.dumps(sarif)
    reparsed = json.loads(serialized)
    assert reparsed["version"] == "2.1.0"
