"""Terminal block for import candidates: leads, listed apart, never counted."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from opencomplai_cli.main import _render_eu_ai_scan, app
from opencomplai_core import scan_engine
from opencomplai_core.models import (
    CorroborationReport,
    DiscrepancySeverity,
    EuAiCandidate,
    EuAiScanSummary,
    EuAiUsageEntry,
    SystemManifest,
)
from typer.testing import CliRunner

runner = CliRunner()

_HEADING = "Candidates (leads for a person, not findings)"


def _report(candidates: list[EuAiCandidate]) -> CorroborationReport:
    return CorroborationReport(
        scan_id="scan_test",
        system_id="test",
        commit_ref="HEAD",
        scanner_version="0.1.0",
        input_digest="abc",
        config_hash="def",
        detector_versions={},
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
            gated_callsite_count=1,
            candidates=candidates,
        ),
    )


def _rendered(report: CorroborationReport) -> list[str]:
    printed: list[str] = []
    mock_console = MagicMock()
    mock_console.print.side_effect = lambda *a, **k: printed.append(
        " ".join(str(x) for x in a)
    )
    with patch("opencomplai_cli.main.console", mock_console):
        _render_eu_ai_scan(report, verbose=False)
    return printed


_CANDIDATE = EuAiCandidate(library="retinaface", file="src/face.py", line=3)


def test_candidates_section_printed_when_present():
    out = "\n".join(_rendered(_report([_CANDIDATE])))
    assert _HEADING in out
    assert "retinaface" in out
    assert "src/face.py:3" in out
    assert "imported_not_classified" in out
    assert "[red]" not in out
    assert "[yellow]" not in out


def test_no_section_and_unchanged_output_when_empty():
    without = _rendered(_report([]))
    assert not any("Candidates" in line for line in without)
    with_block = _rendered(_report([_CANDIDATE]))
    # The block is appended after everything printed today.
    assert with_block[: len(without)] == without
    assert len(with_block) > len(without)


def test_section_does_not_change_exit_code(tmp_path, monkeypatch):
    manifest = tmp_path / "system-manifest.json"
    manifest.write_text(
        SystemManifest(
            system_id="cand-sys", intended_purpose="customer support chatbot"
        ).model_dump_json(),
        encoding="utf-8",
    )
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "face.py").write_text("import retinaface\n", encoding="utf-8")

    def scan():
        return runner.invoke(
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
                "--fail-on",
                "major",
            ],
        )

    with_block = scan()
    assert _HEADING in with_block.output, with_block.output
    assert "src/face.py:1" in with_block.output

    monkeypatch.setattr(scan_engine, "find_import_candidates", lambda *a, **k: [])
    without = scan()
    assert _HEADING not in without.output
    assert without.exit_code == with_block.exit_code == 0
