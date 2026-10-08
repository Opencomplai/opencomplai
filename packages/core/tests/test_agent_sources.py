"""Agent inventory sources for Art. 12, 14, 15 and 26 (declared versus detected)."""

from __future__ import annotations

import json

import pytest
from opencomplai_core.agent_sources import (
    AGENT_ARTICLES,
    AGENT_SOURCE_REF,
    Detected,
    agent_gap_status,
    cross_check,
    detected,
)
from opencomplai_core.gap_probes import STUB_SOURCE_REFS
from opencomplai_core.gap_report import build_gap_report, load_gap_article_map
from opencomplai_core.models import (
    ArticleGapSource,
    CorroborationReport,
    GapStatus,
    SystemManifest,
)

_BASE = {
    "system_id": "sys-1",
    "intended_purpose": "credit scoring",
    "compliance_target": "EU_AI_ACT",
    "high_risk_presumption": True,
    "commit_ref": "abc123",
    "training_data_description": "internal loan applications 2018-2024",
    "model_architecture": "gradient boosted trees",
    "operator_role": "provider",
}
_NAME = "zephyr-planner-7"
_AGENT = {
    "id": "agent-a1",
    "name": _NAME,
    "tools": [
        {"name": "approve-wire-9", "kind": "function", "requires_approval": True}
    ],
    "models": [{"provider": "OpenAI", "model": "gpt-x"}],
    "mandate": {"permitted_actions": ["tool:approve-wire-9"]},
    "guardrails": [{"kind": "output filter"}],
    "logging": {"decision_log_ref": "logs/decisions.jsonl"},
}
_OVERSIGHT = {"roles": [{"role": "Officer", "can_intervene": True}]}


def _manifest(agent: dict | None = None, *, oversight=_OVERSIGHT, **extra):
    agent = _AGENT if agent is None else agent
    return SystemManifest(
        **_BASE,
        agent_inventory={"agents": [agent]},
        **({"human_oversight": oversight} if oversight else {}),
        **extra,
    )


def _empty_inventory_manifest() -> SystemManifest:
    """agents=[] is rejected by the model, so build the inventory unvalidated."""
    manifest = _manifest()
    inventory = manifest.agent_inventory.model_construct(agents=[])
    return manifest.model_copy(update={"agent_inventory": inventory})


def _scan(*findings: tuple[str, str, str]) -> CorroborationReport:
    """findings: (signal_category, token_label, scope)."""
    evidence, items = [], []
    for n, (category, token, scope) in enumerate(findings):
        evidence.append(
            {
                "evidence_id": f"ev{n}",
                "evidence_kind": "import",
                "category": category,
                "token_hash": "h",
                "token_label": token,
                "locations": ["src/a.py:1"],
                "scope": scope,
                "reachability": "reachable_entrypoint",
                "detector_id": "d",
                "detector_version": "1",
                "redaction_level": "none",
                "rationale_code": "r",
                "confidence": 0.9,
            }
        )
        items.append(
            {
                "finding_id": f"f{n}",
                "signal_category": category,
                "evidence_ids": [f"ev{n}"],
                "locations": ["src/a.py:1"],
                "mapped_taxonomy": [],
                "strength": 1.0,
                "scope": scope,
                "reachability": "reachable_entrypoint",
                "confidence_rationale": [],
                "reviewer_prompt": "",
            }
        )
    return CorroborationReport.model_validate(
        {
            "scan_id": "s",
            "system_id": "sys-1",
            "commit_ref": "HEAD",
            "scanner_version": "0",
            "input_digest": "sha256:a",
            "config_hash": "sha256:b",
            "detector_versions": {},
            "declared_purpose": "x",
            "declared_categories": [],
            "evidence": evidence,
            "findings": items,
            "detected_categories": [],
            "discrepancies": [],
            "score_breakdown": {},
            "severity": "none",
            "feature_summary": {},
            "cache_summary": {},
            "skipped_paths": [],
            "limits_hit": [],
            "warnings": [],
            "detector_errors": [],
            "baseline_ref": None,
            "generated_at": "2026-07-11T00:00:00Z",
            "report_hash": "sha256:c",
        }
    )


_FRAMEWORK = ("agent_framework", "langgraph", "prod")
_MCP = ("mcp_server", "mcp", "prod")
_SDK = ("ai_sdk", "openai", "prod")


def _rows(manifest, scan=None):
    report = build_gap_report(
        "sys-1", "HEAD", manifest=manifest, corroboration_report=scan
    )
    return {r.article: r for r in report.articles if r.article in AGENT_ARTICLES}


def _status(article, manifest, scan=None):
    return agent_gap_status(article, manifest, scan)


def test_detected_but_undeclared_agent_framework_is_a_gap_row():
    rows = agent_gap_status_all(_empty_inventory_manifest(), _scan(_FRAMEWORK))
    assert set(rows) == set(AGENT_ARTICLES)
    for row in rows.values():
        assert row.status == GapStatus.MISSING
        assert row.source == ArticleGapSource.MANIFEST
        assert "agent framework" in row.rationale


def agent_gap_status_all(manifest, scan):
    return {a: agent_gap_status(a, manifest, scan) for a in AGENT_ARTICLES}


def test_declared_and_detected_agree_is_partial_never_met():
    scan = _scan(_FRAMEWORK, _MCP, _SDK)
    manifest = _manifest({**_AGENT, "tools": [{**_AGENT["tools"][0], "kind": "mcp"}]})
    for article in AGENT_ARTICLES:
        row = agent_gap_status(article, manifest, scan)
        assert row.status == GapStatus.PARTIAL, article
        assert row.confidence is None


def test_scan_finding_alone_never_produces_met():
    scan = _scan(_FRAMEWORK, _MCP, _SDK)
    for manifest in (_manifest(), _empty_inventory_manifest()):
        for row in _rows(manifest, scan).values():
            assert row.status != GapStatus.MET
    # a scan with no declaration at all leaves the rows alone
    plain = SystemManifest(**_BASE)
    assert all(r.status != GapStatus.MET for r in _rows(plain, scan).values())


def test_declared_but_never_detected_is_reported_not_punished():
    manifest = _manifest({**_AGENT, "tools": [{**_AGENT["tools"][0], "kind": "mcp"}]})
    row = agent_gap_status("Art. 15", manifest, _scan())
    assert row.status == GapStatus.PARTIAL
    for label in ("agent framework", "MCP server", "model provider"):
        assert label in row.rationale.split("Declared but not detected:")[1]


def test_art12_needs_a_decision_log_ref():
    bad = {**_AGENT, "logging": {"captures_intent": True}}
    assert agent_gap_status("Art. 12", _manifest(bad), None).status == GapStatus.MISSING
    assert agent_gap_status("Art. 12", _manifest(), None).status == GapStatus.PARTIAL


def test_art14_approval_tools_need_an_intervening_oversight_role():
    assert (
        agent_gap_status("Art. 14", _manifest(oversight=None), None).status
        == GapStatus.MISSING
    )
    no_power = {"roles": [{"role": "Observer", "can_intervene": False}]}
    assert (
        agent_gap_status("Art. 14", _manifest(oversight=no_power), None).status
        == GapStatus.MISSING
    )
    assert agent_gap_status("Art. 14", _manifest(), None).status == GapStatus.PARTIAL
    no_approval = {**_AGENT, "tools": [{"name": "t", "kind": "api"}]}
    assert (
        agent_gap_status("Art. 14", _manifest(no_approval, oversight=None), None).status
        == GapStatus.PARTIAL
    )


def test_art15_needs_guardrails():
    bad = {**_AGENT, "guardrails": []}
    assert agent_gap_status("Art. 15", _manifest(bad), None).status == GapStatus.MISSING
    assert agent_gap_status("Art. 15", _manifest(), None).status == GapStatus.PARTIAL


def test_art26_needs_a_mandate():
    for bad in (
        {**_AGENT, "mandate": None},
        {**_AGENT, "mandate": {"prohibited_actions": ["x"]}},
    ):
        row = agent_gap_status("Art. 26", _manifest(bad), None)
        assert row.status == GapStatus.MISSING
    assert agent_gap_status("Art. 26", _manifest(), None).status == GapStatus.PARTIAL


def test_no_inventory_means_report_unchanged():
    scan = _scan(_FRAMEWORK, _MCP)
    manifest = SystemManifest(**_BASE)
    with_manifest = build_gap_report(
        "s", "HEAD", manifest=manifest, corroboration_report=scan
    )
    without = build_gap_report("s", "HEAD", corroboration_report=scan)
    a = with_manifest.model_dump(mode="json") | {"generated_at": ""}
    b = without.model_dump(mode="json") | {"generated_at": ""}
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    assert agent_gap_status("Art. 12", manifest, scan) is None


def test_no_scan_report_skips_the_cross_check():
    row = agent_gap_status("Art. 15", _empty_inventory_manifest(), None)
    assert "not cross-checked" in row.rationale
    assert "Detected but not declared" not in row.rationale


def test_scope_filter_ignores_test_and_docs_findings():
    scan = _scan(
        ("agent_framework", "langgraph", "test"),
        ("mcp_server", "mcp", "docs"),
        ("ai_sdk", "openai", "vendor"),
        ("ai_sdk", "cohere", "generated"),
    )
    assert detected(scan) == Detected()
    assert detected(_scan(_FRAMEWORK, _MCP, _SDK)) == Detected(
        True, True, frozenset({"openai"})
    )


def test_cross_check_matches_providers_case_insensitively():
    inv = _manifest().agent_inventory
    assert (
        cross_check(inv, Detected(True, False, frozenset({"openai"}))).undeclared == []
    )
    assert (
        cross_check(inv, Detected(True, False, frozenset({"openai-sdk"}))).undeclared
        == []
    )
    result = cross_check(inv, Detected(True, False, frozenset({"cohere"})))
    assert result.undeclared == ["cohere"]
    assert "model provider" in result.unseen


def test_art14_agent_row_does_not_hide_an_artifact_missing(tmp_path):
    # human_oversight_construct artifact probe finds nothing -> MISSING; the
    # agent PARTIAL must not supersede it (no oversight block here: that one
    # has its own supersession rule).
    agent = {**_AGENT, "tools": [{"name": "t", "kind": "api"}]}
    report = build_gap_report(
        "s", "HEAD", manifest=_manifest(agent, oversight=None), repo_root=tmp_path
    )
    row = next(r for r in report.articles if r.article == "Art. 14")
    assert row.status == GapStatus.MISSING
    assert row.source == ArticleGapSource.ARTIFACT


def test_art14_with_oversight_and_agents_is_partial_never_met(tmp_path):
    report = build_gap_report("s", "HEAD", manifest=_manifest())
    row = next(r for r in report.articles if r.article == "Art. 14")
    assert row.status == GapStatus.PARTIAL
    assert row.source == ArticleGapSource.MANIFEST


def test_row_text_never_carries_declared_names():
    scan = _scan(_FRAMEWORK, _MCP, _SDK)
    report = build_gap_report(
        "s", "HEAD", manifest=_manifest(), corroboration_report=scan
    )
    dumped = report.model_dump_json()
    for secret in (_NAME, "agent-a1", "approve-wire-9", "gpt-x"):
        assert secret not in dumped


def test_map_lists_agent_ref_on_the_four_articles_and_never_first():
    amap = load_gap_article_map()
    for article in AGENT_ARTICLES:
        sources = amap[article]["sources"]
        assert {"kind": "manifest", "ref": AGENT_SOURCE_REF} in sources
        assert sources[0]["kind"] != "manifest"
    assert AGENT_SOURCE_REF not in STUB_SOURCE_REFS["manifest"]


@pytest.mark.parametrize("article", ["Art. 6", "Art. 9", "Art. 13"])
def test_other_articles_get_no_agent_row(article):
    assert agent_gap_status(article, _manifest(), None) is None
