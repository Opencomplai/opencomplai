"""File text that the CLI echoes (gate values, report parse errors, manifest key
names) cannot forge a line or be read as Rich markup (G-FIX-4)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from opencomplai_cli.main import app
from typer.testing import CliRunner

runner = CliRunner()
MARK = "MARKER-9c1d"


def _yaml(tmp_path: Path, text: str) -> None:
    (tmp_path / "opencomplai.yaml").write_text(text, encoding="utf-8")


@pytest.mark.parametrize(
    "text",
    [
        f'gate:\n  frameworks: ["[bold red]{MARK}[/]"]\n',
        f'gate:\n  frameworks: ["{MARK} x"]\n',
        f'gate:\n  fail_on: "[bold]{MARK}[/]"\n',
        f'gate:\n  fail_on: "{MARK}\\u001b[31m"\n',
    ],
    ids=["fw-markup", "fw-space", "fail-on-markup", "fail-on-escape"],
)
def test_a_gate_value_with_markup_or_controls_is_refused_at_load(
    tmp_path, monkeypatch, text
):
    monkeypatch.chdir(tmp_path)
    _yaml(tmp_path, text)
    result = runner.invoke(app, ["controls", "status", "--system-id", "s1"])
    assert result.exit_code == 2
    assert MARK not in result.output
    assert "\x1b" not in result.output


def test_a_scan_report_parse_failure_is_printed_as_plain_text(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "scan-report.json").write_text(
        json.dumps({"findings": f"[bold red]{MARK}[/]\x1b[31m"}), encoding="utf-8"
    )
    result = runner.invoke(
        app,
        ["docs", "generate", "--system-id", "s1", "--scan-report", "scan-report.json"],
    )
    err = result.stderr
    assert "failed to parse" in err
    assert "\x1b" not in err
    assert f"[bold red]{MARK}" in err  # shown literally, not eaten as markup


def test_an_unknown_manifest_key_name_has_its_controls_escaped(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init = runner.invoke(
        app,
        ["init", "--system-id", "s1", "--intended-purpose", "support bot"],
    )
    assert init.exit_code == 0, init.output
    manifest = tmp_path / "system-manifest.json"
    data = json.loads(manifest.read_text())
    data["bad\x1b[31mkey\nFORGED"] = 1
    manifest.write_text(json.dumps(data))
    result = runner.invoke(app, ["gaps", "--manifest", str(manifest), "-o", "json"])
    assert "\x1b" not in result.stderr
    assert "\nFORGED" not in result.stderr
    assert "\\x1b[31mkey\\nFORGED" in result.stderr
