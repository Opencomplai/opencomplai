"""`opencomplai diff`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from opencomplai_cli.main import app
from opencomplai_core.models import (
    ArticleGapSource,
    ArticleGapStatus,
    GapReport,
    GapStatus,
)
from typer.testing import CliRunner

runner = CliRunner()
M, P, X = GapStatus.MET, GapStatus.PARTIAL, GapStatus.MISSING


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


def _artifact(rep: dict, rule_set: str | None = None) -> dict:
    d = {"system_id": "sys", "gap_report": rep}
    if rule_set:
        d["rule_set_version"] = rule_set
    return d


def _envelope(rep: dict) -> dict:
    return {"tool_version": "0", "payload": rep}


def _run(*args):
    return runner.invoke(app, ["diff", *args])


def test_diff_accepts_artifact_envelope_and_bare_gap_report(tmp_path):
    old = _report(Art_9=M, Art_10=P)
    new = _report(Art_9=M, Art_10=X, Art_11=P)
    shapes = [
        lambda r: _artifact(r),
        _envelope,
        lambda r: r,
    ]
    for i, shape in enumerate(shapes):
        a = _write(tmp_path, f"a{i}.json", shape(old))
        b = _write(tmp_path, f"b{i}.json", shape(new))
        r = _run(a, b, "-o", "json")
        assert r.exit_code == 0, r.output
        d = json.loads(r.stdout)
        assert d["added"] == [{"article": "Art 11", "status": "partial"}]
        assert d["changed"][0]["from"] == "partial"
        assert d["changed"][0]["to"] == "missing"
        assert d["b"]["system_id"] == "sys"
        assert d["a"]["commit_ref"] == "abc"


def test_diff_json_rule_set_block(tmp_path):
    rep = _report(Art_9=M)
    cases = [
        (_artifact(rep, "1.5.0"), _artifact(rep, "1.6.0"), True),
        (_artifact(rep, "1.6.0"), _artifact(rep, "1.6.0"), False),
        (_artifact(rep), _artifact(rep, "1.6.0"), None),
        (rep, rep, None),
    ]
    for i, (x, y, expect) in enumerate(cases):
        r = _run(
            _write(tmp_path, f"x{i}.json", x),
            _write(tmp_path, f"y{i}.json", y),
            "-o",
            "json",
        )
        assert r.exit_code == 0
        assert json.loads(r.stdout)["rule_set"]["changed"] is expect
    r = _run(
        _write(tmp_path, "k1.json", cases[0][0]),
        _write(tmp_path, "k2.json", cases[0][1]),
        "-o",
        "json",
    )
    assert json.loads(r.stdout)["rule_set"]["changes"][0]["version"] == "1.6.0"


def test_diff_three_output_formats(tmp_path):
    a = _write(tmp_path, "a.json", _report(Art_9=M, Art_10=P))
    b = _write(tmp_path, "b.json", _report(Art_9=X, Art_12=M))
    human = _run(a, b)
    md = _run(a, b, "-o", "markdown")
    js = _run(a, b, "-o", "json")
    assert human.exit_code == md.exit_code == js.exit_code == 0
    assert "Art 9" in human.stdout
    assert "unknown" in human.stdout
    assert "## Changed" in md.stdout
    assert "| Art 9 | met | missing | worse |" in md.stdout
    assert "## Removed" in md.stdout
    assert "## Added" in md.stdout
    assert json.loads(js.stdout)["regressions"] == ["Art 9"]


@pytest.mark.parametrize("fmt", ["human", "json", "markdown"])
def test_fail_on_regression_exits_1_in_every_format(tmp_path, fmt):
    a = _write(tmp_path, "a.json", _report(Art_9=M))
    b = _write(tmp_path, "b.json", _report(Art_9=P))
    r = _run(a, b, "-o", fmt, "--fail-on-regression")
    assert r.exit_code == 1
    assert "Art 9" in r.stdout  # still rendered before exiting


def test_improvement_or_no_change_exits_0_with_flag(tmp_path):
    worse = _write(tmp_path, "w.json", _report(Art_9=X))
    better = _write(tmp_path, "b.json", _report(Art_9=M))
    assert _run(worse, better, "--fail-on-regression").exit_code == 0
    assert _run(better, better, "--fail-on-regression").exit_code == 0


def test_without_flag_a_regression_still_exits_0(tmp_path):
    a = _write(tmp_path, "a.json", _report(Art_9=M))
    b = _write(tmp_path, "b.json", _report(Art_9=X))
    assert _run(a, b).exit_code == 0


def test_artifact_without_gap_report_exits_2(tmp_path):
    ok = _write(tmp_path, "ok.json", _report(Art_9=M))
    bare = _write(tmp_path, "art.json", {"system_id": "s", "gap_report": None})
    r = _run(ok, bare)
    assert r.exit_code == 2
    assert "check --with-gaps" in " ".join(r.output.split())


def test_missing_or_invalid_file_exits_2(tmp_path):
    ok = _write(tmp_path, "ok.json", _report(Art_9=M))
    junk = tmp_path / "junk.json"
    junk.write_text("not json", encoding="utf-8")
    wrong = _write(tmp_path, "wrong.json", {"hello": 1})
    assert _run(ok, str(tmp_path / "nope.json")).exit_code == 2
    assert _run(ok, str(junk)).exit_code == 2
    assert _run(ok, wrong).exit_code == 2


def test_exit_codes_are_only_0_1_2(tmp_path):
    a = _write(tmp_path, "a.json", _report(Art_9=M))
    b = _write(tmp_path, "b.json", _report(Art_9=X))
    codes = {
        _run(a, b).exit_code,
        _run(a, b, "--fail-on-regression").exit_code,
        _run(a, str(tmp_path / "missing.json")).exit_code,
        _run(a, b, "-o", "yaml").exit_code,  # usage error, click maps to 2
    }
    assert codes == {0, 1, 2}


def test_diff_is_registered_and_readme_row_exists():
    assert "diff" in {c.name for c in app.registered_commands}
    readme = (Path(__file__).resolve().parents[1] / "README.md").read_text(
        encoding="utf-8"
    )
    assert "| `opencomplai diff` |" in readme
