"""The candidate tier is a lead for a person, never a finding."""

from __future__ import annotations

import ast
import json
import typing
from pathlib import Path

import pytest
import yaml
from opencomplai_core import models as _models
from opencomplai_core.models import (
    CANDIDATE_REASON_IMPORTED_NOT_CLASSIFIED,
    CorroborationReport,
    EuAiCandidate,
    EuAiRegulatoryFinding,
    EuAiScanSummary,
)
from opencomplai_core.scan_engine import _build_eu_ai_scan_summary
from opencomplai_core.scanner._hashing import report_hash
from opencomplai_core.scanner.proposal import build_classification_proposal
from opencomplai_core.scanner.sarif import report_to_sarif
from pydantic import ValidationError

_ROOT = Path(__file__).resolve().parents[3]
_OPENAPI = _ROOT / "services" / "gateway-api" / "openapi.yaml"
_ADR = _ROOT / "docs" / "adr" / "ADR-eu-ai-scan-gate.md"

_CANDIDATES = [
    EuAiCandidate(library="torch", file="src/a.py", line=3),
    EuAiCandidate(library="transformers", file="src/b.py", line=1),
]


def _finding(location: str, area: int | None = 4) -> EuAiRegulatoryFinding:
    return EuAiRegulatoryFinding(
        location=location,
        function="rank_candidates",
        risk_tier="high_risk",
        annex_iii_area=area,
    )


def _report(summary: EuAiScanSummary | None) -> CorroborationReport:
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
            "declared_categories": [],
            "evidence": [],
            "findings": [],
            "detected_categories": ["scoring_profiling"],
            "discrepancies": ["scoring_profiling"],
            "score_breakdown": {},
            "severity": "major",
            "feature_summary": {},
            "cache_summary": {},
            "skipped_paths": [],
            "limits_hit": [],
            "warnings": [],
            "detector_errors": [],
            "baseline_ref": None,
            "generated_at": "2026-07-11T00:00:00Z",
            "report_hash": "sha256:ghi",
            "eu_ai_scan": summary.model_dump() if summary is not None else None,
        }
    )


def _summary(with_candidates: bool) -> EuAiScanSummary:
    return EuAiScanSummary(
        high_risk=[_finding("src/a.py:10")],
        gated_callsite_count=1,
        regulatory_finding_count=1,
        candidates=list(_CANDIDATES) if with_candidates else [],
    )


def test_candidate_entry_shape() -> None:
    assert list(EuAiCandidate.model_fields) == ["library", "file", "line", "reason"]
    entry = EuAiCandidate(library="torch", file="src/a.py", line=3)
    assert entry.reason == "imported_not_classified"
    with pytest.raises(ValidationError):
        EuAiCandidate(library="torch", file="a.py", line=3, reason="other")  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        EuAiCandidate(library="torch", file="a.py", line=0)
    again = EuAiCandidate.model_validate(json.loads(entry.model_dump_json()))
    assert again == entry


def test_candidates_empty_by_default() -> None:
    assert EuAiScanSummary().candidates == []
    built = _build_eu_ai_scan_summary(usage_matches={}, regulatory_evidence=[])
    assert built.candidates == []
    dumped = json.loads(_report(EuAiScanSummary()).model_dump_json())
    assert dumped["eu_ai_scan"]["candidates"] == []


def test_candidates_do_not_change_report_hash_or_counts() -> None:
    plain = _report(_summary(with_candidates=False))
    led = _report(_summary(with_candidates=True))
    assert led.eu_ai_scan is not None
    assert len(led.eu_ai_scan.candidates) == 2
    assert report_hash(led) == report_hash(plain)
    assert plain.eu_ai_scan is not None
    assert (
        led.eu_ai_scan.regulatory_finding_count
        == plain.eu_ai_scan.regulatory_finding_count
        == 1
    )
    assert led.severity == plain.severity
    assert led.detected_categories == plain.detected_categories
    assert led.discrepancies == plain.discrepancies


def test_candidates_never_enter_the_proposal() -> None:
    lead_only = EuAiScanSummary(candidates=list(_CANDIDATES))
    proposal = build_classification_proposal(lead_only)
    assert proposal.proposed_annex_iii_area is None
    assert proposal.supporting_evidence == []
    assert proposal.minority_evidence == []

    assert (
        build_classification_proposal(_summary(True)).model_dump()
        == build_classification_proposal(_summary(False)).model_dump()
    )


def test_sarif_ignores_candidates() -> None:
    assert report_to_sarif(_report(_summary(True))) == report_to_sarif(
        _report(_summary(False))
    )


def test_openapi_candidate_schema_matches_models() -> None:
    if not _OPENAPI.exists():
        pytest.skip("gateway openapi.yaml not present in this checkout")
    schemas = yaml.safe_load(_OPENAPI.read_text(encoding="utf-8"))["components"][
        "schemas"
    ]
    assert set(schemas["EuAiScanSummary"]["properties"]) == set(
        EuAiScanSummary.model_fields
    )
    candidate = schemas["EuAiCandidate"]
    assert set(candidate["properties"]) == set(EuAiCandidate.model_fields)
    assert set(candidate["required"]) == set(EuAiCandidate.model_fields)
    assert candidate["properties"]["reason"]["enum"] == [
        CANDIDATE_REASON_IMPORTED_NOT_CLASSIFIED
    ]
    assert (
        schemas["EuAiScanSummary"]["properties"]["candidates"]["items"]["$ref"]
        == "#/components/schemas/EuAiCandidate"
    )


def test_reason_constant_is_the_only_allowed_reason() -> None:
    assert CANDIDATE_REASON_IMPORTED_NOT_CLASSIFIED == "imported_not_classified"
    annotation = EuAiCandidate.model_fields["reason"].annotation
    assert typing.get_args(annotation) == (CANDIDATE_REASON_IMPORTED_NOT_CLASSIFIED,)


def test_candidate_reason_constant_is_final_literal() -> None:
    """The constant must keep its literal type or the mypy ratchet rises."""
    tree = ast.parse(Path(_models.__file__).read_text(encoding="utf-8"))
    ann = [
        n.annotation
        for n in tree.body
        if isinstance(n, ast.AnnAssign)
        and isinstance(n.target, ast.Name)
        and n.target.id == "CANDIDATE_REASON_IMPORTED_NOT_CLASSIFIED"
    ]
    assert len(ann) == 1
    assert isinstance(ann[0], ast.Name)
    assert ann[0].id == "Final"
    assert (
        EuAiCandidate.model_fields["reason"].default
        == CANDIDATE_REASON_IMPORTED_NOT_CLASSIFIED
    )


def test_adr_documents_the_candidate_tier() -> None:
    if not _ADR.exists():
        pytest.skip("ADR not present in this checkout")
    text = " ".join(_ADR.read_text(encoding="utf-8").split())
    assert "candidates" in text
    assert CANDIDATE_REASON_IMPORTED_NOT_CLASSIFIED in text
    assert "`DET_INTENT` stays `1.1.0`" in text
