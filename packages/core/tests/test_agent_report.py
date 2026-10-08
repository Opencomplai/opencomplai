"""Agent report: pure builder and Markdown renderer."""

from __future__ import annotations

import re

from opencomplai_core.agent_report import (
    build_agent_report,
    render_agent_report_markdown,
)
from opencomplai_core.agent_responsibility import get_responsibilities
from opencomplai_core.models import SystemManifest

_BASE = {
    "system_id": "sys-1",
    "intended_purpose": "credit scoring",
    "compliance_target": "EU_AI_ACT",
    "commit_ref": "abc123",
}
_AGENT = {
    "id": "a1",
    "name": "planner",
    "tools": [{"name": "search", "kind": "function"}],
    "models": [{"provider": "OpenAI", "model": "gpt-x"}],
    "mandate": {"permitted_actions": ["tool:search"]},
    "guardrails": [{"kind": "output filter"}],
}


def _manifest(*agents: dict, **inv) -> SystemManifest:
    return SystemManifest(**_BASE, agent_inventory={"agents": list(agents), **inv})


def test_report_is_deterministic():
    m = _manifest(_AGENT)
    a, b = build_agent_report(m), build_agent_report(m)
    assert a == b
    assert render_agent_report_markdown(a) == render_agent_report_markdown(b)


def test_markdown_marks_every_row_for_review():
    md = render_agent_report_markdown(build_agent_report(_manifest(_AGENT)))
    rows = [ln for ln in md.splitlines() if ln.startswith("- ") and "confidence:" in ln]
    assert len(rows) == len(get_responsibilities())
    assert all(
        "needs_founder_review: true" in ln and "confidence: low" in ln for ln in rows
    )


def test_report_without_scan_report_has_no_detected_findings():
    report = build_agent_report(_manifest(_AGENT))
    assert all(f["evidence"] != "detected" for f in report["findings"])
    assert report["findings"] == []


def test_report_with_no_inventory_block_is_empty_not_error():
    report = build_agent_report(SystemManifest(**_BASE))
    assert report["inventory"] == []
    assert report["findings"] == []
    assert len(report["responsibility_map"]["reference_rows"]) == len(
        get_responsibilities()
    )
    assert "No agent inventory declared." in render_agent_report_markdown(report)


def test_invalid_inventory_names_offending_id_and_no_date_text():
    bad = {**_AGENT, "parent_id": "ghost"}
    report = build_agent_report(_manifest(bad))
    assert [(f["kind"], f["id"]) for f in report["findings"]] == [
        ("invalid_inventory", "a1")
    ]
    md = render_agent_report_markdown(report)
    assert not re.search(r"\b\d{4}-\d{2}-\d{2}\b|\bdays?\b", md)
