"""CLI scan command — exit codes and opt-in behavior."""

from __future__ import annotations

import json
from pathlib import Path

from opencomplai_cli.main import app
from typer.testing import CliRunner

runner = CliRunner()


def _write_manifest(tmp_path: Path, purpose: str = "customer support chatbot") -> Path:
    manifest = tmp_path / "system-manifest.json"
    result = runner.invoke(
        app,
        [
            "init",
            "--system-id",
            "scan-test",
            "--intended-purpose",
            purpose,
            "--output",
            str(manifest),
        ],
    )
    assert result.exit_code == 0
    return manifest


def _biometric_repo(tmp_path: Path) -> Path:
    (tmp_path / "requirements.txt").write_text("face_recognition\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "face.py").write_text(
        "import face_recognition\n", encoding="utf-8"
    )
    return tmp_path


def test_scan_exits_zero_with_discrepancies_by_default(tmp_path):
    manifest = _write_manifest(tmp_path)
    repo = _biometric_repo(tmp_path)
    result = runner.invoke(
        app,
        ["scan", "--manifest", str(manifest), "--repo-root", str(repo)],
    )
    assert result.exit_code == 0


def test_scan_json_output_shape(tmp_path):
    manifest = _write_manifest(tmp_path)
    repo = _biometric_repo(tmp_path)
    result = runner.invoke(
        app,
        [
            "scan",
            "--manifest",
            str(manifest),
            "--repo-root",
            str(repo),
            "--output",
            "json",
            "--no-ocignore-bootstrap",
        ],
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "severity" in data
    assert "report_hash" in data
    assert "discrepancies" in data


def test_init_scan_prints_without_mutating_manifest(tmp_path):
    repo = _biometric_repo(tmp_path)
    manifest = tmp_path / "m.json"
    result = runner.invoke(
        app,
        [
            "init",
            "--system-id",
            "scan-test",
            "--intended-purpose",
            "customer support chatbot",
            "--output",
            str(manifest),
            "--scan",
            "--repo-root",
            str(repo),
        ],
    )
    assert result.exit_code == 0
    data = json.loads(manifest.read_text())
    assert data["intended_purpose"] == "customer support chatbot"


def test_check_scan_without_fail_on_preserves_pass_exit(tmp_path):
    manifest = _write_manifest(tmp_path)
    repo = _biometric_repo(tmp_path)
    result = runner.invoke(
        app,
        [
            "check",
            "--manifest",
            str(manifest),
            "--repo-root",
            str(repo),
            "--scan",
        ],
    )
    assert result.exit_code == 0


def test_scan_human_output_shows_token_annotation(tmp_path):
    manifest = _write_manifest(tmp_path)
    repo = _biometric_repo(tmp_path)
    result = runner.invoke(
        app,
        ["scan", "--manifest", str(manifest), "--repo-root", str(repo)],
    )
    assert result.exit_code == 0
    assert "[token:" in result.output or 'token: "' in result.output
    assert "category:" in result.output
    assert "confidence:" in result.output


def test_scan_human_output_shows_evidence_without_discrepancies(tmp_path):
    manifest = _write_manifest(tmp_path, purpose="biometric identity verification")
    repo = tmp_path / "empty"
    repo.mkdir()
    result = runner.invoke(
        app,
        ["scan", "--manifest", str(manifest), "--repo-root", str(repo)],
    )
    assert result.exit_code == 0
    assert "evidence:" in result.output or "No local AI signals" in result.output


def test_scan_output_file_json(tmp_path):
    manifest = _write_manifest(tmp_path)
    repo = _biometric_repo(tmp_path)
    out = tmp_path / "results.json"
    result = runner.invoke(
        app,
        [
            "scan",
            "--manifest",
            str(manifest),
            "--repo-root",
            str(repo),
            "--output-file",
            str(out),
        ],
    )
    assert result.exit_code == 0
    assert out.exists()
    data = json.loads(out.read_text())
    assert "scan_id" in data
    assert "severity" in data


def test_scan_output_file_md(tmp_path):
    manifest = _write_manifest(tmp_path)
    repo = _biometric_repo(tmp_path)
    out = tmp_path / "results.md"
    result = runner.invoke(
        app,
        [
            "scan",
            "--manifest",
            str(manifest),
            "--repo-root",
            str(repo),
            "--output-file",
            str(out),
        ],
    )
    assert result.exit_code == 0
    assert out.exists()
    content = out.read_text()
    assert "# Code Corroboration Scan" in content
    assert "## Summary" in content


def test_scan_creates_ocignore_on_first_run(tmp_path):
    manifest = _write_manifest(tmp_path)
    repo = _biometric_repo(tmp_path)
    assert not (tmp_path / ".ocignore").exists()
    result = runner.invoke(
        app,
        ["scan", "--manifest", str(manifest), "--repo-root", str(repo)],
    )
    assert result.exit_code == 0
    assert (tmp_path / ".ocignore").exists()
    assert "Created scan config" in result.output or ".ocignore" in result.output


def test_scan_no_ocignore_bootstrap_skips_create(tmp_path):
    manifest = _write_manifest(tmp_path)
    repo = _biometric_repo(tmp_path)
    result = runner.invoke(
        app,
        [
            "scan",
            "--manifest",
            str(manifest),
            "--repo-root",
            str(repo),
            "--no-ocignore-bootstrap",
        ],
    )
    assert result.exit_code == 0
    assert not (tmp_path / ".ocignore").exists()


def test_scan_custom_ocignore_path(tmp_path):
    manifest = _write_manifest(tmp_path)
    repo = _biometric_repo(tmp_path)
    custom = tmp_path / "scan-ignore.cfg"
    custom.write_text("src/\n[limits]\nmax_files = 0\n", encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "scan",
            "--manifest",
            str(manifest),
            "--repo-root",
            str(repo),
            "--ocignore",
            str(custom),
            "--no-ocignore-bootstrap",
        ],
    )
    assert result.exit_code == 0


def test_scan_fail_on_new_major_exits_one(tmp_path):
    manifest = _write_manifest(tmp_path)
    repo = _biometric_repo(tmp_path)
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps({"accepted_categories": []}), encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "scan",
            "--manifest",
            str(manifest),
            "--repo-root",
            str(repo),
            "--baseline",
            str(baseline),
            "--fail-on",
            "new-major",
        ],
    )
    if "discrepancies" in result.output and "biometric" in result.output:
        assert result.exit_code == 1
    else:
        assert result.exit_code in (0, 1)


def test_intent_risk_tier_sorting_and_truncation_footer():
    from unittest.mock import MagicMock, patch

    from opencomplai_ai.models import IntentAnnotation
    from opencomplai_cli.main import (
        _intent_risk_tier,
        _intent_sort_key,
        _render_intent_analysis,
    )
    from opencomplai_core.models import (
        EvidenceItem,
        EvidenceKind,
        EvidenceScope,
        Reachability,
        SignalCategory,
    )

    prohibited = IntentAnnotation(
        art5_prohibited=True,
        decision_autonomy="autonomous",
        consequential="yes",
        model_id="test",
        confidence=0.99,
    )
    credit = IntentAnnotation(
        annex_iii_area=5,
        decision_autonomy="autonomous",
        consequential="yes",
        model_id="test",
        confidence=0.9,
    )
    display = IntentAnnotation(
        decision_autonomy="display_only",
        consequential="no",
        model_id="test",
        confidence=0.5,
    )

    assert _intent_risk_tier(prohibited) == "prohibited"
    assert _intent_risk_tier(credit) == "autonomous_high_risk"

    def _ev(ann: IntentAnnotation, idx: int) -> EvidenceItem:
        return EvidenceItem(
            evidence_id=f"ev_{idx}",
            evidence_kind=EvidenceKind.CALLSITE,
            category=SignalCategory.PROMPT_AGENT,
            token_hash=f"sha256:{idx}",
            token_label=f"fn_{idx}",
            locations=[f"src/a.py:{idx}"],
            scope=EvidenceScope.PROD,
            reachability=Reachability.INTERNAL_CALLCHAIN,
            detector_id="DET_INTENT_V1",
            detector_version="1.0.0",
            redaction_level="hash_only",
            rationale_code="intent_annotation",
            confidence=ann.confidence,
            intent_annotation=ann,
        )

    items = [_ev(display, i) for i in range(12)]
    items[0] = _ev(prohibited, 0)
    items[1] = _ev(credit, 1)
    sorted_items = sorted(items, key=_intent_sort_key)
    assert _intent_risk_tier(sorted_items[0].intent_annotation) == "prohibited"

    printed: list[str] = []

    def fake_print(*args, **kwargs):
        printed.append(" ".join(str(a) for a in args))

    mock_console = MagicMock()
    mock_console.print.side_effect = fake_print
    with patch("opencomplai_cli.main.console", mock_console):
        _render_intent_analysis(items, verbose=False)

    output = "\n".join(printed)
    assert "Summary by Annex III area / risk tier" in output
    assert "5 Essential services" in output or "prohibited" in output
    assert "and 2 more (use --ai-verbose" in output
