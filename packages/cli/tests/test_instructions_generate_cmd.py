"""CLI tests for `opencomplai instructions generate` (Art. 13(3))."""

from __future__ import annotations

import json
from pathlib import Path

from opencomplai_cli.main import app
from opencomplai_core.gap_report import build_gap_report
from opencomplai_core.models import SystemManifest
from typer.testing import CliRunner

runner = CliRunner()

ALWAYS_UNCAPTURED = ["b_iv", "b_v", "b_vii"]


def _write_manifest(tmp_path: Path, **extra: object) -> Path:
    manifest = SystemManifest(
        system_id="sys-1",
        intended_purpose="credit scoring",
        commit_ref="abc123",
        **extra,
    )
    path = tmp_path / "system-manifest.json"
    path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return path


def test_generate_writes_json_and_markdown(tmp_path: Path):
    manifest = _write_manifest(
        tmp_path,
        provider_contact="Acme AI",
        foreseeable_misuse=["used on minors"],
        input_data_specifications="PDF",
        predetermined_changes=["quarterly recalibration"],
        expected_lifetime_and_maintenance="5 years",
        log_interpretation="JSON lines",
        performance_metrics={"recall": 0.9},
        known_limitations=["thin files"],
        human_oversight_measures=["reviewer confirms denials"],
    )
    out = tmp_path / "out"
    result = runner.invoke(
        app,
        ["instructions", "generate", "-m", str(manifest), "--output-dir", str(out)],
    )
    assert result.exit_code == 0, result.output
    data = json.loads((out / "instructions_for_use.json").read_text(encoding="utf-8"))
    assert data["populated_point_count"] == 10
    assert data["not_captured_points"] == ALWAYS_UNCAPTURED
    assert (out / "instructions_for_use.md").exists()


def test_generate_on_minimal_manifest_marks_uncaptured_points(tmp_path: Path):
    manifest = _write_manifest(tmp_path)
    out = tmp_path / "out"
    result = runner.invoke(
        app,
        ["instructions", "generate", "-m", str(manifest), "--output-dir", str(out)],
    )
    assert result.exit_code == 0, result.output
    data = json.loads((out / "instructions_for_use.json").read_text(encoding="utf-8"))
    assert len(data["not_captured_points"]) == 12
    flat = " ".join(result.output.split())
    for pid in data["not_captured_points"]:
        assert f"not captured: {pid} " in flat


def test_generate_missing_manifest_exits_2(tmp_path: Path):
    result = runner.invoke(
        app, ["instructions", "generate", "-m", str(tmp_path / "nope.json")]
    )
    assert result.exit_code == 2


def test_generated_files_do_not_satisfy_deployer_instructions_probe(
    tmp_path: Path, monkeypatch
):
    def art13(root: Path):
        report = build_gap_report("s", "HEAD", repo_root=root)
        return next(r for r in report.articles if r.article == "Art. 13")

    before = art13(tmp_path)
    manifest = _write_manifest(tmp_path)
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["instructions", "generate", "-m", str(manifest)])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "instructions-for-use" / "instructions_for_use.md").exists()
    assert art13(tmp_path) == before


def test_docs_page_is_in_nav():
    root = Path(__file__).resolve().parents[3]
    assert (root / "docs" / "src" / "cli" / "instructions-generate.md").is_file()
    nav = (root / "docs" / "mkdocs.yml").read_text(encoding="utf-8")
    assert "cli/instructions-generate.md" in nav
