"""An imported provider pack is read in the Art. 26 deployer row (Partial at most)."""

from __future__ import annotations

from datetime import date

import pytest
from opencomplai_core.gap_report import build_gap_report
from opencomplai_core.models import (
    ArticleGapSource,
    CheckerSessionRef,
    GapStatus,
    SystemManifest,
)

REASON = "provider-supplied, not verified by the deployer"
_PROVIDER_ID = "provider-sys-secret-77"
_FILE = "acme-secret-pack.json"
_SHA = "ab" * 32
_TODAY = date(2026, 10, 11)
_SESSION = CheckerSessionRef(
    checker_version="checker-test",
    session_id="sess-1",
    completed_at="2026-09-18T00:00:00+00:00",
    obligation_ids=["deployer_high_risk"],
)
_AGENT = {
    "id": "agent-a1",
    "name": "planner",
    "tools": [{"name": "approve", "kind": "function", "requires_approval": True}],
    "models": [{"provider": "OpenAI", "model": "gpt-x"}],
    "mandate": {"permitted_actions": ["tool:approve"]},
    "guardrails": [{"kind": "output filter"}],
    "logging": {"decision_log_ref": "logs/decisions.jsonl"},
}


def _pack(verification: str = "verified") -> dict:
    return {
        "deployer_pack:" + _SHA[:12]: {
            "source": "deployer_pack",
            "status": "imported_pack",
            "source_file": _FILE,
            "pack_sha256": _SHA,
            "provider_system_id": _PROVIDER_ID,
            "verification": verification,
            "signer_key_id": "cd" * 8 if verification == "verified" else None,
            "imported_on": "2026-10-07",
        }
    }


def _row(tmp_path, *, evidence=None, session=_SESSION, **extra):
    manifest = SystemManifest(
        system_id="deployer-sys",
        intended_purpose="support",
        commit_ref="HEAD",
        operator_role="deployer",
        checker_session=session,
        **({"imported_evidence": evidence} if evidence else {}),
        **extra,
    )
    report = build_gap_report(
        "deployer-sys",
        "HEAD",
        repo_root=tmp_path,
        manifest=manifest,
        checker_session=session,
        today=_TODAY,
    )
    return report, next((r for r in report.articles if r.article == "Art. 26"), None)


def test_imported_pack_lifts_missing_to_partial_with_reason(tmp_path):
    _, before = _row(tmp_path)
    assert before.status is GapStatus.MISSING
    _, row = _row(tmp_path, evidence=_pack())
    assert row.status is GapStatus.PARTIAL
    assert row.source is ArticleGapSource.MANIFEST
    assert row.evidence_ref == "manifest:imported_provider_pack"
    assert REASON in row.rationale
    assert "1 deployer pack(s)" in row.rationale
    assert "0 unsigned" in row.rationale


@pytest.mark.parametrize("verification", ["verified", "unsigned"])
def test_imported_pack_row_is_never_met(tmp_path, verification):
    _, row = _row(tmp_path, evidence=_pack(verification))
    assert row.status is GapStatus.PARTIAL
    assert REASON in row.rationale
    (tmp_path / "DEPLOYER_USE_RECORDS.md").write_text(
        "# Use records\n", encoding="utf-8"
    )
    _, row = _row(tmp_path, evidence=_pack(verification))
    assert row.status in (GapStatus.PARTIAL, GapStatus.MISSING)
    assert row.source is not ArticleGapSource.ATTESTATION


def test_without_pack_row_reads_missing_as_before(tmp_path):
    _, row = _row(tmp_path)
    assert row.status is GapStatus.MISSING
    assert REASON not in row.rationale
    assert row.evidence_ref != "manifest:imported_provider_pack"


def test_model_card_evidence_is_not_a_pack(tmp_path):
    card = {
        "system_name": {
            "source": "model_card",
            "status": "attested",
            "source_file": "card.md",
            "card_sha256": _SHA,
            "imported_on": "2026-10-07",
        }
    }
    manifest = SystemManifest(
        system_id="s", intended_purpose="p", commit_ref="HEAD", imported_evidence=card
    )
    assert manifest.imported_evidence  # accepted, but not a pack
    _, row = _row(tmp_path, evidence=card)
    assert row.status is GapStatus.MISSING
    assert REASON not in row.rationale


def test_expired_mandate_still_wins_over_pack(tmp_path):
    agent = {**_AGENT, "mandate": {**_AGENT["mandate"], "expires_at": "2026-10-10"}}
    _, row = _row(tmp_path, evidence=_pack(), agent_inventory={"agents": [agent]})
    assert row.status is GapStatus.MISSING
    assert REASON not in row.rationale
    assert row.evidence_ref != "manifest:imported_provider_pack"


def test_pack_row_text_has_no_identifiers(tmp_path):
    report, row = _row(tmp_path, evidence=_pack("unsigned"))
    assert "1 unsigned" in row.rationale
    dumped = report.model_dump_json()
    for banned in (_PROVIDER_ID, _FILE, _SHA, _SHA[:12]):
        assert banned not in dumped


def test_no_session_means_no_art26_row_change(tmp_path):
    report, row = _row(tmp_path, evidence=_pack(), session=None)
    assert row is None or REASON not in row.rationale
    gated, _ = _row(
        tmp_path,
        session=_SESSION.model_copy(update={"obligation_ids": ["ai_literacy"]}),
        evidence=_pack(),
    )
    assert "Art. 26" in gated.not_applicable
    assert report.not_applicable is None or "Art. 26" not in report.not_applicable
