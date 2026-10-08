"""Applicability (E-1): a recorded checker session can move articles out of gaps."""

from __future__ import annotations

import re

import pytest
from opencomplai_core.compliance_checker.catalog import load_obligations
from opencomplai_core.control_assessment import derive_controls
from opencomplai_core.control_catalog import get_catalog
from opencomplai_core.frameworks import EU_AI_ACT, evaluate_targets, gate_failures
from opencomplai_core.gap_report import (
    STATUS_SEVERITY,
    build_gap_report,
    load_gap_article_map,
)
from opencomplai_core.models import (
    CheckerSessionRef,
    ConfidenceLabel,
    FrameworkInputs,
    GapStatus,
    SystemManifest,
)
from opencomplai_core.nist_rmf_report import build_nist_rmf_report
from opencomplai_core.principle_report import build_principle_summary

PROVIDER_ONLY = ["Art. 9", "Art. 10", "Art. 11", "Art. 16", "Art. 17", "Art. 43"]
ALWAYS_PRESENT = ["Art. 4", "Art. 5", "Art. 6"]


def _session(*obligation_ids: str) -> CheckerSessionRef:
    return CheckerSessionRef(
        checker_version="checker-test",
        session_id="sess-1",
        completed_at="2026-09-18T00:00:00+00:00",
        obligation_ids=list(obligation_ids),
    )


def _manifest(session: CheckerSessionRef | None, **extra: object) -> SystemManifest:
    return SystemManifest(
        system_id="sys-1",
        intended_purpose="credit scoring",
        compliance_target="EU_AI_ACT",
        commit_ref="abc123",
        operator_role="deployer",
        checker_session=session,
        **extra,
    )


def _report(session: CheckerSessionRef | None):
    return build_gap_report(
        "sys-1", "abc123", manifest=_manifest(session), checker_session=session
    )


def _articles(report) -> set[str]:
    return {row.article for row in report.articles}


def test_deployer_session_moves_provider_only_articles_to_not_applicable():
    report = _report(_session("deployer_general", "ai_literacy"))
    for article in PROVIDER_ONLY:
        assert article not in _articles(report)
        assert report.not_applicable[article]
    for article in ALWAYS_PRESENT:
        assert article in _articles(report)


def test_provider_high_risk_session_keeps_provider_articles():
    report = _report(_session("provider_high_risk", "ai_literacy"))
    assert set(PROVIDER_ONLY) <= _articles(report)
    assert "Art. 9" not in report.not_applicable


def test_no_session_output_is_unchanged():
    plain = build_gap_report("sys-1", "abc123")
    with_kwargs = build_gap_report(
        "sys-1", "abc123", manifest=_manifest(None), checker_session=None
    )
    drop = {"generated_at"}
    assert plain.model_dump(exclude=drop) == with_kwargs.model_dump(exclude=drop)
    assert "not_applicable" not in with_kwargs.model_dump()
    assert _articles(with_kwargs) == set(load_gap_article_map())


def test_session_without_obligation_ids_changes_nothing():
    report = _report(_session())
    assert "not_applicable" not in report.model_dump()
    assert _articles(report) == set(load_gap_article_map())


def test_not_applicable_article_creates_no_control():
    session = _session("deployer_general")
    report = _report(session)
    controls = derive_controls(report, _manifest(session), get_catalog())
    ids = {c.obligation_id for c in controls}
    assert ids
    assert not ids & set(report.not_applicable)


def test_rollups_ignore_not_applicable_articles():
    manifest = _manifest(_session("deployer_general"))
    reports = evaluate_targets(
        manifest, [EU_AI_ACT, "NIST_AI_RMF"], commit_ref="abc123"
    )
    report = reports[EU_AI_ACT].report
    gone = set(report.not_applicable)
    assert gone

    # `principle.articles` lists the mapped articles; only present rows count.
    present = {row.article: row.status for row in report.articles}
    for principle in build_principle_summary(report).principles:
        counted = [present[a] for a in principle.articles if a in present]
        expected = (
            max(counted, key=lambda s: STATUS_SEVERITY[s])
            if counted
            else GapStatus.UNVERIFIED
        )
        assert principle.status == expected

    # An all-absent subcategory still names its mapped articles in an
    # unassessed row; rows that carry a verdict must not.
    for sub in build_nist_rmf_report(report).subcategories:
        if sub.confidence_label == ConfidenceLabel.HEURISTIC_ESTIMATE:
            assert not gone & set(sub.source_eu_ai_act_articles)

    for fail_on in ("missing", "partial"):
        assert not gone & set(gate_failures(reports, ["NIST_AI_RMF"], fail_on))


def test_eu_framework_inputs_are_still_rejected():
    manifest = _manifest(
        _session("deployer_general"),
        framework_inputs={EU_AI_ACT: FrameworkInputs(excluded={"Art. 9": "n/a"})},
    )
    with pytest.raises(ValueError, match="EU_AI_ACT"):
        evaluate_targets(manifest, [EU_AI_ACT], commit_ref="abc123")


def test_reason_has_no_dates_and_is_deterministic():
    first = _report(_session("deployer_general")).not_applicable
    second = _report(_session("deployer_general")).not_applicable
    assert first == second
    reason = first["Art. 9"]
    assert "provider_high_risk" in reason
    assert "sess-1" in reason
    assert "deployer" in reason
    assert not re.search(r"\d{4}-\d{2}-\d{2}|\bdays?\b|\bago\b", reason)


def _tagged() -> dict[str, dict]:
    return {a: c for a, c in load_gap_article_map().items() if "applies_when_any" in c}


def test_every_applies_when_any_id_is_a_known_obligation():
    known = set(load_obligations())
    tagged = _tagged()
    assert tagged
    for article, config in tagged.items():
        assert config["applies_when_any"], article
        assert set(config["applies_when_any"]) <= known, article


def test_every_applicability_entry_carries_source_confidence_and_review_flag():
    for article, config in _tagged().items():
        note = config["applicability_note"]
        assert note["source"], article
        assert note["confidence"] in {"low", "medium"}, article
        assert note["needs_founder_review"] is True, article
