"""`opencomplai diff`: tool and scanner version changes."""

from __future__ import annotations

import json
from pathlib import Path

from opencomplai_cli.main import app
from opencomplai_core.models import (
    ArticleGapSource,
    ArticleGapStatus,
    GapReport,
    GapStatus,
)
from typer.testing import CliRunner

runner = CliRunner()
M, X = GapStatus.MET, GapStatus.MISSING
NOTE = "The tool changed between these runs"
BASE_KEYS = {
    "a", "b", "added", "removed", "changed", "unchanged_count",
    "regressions", "regression", "rule_set",
}  # fmt: skip


def _report(**statuses: GapStatus) -> dict:
    rows = [
        ArticleGapStatus(
            article=k.replace("_", " "),
            status=v,
            source=ArticleGapSource.RULE,
            evidence_ref="r",
        )
        for k, v in statuses.items()
    ]
    return json.loads(
        GapReport(
            system_id="sys", commit_ref="abc", generated_at="t", articles=rows
        ).model_dump_json()
    )


def _write(tmp_path: Path, name: str, obj) -> str:
    p = tmp_path / name
    p.write_text(json.dumps(obj), encoding="utf-8")
    return str(p)


def _artifact(rep: dict, **stamps) -> dict:
    return {"system_id": "sys", "gap_report": rep, **stamps}


def _run(*args):
    return runner.invoke(app, ["diff", *args])


def test_cli_version_only_change_is_tool_change_not_regression(tmp_path):
    rep = _report(Art_9=M)
    a = _write(tmp_path, "a.json", _artifact(rep, cli_version="0.9.0"))
    b = _write(tmp_path, "b.json", _artifact(rep, cli_version="0.9.1"))
    r = _run(a, b, "-o", "json", "--fail-on-regression")
    assert r.exit_code == 0, r.output
    d = json.loads(r.stdout)
    assert d["tool_changes"] == {
        "changed": True,
        "fields": [{"field": "cli_version", "from": "0.9.0", "to": "0.9.1"}],
    }
    assert d["regression"] is False
    assert d["regressions"] == []


def test_scanner_version_change_is_listed(tmp_path):
    rep = _report(Art_9=M)
    a = _write(
        tmp_path, "a.json", _artifact(rep, scan_summary={"scanner_version": "1"})
    )
    b = _write(
        tmp_path, "b.json", _artifact(rep, scan_summary={"scanner_version": "2"})
    )
    d = json.loads(_run(a, b, "-o", "json").stdout)
    assert d["tool_changes"]["fields"] == [
        {"field": "scanner_version", "from": "1", "to": "2"}
    ]
    human = _run(a, b).output
    assert "Tool changed" in human
    assert "scanner_version: 1 -> 2" in human


def test_json_tool_changes_is_additive(tmp_path):
    rep = _report(Art_9=M)
    sa = _write(tmp_path, "sa.json", _artifact(rep, cli_version="0.9.0"))
    sb = _write(tmp_path, "sb.json", _artifact(rep, cli_version="0.9.1"))
    ba = _write(tmp_path, "ba.json", rep)
    bb = _write(tmp_path, "bb.json", rep)
    for x, y in ((sa, sb), (ba, bb)):
        d = json.loads(_run(x, y, "-o", "json").stdout)
        assert set(d) == BASE_KEYS | {"tool_changes"}
    assert json.loads(_run(ba, bb, "-o", "json").stdout)["tool_changes"] == {
        "changed": None,
        "fields": [],
    }


def test_regression_with_tool_change_gets_note_and_same_exit_code(tmp_path):
    a = _write(tmp_path, "a.json", _artifact(_report(Art_9=M), cli_version="0.9.0"))
    b = _write(tmp_path, "b.json", _artifact(_report(Art_9=X), cli_version="0.9.1"))
    assert NOTE in _run(a, b).output
    md = _run(a, b, "-o", "markdown")
    assert md.exit_code == 0
    assert NOTE in md.stdout
    assert "## Tool changed" in md.stdout
    assert _run(a, b, "--fail-on-regression").exit_code == 1


def test_unstamped_inputs_claim_nothing(tmp_path):
    rep = _report(Art_9=M)
    bare = _write(tmp_path, "bare.json", rep)
    env = _write(tmp_path, "env.json", {"tool_version": "0", "payload": rep})
    r = _run(bare, env, "-o", "json")
    assert json.loads(r.stdout)["tool_changes"]["changed"] is None
    assert "Tool changed" not in _run(bare, env).output
    one = _write(tmp_path, "one.json", _artifact(rep, cli_version="0.9.0"))
    none = _write(tmp_path, "none.json", _artifact(rep))
    d = json.loads(_run(one, none, "-o", "json").stdout)
    assert d["tool_changes"] == {"changed": None, "fields": []}
    assert "Tool changed" not in _run(one, none, "-o", "markdown").stdout


def test_docs_describe_tool_changed_block():
    p = Path(__file__).resolve().parents[3] / "docs" / "src" / "cli" / "diff.md"
    text = p.read_text(encoding="utf-8")
    assert "Tool changed" in text
    assert "tool_changes" in text
