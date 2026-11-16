"""OSCAL assessment-results export."""

from __future__ import annotations

import copy
import uuid

import pytest
from opencomplai_core.oscal_export import (
    build_assessment_results,
    control_token,
    to_json,
)


def _row(article: str, status: str, **extra: object) -> dict:
    row = {
        "article": article,
        "status": status,
        "source": "rule",
        "evidence_ref": f"R-{article}",
        "rationale": f"why {article}",
        "confidence_label": "heuristic_estimate",
    }
    row.update(extra)
    return row


def _artifact() -> dict:
    return {
        "system_id": "sys-1",
        "commit_ref": "abc123",
        "timestamp": "2026-01-02T03:04:05Z",
        "rule_set_version": "9.9",
        "gap_report": {
            "system_id": "sys-1",
            "commit_ref": "abc123",
            "generated_at": "2026-01-01T00:00:00Z",
            "articles": [
                _row("Art. 6", "met"),
                _row("Art. 9", "partial"),
                _row("Art. 10", "missing", rationale=""),
                _row("Art. 15", "unverified"),
            ],
            "not_applicable": {"Art. 50": "No user-facing interaction."},
        },
        "framework_reports": {
            "ISO_IEC_42001": {
                "label": "ISO/IEC 42001",
                "excluded": {"ISO_IEC_42001:A.7.1": "Out of scope."},
                "report": {
                    "articles": [_row("ISO_IEC_42001:A.6.2", "met")],
                },
            }
        },
    }


def _doc() -> dict:
    return build_assessment_results(_artifact())["assessment-results"]


def test_token_examples() -> None:
    assert control_token("Art. 6") == "art-6"
    assert control_token("ISO_IEC_42001:A.6.2") == "iso-iec-42001-a-6-2"


def test_two_results_and_metadata() -> None:
    doc = _doc()
    assert doc["metadata"]["oscal-version"] == "1.1.2"
    assert doc["metadata"]["version"] == "9.9"
    assert doc["metadata"]["last-modified"] == "2026-01-02T03:04:05Z"
    assert doc["import-ap"] == {"href": "#no-assessment-plan"}
    assert len(doc["results"]) == 2
    for result in doc["results"]:
        for key in ("uuid", "title", "description", "start", "reviewed-controls"):
            assert key in result


def test_last_modified_falls_back_to_gap_report() -> None:
    art = _artifact()
    del art["timestamp"]
    doc = build_assessment_results(art)["assessment-results"]
    assert doc["metadata"]["last-modified"] == "2026-01-01T00:00:00Z"


def test_state_mapping_and_props() -> None:
    findings = _doc()["results"][0]["findings"]
    states = {f["title"]: f["target"]["status"]["state"] for f in findings}
    assert states == {
        "Art. 6": "satisfied",
        "Art. 9": "not-satisfied",
        "Art. 10": "not-satisfied",
        "Art. 15": "not-satisfied",
    }
    partial = findings[1]
    assert partial["target"]["type"] == "objective-id"
    assert partial["target"]["target-id"] == "art-9"
    props = {p["name"]: p for p in partial["props"]}
    assert props["opencomplai-status"]["value"] == "partial"
    assert set(props) == {
        "opencomplai-status",
        "requirement-id",
        "source",
        "confidence-label",
        "evidence-ref",
    }
    assert all(p["ns"] == "https://opencomplai.com/ns/oscal" for p in props.values())
    assert findings[2]["description"] == "No rationale recorded."


def test_excluded_rows_have_no_finding() -> None:
    results = _doc()["results"]
    eu = results[0]["reviewed-controls"]["control-selections"][0]
    assert eu["exclude-controls"] == [
        {"control-id": "art-50", "remarks": "No user-facing interaction."}
    ]
    iso = results[1]["reviewed-controls"]["control-selections"][0]
    assert iso["exclude-controls"] == [
        {"control-id": "iso-iec-42001-a-7-1", "remarks": "Out of scope."}
    ]
    titles = [f["title"] for r in results for f in r["findings"]]
    assert "Art. 50" not in titles
    assert "ISO_IEC_42001:A.7.1" not in titles
    assert len(results[0]["findings"]) == 4


def test_stable_bytes_and_uuids() -> None:
    first = to_json(build_assessment_results(_artifact()))
    second = to_json(build_assessment_results(copy.deepcopy(_artifact())))
    assert first == second
    assert first.endswith("}\n")
    doc = _doc()
    ids = [doc["uuid"]]
    for result in doc["results"]:
        ids.append(result["uuid"])
        ids.extend(f["uuid"] for f in result["findings"])
    assert len(set(ids)) == len(ids)
    for value in ids:
        assert str(uuid.UUID(value)) == value


def test_no_gap_report_raises() -> None:
    with pytest.raises(ValueError, match="no gap report"):
        build_assessment_results({"system_id": "x"})
