"""A proposal lead never changes an exit code."""

from __future__ import annotations

from typing import Any

from opencomplai_cli.main import FailOnLevel, _scan_should_fail
from opencomplai_core.models import CorroborationReport, EuAiScanSummary


def _lead(i: int) -> dict[str, Any]:
    return {
        "reason": "deterministic_matcher",
        "file": f"src/m{i}.py",
        "line": i + 1,
        "function": "rank_candidates",
        "annex_iii_area": 4,
        "confidence_band": "medium",
        "signals": ["rank_candidates"],
    }


def _report(severity: str, n_leads: int) -> CorroborationReport:
    summary = EuAiScanSummary.model_validate(
        {"proposal_leads": [_lead(i) for i in range(n_leads)]}
    )
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
            "detected_categories": [],
            "discrepancies": ["scoring_profiling"] if severity != "none" else [],
            "score_breakdown": {},
            "severity": severity,
            "feature_summary": {},
            "cache_summary": {},
            "skipped_paths": [],
            "limits_hit": [],
            "warnings": [],
            "detector_errors": [],
            "baseline_ref": None,
            "generated_at": "2026-07-11T00:00:00Z",
            "report_hash": "sha256:ghi",
            "eu_ai_scan": summary.model_dump(),
        }
    )


def test_leads_never_change_the_exit_code() -> None:
    assert "proposal_leads" in EuAiScanSummary.model_fields
    for level in FailOnLevel:
        for severity in ("none", "major"):
            assert _scan_should_fail(
                _report(severity, 3), level, None
            ) == _scan_should_fail(_report(severity, 0), level, None), (level, severity)
