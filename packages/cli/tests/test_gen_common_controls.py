from __future__ import annotations

import json

import typer
from opencomplai_cli.commands.generate import app
from typer.testing import CliRunner

runner = CliRunner()
# A lone command would collapse the group, so mount it under a parent.
_root = typer.Typer()
_root.add_typer(app, name="generate")


def _run(args):
    return runner.invoke(_root, ["generate", *args])


def test_json_output_parses():
    result = _run(["common-controls", "--output-format", "json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert data
    assert {"kind", "ref", "frameworks", "rows", "credited_rows"} <= set(data[0])


def test_min_frameworks_drops_single_framework_controls():
    base = ["common-controls", "--output-format", "json"]
    everything = json.loads(_run(base).stdout)
    shared = json.loads(_run([*base, "--min-frameworks", "2"]).stdout)
    assert all(len(c["frameworks"]) >= 2 for c in shared)
    expected = [c for c in everything if len(c["frameworks"]) >= 2]
    assert shared == expected


def test_human_output_has_header():
    result = _run(["common-controls"])
    assert result.exit_code == 0, result.output
    assert result.stdout.splitlines()[0].split() == [
        "ref",
        "kind",
        "frameworks",
        "rows",
    ]


def test_bad_artifact_exits_2(tmp_path):
    bad = tmp_path / "a.json"
    bad.write_text("not json", encoding="utf-8")
    result = _run(["common-controls", "--artifact", str(bad)])
    assert result.exit_code == 2
    missing = _run(["common-controls", "--artifact", str(tmp_path / "none.json")])
    assert missing.exit_code == 2
    assert "Got unexpected" not in missing.output


def test_artifact_is_accepted(tmp_path):
    art = tmp_path / "a.json"
    art.write_text(json.dumps({"gap_report": {"articles": []}}), encoding="utf-8")
    result = _run(
        ["common-controls", "--artifact", str(art), "--output-format", "json"]
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)
