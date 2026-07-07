"""Golden regression tests for EU AI Act scan output."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from opencomplai_cli.main import _render_eu_ai_scan
from opencomplai_core.models import (
    CorroborationReport,
    DiscrepancySeverity,
    EuAiRegulatoryFinding,
    EuAiScanSummary,
    EuAiUsageEntry,
    FlagRationale,
)

FIXTURE_ROOT = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "eu_ai_scan"


def test_golden_fixture_has_no_apirouter_in_gated_callsites():
    from opencomplai_core.scanner.ai_usage_gate import gate_features_for_intent
    from opencomplai_core.scanner.features import extract_features
    from opencomplai_core.scanner.file_ai_context import build_file_ai_context_map
    from opencomplai_core.scanner.inventory import build_repo_inventory

    repo = FIXTURE_ROOT
    inventory = build_repo_inventory(repo, limits=None)
    features = extract_features(inventory)
    ctx = build_file_ai_context_map(features, [])
    gated = gate_features_for_intent(features, ctx)
    all_tokens = {c.name for c in gated.features.callsites}
    all_tokens.update(i.module for i in gated.features.imports)
    assert "APIRouter" not in all_tokens
    assert "ASGITransport" not in all_tokens
    assert any("openai" in t.lower() for t in all_tokens)


def test_golden_fixture_detects_gemini_config_callsites():
    from opencomplai_core.scanner.ai_usage_gate import gate_features_for_intent
    from opencomplai_core.scanner.features import extract_features
    from opencomplai_core.scanner.file_ai_context import build_file_ai_context_map
    from opencomplai_core.scanner.inventory import build_repo_inventory

    repo = FIXTURE_ROOT
    inventory = build_repo_inventory(repo, limits=None)
    assert inventory.entries, "fixture repo should inventory source files"
    features = extract_features(inventory)
    ctx = build_file_ai_context_map(features, [])
    gated = gate_features_for_intent(features, ctx)
    locations = set(gated.usage_matches.keys())
    assert any("oracle/route.ts" in loc for loc in locations)
    assert any(
        match.reason == "config_llm_signal" for match in gated.usage_matches.values()
    )


def test_render_eu_ai_scan_sections():
    report = CorroborationReport(
        scan_id="scan_test",
        system_id="test",
        commit_ref="HEAD",
        scanner_version="0.1.0",
        input_digest="abc",
        config_hash="def",
        detector_versions={},
        declared_purpose="essential services scoring",
        declared_categories=["essential_services"],
        evidence=[],
        findings=[],
        detected_categories=["essential_services"],
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
        generated_at="2026-01-01T00:00:00Z",
        report_hash="hash",
        eu_ai_scan=EuAiScanSummary(
            capabilities=[
                EuAiUsageEntry(
                    location="src/app.py:1",
                    function="openai",
                    usage_type="llm_inference",
                    file="src/app.py",
                )
            ],
            high_risk=[
                EuAiRegulatoryFinding(
                    location="src/app.py:18",
                    function="predict_proba",
                    risk_tier="high_risk",
                    annex_iii_area=5,
                    eu_obligation=["Art.6(2)+Annex III area 5"],
                    rationale=FlagRationale(
                        summary=(
                            'Matched Annex III area 5 code signal "predict_proba" '
                            "(Creditworthiness assessment); high-risk under Art. 6(2)."
                        ),
                        needed_action=(
                            "Declare this high-risk use in intended_purpose and implement "
                            "Annex III controls."
                        ),
                        matched_signals=["predict_proba"],
                        gate_reason="inference_verb_with_file_context",
                        regulation_ref="Art. 6(2), Annex III pt.5(b)",
                        knowledge_entry_title="Creditworthiness assessment",
                    ),
                )
            ],
            gated_callsite_count=3,
            regulatory_finding_count=1,
        ),
    )

    printed: list[str] = []

    mock_console = MagicMock()
    mock_console.print.side_effect = lambda *a, **k: printed.append(
        " ".join(str(x) for x in a)
    )

    with patch("opencomplai_cli.main.console", mock_console):
        _render_eu_ai_scan(report, verbose=False)

    output = "\n".join(printed)
    assert "EU AI Act Scan" in output
    assert "1. AI usage map" in output
    assert "2. Prohibited" in output
    assert "3. High-risk" in output
    assert "4. Limited-risk" in output
    assert "5. Declaration cross-check" in output
    assert "6. Flag rationale" in output
    assert "WHY:" in output
    assert "ACTION:" in output
    assert "APIRouter" not in output
    assert (
        "5 Essential services" in output
        or "Area 5" in output
        or "area 5" in output.lower()
    )


@pytest.mark.slow
def test_fixture_scan_json_includes_eu_ai_scan():
    pytest.importorskip("opencomplai_ai")
    from opencomplai_cli.main import app
    from typer.testing import CliRunner

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "scan",
            "--manifest",
            str(FIXTURE_ROOT / "system-manifest.json"),
            "--repo-root",
            str(FIXTURE_ROOT),
            "--output",
            "json",
            "--no-emit-evidence",
            "--no-ocignore-bootstrap",
            "--ai-intent",
        ],
    )
    if result.exit_code != 0:
        if "manifest not found" in result.output or "Error:" in result.output:
            pytest.fail(result.output)
        pytest.skip(f"AI intent scan unavailable: {result.output[:200]}")
    data = json.loads(result.output)
    assert "eu_ai_scan" in data
    if data["eu_ai_scan"] is not None:
        assert "capabilities" in data["eu_ai_scan"]
        capability_locs = [
            c.get("location", "") for c in data["eu_ai_scan"]["capabilities"]
        ]
        assert any("oracle/route.ts" in loc for loc in capability_locs)
        evidence_labels = [e.get("token_label", "") for e in data.get("evidence", [])]
        assert "APIRouter" not in evidence_labels
        for tier in ("prohibited", "high_risk", "limited_risk"):
            for finding in data["eu_ai_scan"].get(tier, []):
                if finding:
                    assert finding.get("rationale") is not None
                    assert finding["rationale"].get("summary")
                    assert finding["rationale"].get("needed_action")
                    assert finding.get("needed_action")
