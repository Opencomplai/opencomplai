"""Failed pack rows are reported one by one in JUnit, SARIF and the summary."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import jsonschema
from opencomplai_core import ci_reports

SCHEMA = json.loads(
    (
        Path(__file__).resolve().parents[2]
        / "cli"
        / "tests"
        / "fixtures"
        / "sarif-2.1.0.subset.schema.json"
    ).read_text(encoding="utf-8")
)


def _row(rid: str, status: str, evidence: str, rationale: str) -> dict:
    return {
        "article": rid,
        "status": status,
        "evidence_ref": evidence,
        "rationale": rationale,
    }


def _artifact(**extra: object) -> dict:
    return {
        "system_id": "sys",
        "commit_ref": "abc",
        "result": "control_fail",
        "failed_controls": [
            "EU_AIA_ART6_HIGH_RISK",
            "GDPR:Art. 5",
            "GDPR:Art. 6",
            "NIS2:Art. 21",
        ],
        "framework_reports": {
            "GDPR": {
                "framework": "GDPR",
                "label": "GDPR",
                "report": {
                    "articles": [
                        _row("GDPR:Art. 5", "missing", "ROPA", "no register | found"),
                        _row("GDPR:Art. 6", "partial", "docs/lawful.md", "thin"),
                        _row("GDPR:Art. 7", "met", "docs/consent.md", "ok"),
                    ]
                },
            },
            "NIS2": {
                "framework": "NIS2",
                "label": "NIS2 Directive",
                "report": {
                    "articles": [_row("NIS2:Art. 21", "missing", "none", "gap")]
                },
            },
        },
        **extra,
    }


def test_failed_pack_rows_in_report_order():
    rows = ci_reports.failed_pack_rows(_artifact())
    assert [r["id"] for r in rows] == ["GDPR:Art. 5", "GDPR:Art. 6", "NIS2:Art. 21"]
    first = rows[0]
    assert first["framework"] == "GDPR"
    assert first["label"] == "GDPR"
    assert first["status"] == "missing"
    assert first["evidence_ref"] == "ROPA"
    assert first["title"]
    assert set(first) == {
        "id",
        "framework",
        "label",
        "title",
        "status",
        "evidence_ref",
        "rationale",
    }


def test_no_pack_rows_without_reports_or_artifact():
    assert ci_reports.failed_pack_rows(None) == []
    plain = {"result": "control_fail", "failed_controls": ["EU_AIA_ART6_HIGH_RISK"]}
    assert ci_reports.failed_pack_rows(plain) == []
    assert (
        ci_reports.failed_pack_rows({**plain, "failed_controls": ["GDPR:Art. 5"]}) == []
    )


def test_junit_has_one_testcase_per_row():
    suite = ET.fromstring(ci_reports.artifact_to_junit(_artifact()))
    assert suite.get("tests") == "4"
    cases = suite.findall("testcase")
    assert [c.get("name") for c in cases] == [
        "compliance-scan",
        "GDPR:Art. 5",
        "GDPR:Art. 6",
        "NIS2:Art. 21",
    ]
    assert [c.get("classname") for c in cases[1:]] == [
        "opencomplai.GDPR",
        "opencomplai.GDPR",
        "opencomplai.NIS2",
    ]
    failure = cases[1].find("failure")
    assert failure is not None
    assert failure.get("message", "").startswith("missing: ")
    assert failure.text == "no register | found (evidence: ROPA)"
    assert cases[3].find("failure").text == "gap (evidence: none)"


def test_sarif_has_one_result_per_row_and_validates():
    doc = ci_reports.artifact_to_sarif(_artifact())
    jsonschema.validate(doc, SCHEMA)
    run = doc["runs"][0]
    results = {r["ruleId"]: r for r in run["results"]}
    assert list(results) == [
        "EU_AIA_ART6_HIGH_RISK",
        "GDPR:Art. 5",
        "GDPR:Art. 6",
        "NIS2:Art. 21",
    ]
    assert len(run["results"]) == 4
    assert results["GDPR:Art. 5"]["level"] == "error"
    assert results["GDPR:Art. 6"]["level"] == "warning"
    assert results["GDPR:Art. 6"]["message"]["text"].endswith(": thin")
    assert results["GDPR:Art. 6"]["locations"] == results["NIS2:Art. 21"]["locations"]
    assert {r["id"] for r in run["tool"]["driver"]["rules"]} == set(results)


def test_summary_has_a_table_per_framework():
    md = ci_reports.artifact_to_summary_md(_artifact())
    head = "| Requirement | Title | Status | Evidence |"
    assert md.count(head) == 2
    assert md.index("### GDPR\n") < md.index("### NIS2 Directive\n")
    assert "| GDPR:Art. 5 | " in md
    assert "| missing | ROPA |" in md
    assert "| partial | docs/lawful.md |" in md
    assert "| NIS2:Art. 21 | " in md
    assert "| missing | none |" in md
    assert "no register" not in md  # rationale is not a column


def test_eu_only_artifact_is_unchanged():
    eu = {
        "system_id": "s",
        "commit_ref": "c",
        "result": "control_fail",
        "failed_controls": ["EU_AIA_ART6_HIGH_RISK"],
    }
    with_reports = {**eu, "framework_reports": _artifact()["framework_reports"]}
    assert ci_reports.artifact_to_junit(with_reports) == ci_reports.artifact_to_junit(
        eu
    )
    assert ci_reports.artifact_to_sarif(with_reports) == ci_reports.artifact_to_sarif(
        eu
    )
    assert ci_reports.artifact_to_summary_md(with_reports) == (
        ci_reports.artifact_to_summary_md(eu)
    )
    assert ET.fromstring(ci_reports.artifact_to_junit(eu)).get("tests") == "1"
