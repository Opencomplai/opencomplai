"""A candidate never changes an exit code."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from opencomplai_cli.main import FailOnLevel, _scan_should_fail, app
from opencomplai_core.models import (
    CorroborationReport,
    EuAiCandidate,
    EuAiScanSummary,
    SystemManifest,
)
from typer.testing import CliRunner

runner = CliRunner()


def _report(severity: str, n_candidates: int) -> CorroborationReport:
    summary = EuAiScanSummary(
        candidates=[
            EuAiCandidate(library="torch", file=f"src/m{i}.py", line=i + 1)
            for i in range(n_candidates)
        ]
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


def test_candidates_never_change_the_exit_code() -> None:
    for level in FailOnLevel:
        for severity in ("none", "major"):
            assert _scan_should_fail(
                _report(severity, 3), level, None
            ) == _scan_should_fail(_report(severity, 0), level, None), (level, severity)


def test_scan_json_carries_candidates_key(tmp_path: Path) -> None:
    pytest.importorskip("opencomplai_ai")
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "a.py").write_text(
        "from sklearn.ensemble import RandomForestClassifier\n\n\n"
        "def screen(applicants):\n    return rank_candidates(applicants)\n",
        encoding="utf-8",
    )
    manifest = tmp_path / "system-manifest.json"
    manifest.write_text(
        SystemManifest(
            system_id="cand-sys", intended_purpose="customer support chatbot"
        ).model_dump_json(),
        encoding="utf-8",
    )
    result = runner.invoke(
        app,
        [
            "scan",
            "--manifest",
            str(manifest),
            "--repo-root",
            str(repo),
            "--ai-intent",
            "--ai-model",
            "codebert-onnx",
            "--no-emit-evidence",
            "--no-ocignore-bootstrap",
            "-o",
            "json",
        ],
    )
    assert result.exit_code == 0, result.output[:200]
    payload = json.loads(result.stdout)["payload"]
    assert payload["eu_ai_scan"] is not None
    assert payload["eu_ai_scan"]["candidates"] == []
