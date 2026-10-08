"""`opencomplai rules changelog`."""

from __future__ import annotations

import json

from opencomplai_cli.main import app
from opencomplai_core.rules import RULE_SET_VERSION
from typer.testing import CliRunner

runner = CliRunner()


def test_changelog_json_last_entry_is_rule_set_version():
    r = runner.invoke(app, ["rules", "changelog", "-o", "json"])
    assert r.exit_code == 0
    assert json.loads(r.stdout)[-1]["version"] == RULE_SET_VERSION


def test_since_filters_and_rejects_bad_version():
    r = runner.invoke(app, ["rules", "changelog", "--since", "1.5.0", "-o", "json"])
    assert r.exit_code == 0
    versions = [e["version"] for e in json.loads(r.stdout)]
    assert "1.5.0" not in versions
    assert versions[-1] == RULE_SET_VERSION
    assert (
        runner.invoke(app, ["rules", "changelog", "--since", "banana"]).exit_code == 2
    )


def test_changelog_human_and_markdown_show_source_and_review_flag():
    entries = json.loads(
        runner.invoke(app, ["rules", "changelog", "-o", "json"]).stdout
    )
    flagged = [e for e in entries if e["needs_founder_review"]]
    for fmt in ("human", "markdown"):
        out = runner.invoke(app, ["rules", "changelog", "-o", fmt]).stdout
        for e in entries:
            assert e["version"] in out
            assert e["source"].split()[0] in out
            assert e["confidence"] in out
        if flagged:
            assert "needs founder review" in out
