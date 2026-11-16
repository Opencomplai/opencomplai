"""EU AI Act Art. 20 (corrective actions, duty of information) takes an attestation.

No code can show that a provider took corrective action or told distributors, deployers
and authorities, so the row is decided by the provider's attestation alone. It applies
only to a provider of a high-risk system, which a recorded checker session decides.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from opencomplai_core.control_catalog import CONTROL_CATALOG
from opencomplai_core.framework_crosswalk import get_crosswalk
from opencomplai_core.frameworks import (
    EU_AI_ACT,
    attestable_ids,
    attestation_only_ids,
    evaluate_targets,
)
from opencomplai_core.gap_report import build_gap_report, load_gap_article_map
from opencomplai_core.models import (
    ArticleGapSource,
    Attestation,
    CheckerSessionRef,
    ConfidenceLabel,
    FrameworkInputs,
    GapStatus,
    SystemManifest,
)

TODAY = date(2026, 11, 9)
_DATA = Path(__file__).resolve().parents[1] / "src" / "opencomplai_core" / "data"


def _att(**over: object) -> Attestation:
    base: dict[str, object] = {
        "statement": "Corrective actions are logged and distributors are told.",
        "attested_by": "Jane Doe",
        "attested_at": "2026-10-01",
    }
    return Attestation.model_validate({**base, **over})


def _row(attested: dict[str, Attestation] | None = None):
    manifest = SystemManifest(
        system_id="sys",
        intended_purpose="credit scoring",
        framework_inputs={EU_AI_ACT: FrameworkInputs(attested=attested or {})},
    )
    reports = evaluate_targets(manifest, [EU_AI_ACT], commit_ref="abc", today=TODAY)
    return {r.article: r for r in reports[EU_AI_ACT].report.articles}["Art. 20"]


def _session(*obligation_ids: str) -> CheckerSessionRef:
    return CheckerSessionRef(
        checker_version="checker-2026-10-26",
        session_id="s-1",
        completed_at="2026-11-09T00:00:00Z",
        obligation_ids=list(obligation_ids),
    )


def test_art_20_is_unverified_without_an_attestation() -> None:
    row = _row()
    assert row.status is GapStatus.UNVERIFIED
    assert row.source is ArticleGapSource.ATTESTATION
    assert row.evidence_ref == "none"
    assert row.confidence_label is ConfidenceLabel.NOT_ASSESSED
    assert row.rationale == (
        "No attestation recorded. Add one under "
        "framework_inputs.EU_AI_ACT.attested in the manifest."
    )


def test_art_20_is_met_when_attested() -> None:
    row = _row({"Art. 20": _att()})
    assert row.status is GapStatus.MET
    assert row.source is ArticleGapSource.ATTESTATION
    assert row.confidence_label is ConfidenceLabel.ATTESTED


def test_art_20_reads_unverified_again_when_the_attestation_has_expired() -> None:
    row = _row({"Art. 20": _att(valid_until=date(2026, 11, 8))})
    assert row.status is GapStatus.UNVERIFIED
    assert row.rationale.startswith("Attestation expired on 2026-11-08.")


def test_a_session_without_the_provider_obligation_makes_art_20_not_applicable() -> (
    None
):
    report = build_gap_report("s", "abc", checker_session=_session("deployer_general"))
    assert "Art. 20" in report.not_applicable
    assert "Art. 20" not in {r.article for r in report.articles}


def test_a_provider_high_risk_session_keeps_art_20() -> None:
    report = build_gap_report(
        "s", "abc", checker_session=_session("provider_high_risk")
    )
    assert "Art. 20" in {r.article for r in report.articles}
    assert "Art. 20" not in report.not_applicable


def test_art_20_is_attestation_only_and_never_missing() -> None:
    config = load_gap_article_map()["Art. 20"]
    assert [s["kind"] for s in config["sources"]] == ["attestation"]
    assert config["default_ttl_days"] == 365
    assert config["applies_when_any"] == ["provider_high_risk"]
    assert (
        config["applicability_note"]
        == (load_gap_article_map()["Art. 16"]["applicability_note"])
    )
    assert config["confidence"] == "low"
    assert config["needs_founder_review"] is True
    assert not {"heuristic", "placeholder"} & set(config["note"].lower().split())


def test_the_eu_attestable_set_is_art_4_and_art_20() -> None:
    expected = {"Art. 4", "Art. 20"}
    assert attestable_ids(EU_AI_ACT) == expected
    assert attestation_only_ids(EU_AI_ACT) == expected


def test_art_9_still_refuses_an_attestation() -> None:
    manifest = SystemManifest(
        system_id="sys",
        intended_purpose="x",
        framework_inputs={EU_AI_ACT: FrameworkInputs(attested={"Art. 9": _att()})},
    )
    with pytest.raises(ValueError, match=r"'Art\. 9' is not a EU_AI_ACT requirement"):
        evaluate_targets(manifest, [EU_AI_ACT], commit_ref="abc")


def test_the_catalog_entry_exists() -> None:
    entry = CONTROL_CATALOG["Art. 20"]
    assert entry.title == "Corrective actions and duty of information"
    assert entry.default_ttl_days == 365
    assert entry.confidence == "low"
    assert entry.needs_founder_review is True


def test_the_crosswalk_row_is_low_confidence_clause_10_2_manage_2() -> None:
    row = get_crosswalk()["Art. 20"]
    assert row.iso_42001_clause.startswith("Clause 10.2")
    assert row.iso_42001_annex_a_control is None
    assert row.nist_ai_rmf_subcategory == "MANAGE 2"
    assert row.confidence == "low"
    assert row.needs_founder_review is True


def test_the_principles_file_groups_art_20_under_accountability_and_flags_it() -> None:
    data = json.loads((_DATA / "eu_ai_act_principles.json").read_text("utf-8"))
    assert "Art. 20" in data["principles"]["accountability"]["articles"]
    flag = data["review_flags"]["Art. 20"]
    assert flag["confidence"] == "low"
    assert flag["needs_founder_review"] is True
