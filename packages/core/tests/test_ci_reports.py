"""CI report renderers: pure functions of the artifact dict."""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET

import pytest
from opencomplai_core import ci_reports

GAP = {
    "generated_at": "2026-01-02T03:04:05+00:00",
    "articles": [
        {
            "article": "Art. 6",
            "status": "missing",
            "evidence_ref": "R6",
            "rationale": "why6",
        },
        {
            "article": "Art. 9",
            "status": "partial",
            "evidence_ref": "docs/r.md",
            "rationale": "",
        },
        {
            "article": "Art. 10",
            "status": "unverified",
            "evidence_ref": "none",
            "rationale": "r10",
        },
        {
            "article": "Art. 13",
            "status": "met",
            "evidence_ref": "I.md",
            "rationale": "ok",
        },
    ],
}
ART = {
    "system_id": "s1",
    "commit_ref": "abc1234",
    "result": "control_fail",
    "failed_controls": ["EU_AIA_ART6_HIGH_RISK", "EU_AIA_ART6_PROFILING"],
    "gap_report": GAP,
}


def _children(xml: str) -> list[str]:
    case = ET.fromstring(xml).find("testcase")
    return [c.tag for c in case]


@pytest.mark.parametrize(
    ("artifact", "expected"),
    [
        ({"result": "pass"}, []),
        ({"result": "control_fail", "failed_controls": ["A"]}, ["failure"]),
        ({"result": "trap_detected"}, ["failure"]),
        ({"result": "policy_block"}, ["failure"]),
        ({"result": "validation_fail"}, ["failure"]),
        (None, ["error"]),
    ],
)
def test_junit_cases_per_result(artifact, expected):
    xml = ci_reports.artifact_to_junit(artifact, "detail")
    root = ET.fromstring(xml)
    assert root.tag == "testsuite"
    assert root.get("tests") == "1"
    assert _children(xml) == expected
    if expected == ["failure"]:
        assert ET.fromstring(xml).find("testcase/failure").text == "detail"


def test_summary_md_rows():
    base = ci_reports.artifact_to_summary_md(
        {"result": "pass", "system_id": "s", "commit_ref": "c"}
    )
    assert "| Result | `pass` |" in base
    assert "| System | `s` |" in base
    assert "| Commit | `c` |" in base
    assert "Failed controls" not in base
    assert "Eval outcome" not in base
    failed = ci_reports.artifact_to_summary_md(ART)
    assert (
        "| Failed controls | `EU_AIA_ART6_HIGH_RISK, EU_AIA_ART6_PROFILING` |" in failed
    )
    nested = ci_reports.artifact_to_summary_md(
        {"eval_summary": {"overall_outcome": "fail"}}
    )
    flat = ci_reports.artifact_to_summary_md({"eval_overall_outcome": "pass"})
    assert "| Eval outcome | `fail` |" in nested
    assert "| Eval outcome | `pass` |" in flat


def test_sarif_levels_and_determinism():
    doc = ci_reports.artifact_to_sarif(ART, "m.json", tool_version="1.2.3")
    assert doc == ci_reports.artifact_to_sarif(ART, "m.json", tool_version="1.2.3")
    assert doc["version"] == "2.1.0"
    run = doc["runs"][0]
    assert run["tool"]["driver"]["version"] == "1.2.3"
    assert [(r["ruleId"], r["level"]) for r in run["results"]] == [
        ("EU_AIA_ART6_HIGH_RISK", "error"),
        ("EU_AIA_ART6_PROFILING", "error"),
        ("gap/R6", "error"),
        ("gap/docs/r.md", "warning"),
        ("gap/none", "note"),
    ]  # met omitted
    for r in run["results"]:
        loc = r["locations"][0]["physicalLocation"]
        assert loc["artifactLocation"]["uri"] == "m.json"
        assert loc["region"]["startLine"] == 1
    assert "why6" in run["results"][2]["message"]["text"]
    assert "Heuristic projection" in run["results"][2]["message"]["text"]
    assert run["properties"]["opencomplai_result"] == "control_fail"
    assert (
        "version" not in ci_reports.artifact_to_sarif(ART)["runs"][0]["tool"]["driver"]
    )
    ids = [r["id"] for r in run["tool"]["driver"]["rules"]]
    assert len(ids) == len(set(ids))


def test_sarif_pass_has_no_results():
    doc = ci_reports.artifact_to_sarif({"result": "pass", "system_id": "s"})
    assert doc["runs"][0]["results"] == []
    assert ci_reports.artifact_to_sarif({})["runs"][0]["results"] == []


def test_no_dates_in_outputs():
    outs = [
        ci_reports.artifact_to_junit(ART, "x"),
        ci_reports.artifact_to_summary_md(ART),
        json.dumps(ci_reports.artifact_to_sarif(ART)),
    ]
    for out in outs:
        assert "generated_at" not in out
        assert not re.search(r"\d{4}-\d{2}-\d{2}", out)


def test_connector_wrappers_delegate():
    from opencomplai_cli import connectors
    from opencomplai_cli.connectors import github_actions, gitlab_ci

    assert connectors.summarize_failed_controls is ci_reports.summarize_failed_controls
    assert gitlab_ci._build_junit_xml(ART, "out") == ci_reports.artifact_to_junit(
        ART, "out"
    )
    assert github_actions._build_summary(
        ART, "o", "e"
    ) == ci_reports.artifact_to_summary_md(ART)
    assert gitlab_ci._build_junit_xml(None, "") == ci_reports.artifact_to_junit(None)
