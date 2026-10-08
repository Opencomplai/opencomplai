"""`agents import-log` and `agents dispute-report`: offline, exit 0 or 2 only."""

from __future__ import annotations

import json
from pathlib import Path

from opencomplai_cli.main import app
from typer.testing import CliRunner

runner = CliRunner()
FIX = Path(__file__).parents[2] / "core" / "tests" / "fixtures" / "agt_audit"
AGT = str(FIX / "sample_agt.jsonl")
NATIVE = str(FIX / "sample_native.jsonl")


def _run(*args):
    return runner.invoke(app, ["agents", *args])


def test_import_human_output_shows_partial_and_integrity_label():
    res = _run("import-log", AGT)
    assert res.exit_code == 0, res.output
    assert "PARTIAL" in res.output
    assert "format-valid, not verified" in res.output
    assert "mapped: 6, rejected: 1" in res.output
    assert "rejected line 3" in res.output


def test_import_json_output_status_partial():
    res = _run("import-log", AGT, "--format", "json")
    assert res.exit_code == 0, res.output
    body = json.loads(res.output)
    assert body["status"] == "partial"
    assert body["integrity"] == "format-valid, not verified"
    assert (body["mapped"], body["rejected"]) == (6, 1)
    assert "records" not in body


def test_import_exit_zero_even_with_rejected_lines(tmp_path):
    p = tmp_path / "junk.jsonl"
    p.write_text("junk\n[1]\n")
    res = _run("import-log", str(p))
    assert res.exit_code == 0
    assert "UNVERIFIED" in res.output
    assert "rejected: 2" in res.output
    empty = tmp_path / "empty.jsonl"
    empty.write_text("")
    assert _run("import-log", str(empty)).exit_code == 0


def test_import_exit_two_only_on_usage_errors(tmp_path):
    assert _run("import-log", str(tmp_path / "missing.jsonl")).exit_code == 2
    assert _run("import-log", AGT, "--map", "nonsense").exit_code == 2
    assert _run("import-log", AGT, "--map", "bogus=a.b").exit_code == 2
    assert _run("import-log", AGT, "--source", "other").exit_code == 2
    assert _run("import-log", AGT, "--source", "native").exit_code == 2
    assert _run("import-log", str(tmp_path)).exit_code == 2


def test_import_map_changes_extraction(tmp_path):
    p = tmp_path / "custom.jsonl"
    p.write_text('{"stamp": "2026-03-01T00:00:00Z", "verb": "run"}\n')
    assert (
        json.loads(_run("import-log", str(p), "--format", "json").output)["mapped"] == 0
    )
    res = _run(
        "import-log",
        str(p),
        "--map",
        "ts=stamp",
        "--map",
        "action=verb",
        "--format",
        "json",
    )
    assert json.loads(res.output)["mapped"] == 1


def test_import_output_file(tmp_path):
    out = tmp_path / "o.json"
    res = _run("import-log", AGT, "--format", "json", "--output", str(out))
    assert res.exit_code == 0
    assert res.output == ""
    assert b"\r" not in out.read_bytes()
    assert json.loads(out.read_text(encoding="utf-8"))["status"] == "partial"


def test_dispute_report_cli_renders_fixture(tmp_path):
    args = (
        "dispute-report",
        "--log",
        AGT,
        "--from",
        "2026-03-01",
        "--to",
        "2026-03-03",
    )
    res = _run(*args)
    assert res.exit_code == 0, res.output
    assert "# Agent dispute report" in res.output
    assert "6 in window" in res.output
    assert "agent-alpha" in res.output
    narrow = _run(
        "dispute-report", "--log", AGT, "--from", "2026-03-02", "--to", "2026-03-02"
    )
    assert "2 in window" in narrow.output
    out = tmp_path / "r.md"
    assert _run(*args, "--output", str(out)).exit_code == 0
    assert out.read_text(encoding="utf-8") == res.output
    js = _run(*args, "--format", "json", "--agent", "agent-beta")
    assert json.loads(js.output)["counts"]["in_window"] == 3


def test_dispute_report_requires_from_and_to():
    assert _run("dispute-report", "--log", AGT, "--to", "2026-03-03").exit_code == 2
    assert _run("dispute-report", "--log", AGT, "--from", "2026-03-01").exit_code == 2
    base = ("dispute-report", "--log", AGT)
    assert _run(*base, "--from", "bad", "--to", "2026-03-03").exit_code == 2
    assert _run(*base, "--from", "2026-03-04", "--to", "2026-03-03").exit_code == 2
    assert (
        _run(
            *base, "--from", "2026-03-01", "--to", "2026-03-03", "--source", "x"
        ).exit_code
        == 2
    )


def test_dispute_report_native_source():
    res = _run(
        "dispute-report", "--log", NATIVE, "--source", "native",
        "--from", "2026-03-01", "--to", "2026-03-03",
    )  # fmt: skip
    assert res.exit_code == 0, res.output
    assert "5 in window" in res.output
    assert "agents verify-log" in res.output
    assert "| yes |" in res.output
    bad = _run(
        "dispute-report", "--log", NATIVE, "--source", "native", "--map", "ts=x",
        "--from", "2026-03-01", "--to", "2026-03-03",
    )  # fmt: skip
    assert bad.exit_code == 2


def test_commands_listed_in_agents_help():
    res = _run("--help")
    assert res.exit_code == 0
    assert "import-log" in res.output
    assert "dispute-report" in res.output


def test_other_exit_codes_unaffected(tmp_path):
    good = tmp_path / "m.json"
    init = [
        "init",
        "--system-id",
        "s1",
        "--intended-purpose",
        "customer support chatbot",
    ]
    assert runner.invoke(app, [*init, "--output", str(good)]).exit_code == 0
    assert runner.invoke(app, ["validate-manifest", str(good)]).exit_code == 0
    assert runner.invoke(app, ["validate-manifest", "nonexistent.json"]).exit_code == 2
