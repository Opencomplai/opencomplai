"""`opencomplai generate oscal`."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from opencomplai_cli.commands.gen_oscal import oscal
from typer.testing import CliRunner

runner = CliRunner()

# Typer collapses a one-command group, so mount the real command next to a
# second one; the registered `generate` group has several generators.
app = typer.Typer()
app.command("oscal")(oscal)
app.command("other")(lambda: None)


def _write(path: Path, data: dict) -> Path:
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_out_writes_document(tmp_path: Path) -> None:
    art = _write(
        tmp_path / "a.json",
        {
            "system_id": "s",
            "commit_ref": "c",
            "timestamp": "2026-01-01T00:00:00Z",
            "gap_report": {
                "articles": [
                    {"article": "Art. 6", "status": "met", "evidence_ref": "R"}
                ]
            },
        },
    )
    out = tmp_path / "o.json"
    result = runner.invoke(app, ["oscal", str(art), "--out", str(out)])
    assert result.exit_code == 0, result.output
    doc = json.loads(out.read_text(encoding="utf-8"))["assessment-results"]
    assert doc["metadata"]["oscal-version"] == "1.1.2"
    assert doc["results"][0]["findings"][0]["target"]["target-id"] == "art-6"


def test_no_gap_report_exits_2(tmp_path: Path) -> None:
    art = _write(tmp_path / "a.json", {"system_id": "s"})
    result = runner.invoke(app, ["oscal", str(art)])
    assert result.exit_code == 2
    assert "artifact has no gap report; run check --with-gaps" in result.output
