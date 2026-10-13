"""Scan display snippets resolve against the repo root, not the process cwd."""

from __future__ import annotations

from itertools import pairwise
from pathlib import Path

import opencomplai_cli.main as cli_main
from opencomplai_cli.commands.snippet import read_display_snippet
from opencomplai_cli.main import app
from typer.testing import CliRunner

runner = CliRunner()
ENV = {"COLUMNS": "300"}


def _setup(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "requirements.txt").write_text("face_recognition\n", encoding="utf-8")
    (repo / "src" / "face.py").write_text("import face_recognition\n", encoding="utf-8")
    manifest = repo / "system-manifest.json"
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
        ],
    )
    assert result.exit_code == 0
    return repo, manifest


def _scan(repo: Path, manifest: Path):
    return runner.invoke(
        app,
        [
            "scan",
            "--manifest",
            str(manifest),
            "--repo-root",
            str(repo),
            "--no-ocignore-bootstrap",
        ],
        env=ENV,
    )


def _snippet_lines(output: str) -> list[str]:
    """Lines printed with the six-space snippet indent right after a location."""
    lines = output.splitlines()
    return [
        cur.strip()
        for prev, cur in pairwise(lines)
        if ".py:" in prev and cur.startswith("      ") and not cur.startswith("       ")
    ]


def test_scan_snippets_same_from_foreign_cwd(tmp_path, monkeypatch):
    repo, manifest = _setup(tmp_path)
    other = tmp_path / "other"
    other.mkdir()

    monkeypatch.chdir(repo)
    here = _scan(repo, manifest)
    monkeypatch.chdir(other)
    away = _scan(repo, manifest)

    assert here.exit_code == 0
    assert away.exit_code == 0
    snippets_here = _snippet_lines(here.output)
    assert any("import face_recognition" in s for s in snippets_here)
    assert _snippet_lines(away.output) == snippets_here


def test_unreadable_snippet_prints_nothing_and_succeeds(tmp_path, monkeypatch):
    repo, manifest = _setup(tmp_path)
    real = cli_main._run_scan_corroboration

    def run_then_delete(*args, **kwargs):
        out = real(*args, **kwargs)
        (repo / "src" / "face.py").unlink()
        return out

    monkeypatch.setattr(cli_main, "_run_scan_corroboration", run_then_delete)
    result = _scan(repo, manifest)

    assert result.exit_code == 0
    assert "face.py" in result.output
    assert not any(
        "import face_recognition" in s for s in _snippet_lines(result.output)
    )


def test_helper_returns_none_when_unreadable(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "adir").mkdir()
    assert read_display_snippet("missing.py:1", tmp_path) is None
    assert read_display_snippet("adir:1", tmp_path) is None
    assert read_display_snippet("a.py:9", tmp_path) is None
    assert read_display_snippet("a.py:0", tmp_path) is None
    assert read_display_snippet("pkg.json:dep", tmp_path) is None
    assert read_display_snippet("nocolon", tmp_path) is None


def test_helper_resolves_against_root(tmp_path, monkeypatch):
    root = tmp_path / "root"
    root.mkdir()
    (root / "a.py").write_text("    " + "y" * 100 + "\n", encoding="utf-8")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    assert read_display_snippet("a.py:1", root) == "y" * 76
    assert read_display_snippet("a.py:1") is None
    assert read_display_snippet(f"{root / 'a.py'}:1") == "y" * 76
