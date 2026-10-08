"""`opencomplai docs generate --render`: Markdown/PDF next to the dossier JSON.

Local fallback only (no OPENCOMPLAI_API_URL). cwd and --output-dir are
tmp_path so nothing is written to the repo. The real dossier_id/generated_at
vary per run, so these tests assert markers, never whole-file equality.
"""

from __future__ import annotations

from pathlib import Path

from opencomplai_cli.main import app
from opencomplai_core.models import SystemManifest
from typer.testing import CliRunner

runner = CliRunner()

_SYSTEM_ID = "render-test"


def _run(tmp_path: Path, monkeypatch, *extra: str, high_risk: bool = True):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENCOMPLAI_API_URL", raising=False)
    manifest = tmp_path / "system-manifest.json"
    manifest.write_text(
        SystemManifest(
            system_id=_SYSTEM_ID,
            intended_purpose="Not specified",
            high_risk_presumption=high_risk,
            commit_ref="HEAD",
        ).model_dump_json(indent=2)
    )
    out = tmp_path / "out"
    result = runner.invoke(
        app,
        [
            "docs",
            "generate",
            "--system-id",
            _SYSTEM_ID,
            "--manifest",
            str(manifest),
            "--output-dir",
            str(out),
            *extra,
        ],
    )
    return result, out


def _one(out: Path, pattern: str) -> Path:
    files = list(out.glob(pattern))
    assert len(files) == 1, files
    return files[0]


def test_incomplete_high_risk_exits_2_and_marks_incomplete(tmp_path, monkeypatch):
    result, out = _run(tmp_path, monkeypatch, "--render", "md", "--render", "pdf")
    assert result.exit_code == 2, result.output
    md = _one(out, "dossier_*.md").read_text(encoding="utf-8")
    assert "INCOMPLETE" in md
    assert "NOT PROVIDED" in md
    assert _one(out, "dossier_*.pdf").read_bytes().startswith(b"%PDF")
    assert _one(out, "dossier_*.json")


def test_allow_incomplete_exits_0_but_still_marks_incomplete(tmp_path, monkeypatch):
    result, out = _run(tmp_path, monkeypatch, "--render", "md", "--allow-incomplete")
    assert result.exit_code == 0, result.output
    assert "INCOMPLETE" in _one(out, "dossier_*.md").read_text(encoding="utf-8")


def test_complete_dossier_renders_and_exits_0(tmp_path, monkeypatch):
    result, out = _run(tmp_path, monkeypatch, "--render", "md", high_risk=False)
    assert result.exit_code == 0, result.output
    md = _one(out, "dossier_*.md").read_text(encoding="utf-8")
    assert "INCOMPLETE" not in md
    assert "No completeness gap flagged by the dossier" in md


def test_no_render_flag_writes_json_only(tmp_path, monkeypatch):
    result, out = _run(tmp_path, monkeypatch, "--allow-incomplete")
    assert result.exit_code == 0, result.output
    assert sorted(p.suffix for p in out.iterdir()) == [".json"]


def test_bad_render_value_exits_2_writes_nothing(tmp_path, monkeypatch):
    result, out = _run(tmp_path, monkeypatch, "--render", "html")
    assert result.exit_code == 2, result.output
    assert not out.exists()
