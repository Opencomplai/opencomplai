from __future__ import annotations

import json
from pathlib import Path

import pytest
from opencomplai_cli.commands import generate
from opencomplai_cli.commands.generate import app
from typer.testing import CliRunner

MANIFEST = {
    "system_id": "demo",
    "intended_purpose": "Triage",
    "performance_metrics": {"imdb/accuracy": 0.9},
}


@pytest.fixture(autouse=True)
def _group_level(monkeypatch: pytest.MonkeyPatch) -> None:
    # Typer collapses a one-command app into the command itself, and the other
    # generator modules do not exist yet: add a probe command on a copy.
    monkeypatch.setattr(
        generate.app, "registered_commands", list(generate.app.registered_commands)
    )

    @generate.app.command("probe")
    def _probe() -> None:
        """Probe."""


def _write(tmp_path: Path) -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(MANIFEST), encoding="utf-8")
    return path


def test_writes_card(tmp_path: Path) -> None:
    out = tmp_path / "MODEL_CARD.md"
    result = CliRunner().invoke(
        app, ["model-card", "--manifest", str(_write(tmp_path)), "--output", str(out)]
    )
    assert result.exit_code == 0, result.output
    text = out.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "## Intended use" in text


def test_missing_manifest_exits_2(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app,
        [
            "model-card",
            "--manifest",
            str(tmp_path / "none.json"),
            "--output",
            str(tmp_path / "o.md"),
        ],
    )
    assert result.exit_code == 2
    assert not (tmp_path / "o.md").exists()


def test_invalid_manifest_exits_2(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    result = CliRunner().invoke(
        app, ["model-card", "--manifest", str(bad), "--output", str(tmp_path / "o.md")]
    )
    assert result.exit_code == 2


def test_json_format_parses(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app,
        [
            "model-card",
            "--manifest",
            str(_write(tmp_path)),
            "--output",
            str(tmp_path / "o.md"),
            "--output-format",
            "json",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["system_id"] == "demo"
    assert len(payload["sections"]) == 9
    assert payload["metrics"] == {"imdb/accuracy": 0.9}
