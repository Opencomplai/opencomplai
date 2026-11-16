from __future__ import annotations

import json
from pathlib import Path

import pytest
from opencomplai_cli.commands.generate import app
from typer.testing import CliRunner

runner = CliRunner()


@pytest.fixture(autouse=True)
def _two_commands():
    """Typer folds a one-command group into that command; keep a second one."""
    added = len(app.registered_commands) < 2
    if added:
        app.command("probe-noop")(lambda: None)
    yield
    if added:
        app.registered_commands.pop()


def _manifest(tmp_path: Path) -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps({"system_id": "sys-1", "intended_purpose": "Rank applicants"}),
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize("kind", ["ai-system", "dpia"])
def test_writes_markdown_and_json(tmp_path: Path, kind: str) -> None:
    out = tmp_path / "out"
    result = runner.invoke(
        app,
        [
            "impact-assessment",
            "--kind",
            kind,
            "--manifest",
            str(_manifest(tmp_path)),
            "--output-dir",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    md = out / f"impact_assessment_{kind}.md"
    data = json.loads((out / f"impact_assessment_{kind}.json").read_text("utf-8"))
    assert md.read_text("utf-8").startswith("Draft for review.")
    assert data["kind"] == kind


def test_unknown_kind_exits_2(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["impact-assessment", "--kind", "nope", "--manifest", str(_manifest(tmp_path))],
    )
    assert result.exit_code == 2


def test_bad_manifest_exits_2(tmp_path: Path) -> None:
    bad = tmp_path / "m.json"
    bad.write_text("{}", encoding="utf-8")
    result = runner.invoke(
        app, ["impact-assessment", "--kind", "dpia", "--manifest", str(bad)]
    )
    assert result.exit_code == 2
