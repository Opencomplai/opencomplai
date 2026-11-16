"""Two rules of the NIST AI RMF re-projection that came out of the mapping review.

A low-confidence link cannot make a subcategory Missing or Partial: it counts as
Unverified in the rollup and is cited as supporting evidence. A subcategory whose
mapped articles are all not applicable (a checker session says so) or decided by
an attestation takes an attestation instead of reading from evidence that is not
there.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from opencomplai_core.frameworks import evaluate_targets, gate_failures
from opencomplai_core.models import (
    ArticleGapSource,
    ArticleGapStatus,
    Attestation,
    CheckerSessionRef,
    ConfidenceLabel,
    FrameworkInputs,
    GapReport,
    GapStatus,
    SystemManifest,
)
from opencomplai_core.nist_rmf_report import (
    attestable_subcategories,
    build_nist_rmf_report,
    nist_rmf_as_gap_report,
)

TODAY = date(2026, 11, 3)
NIST = "NIST_AI_RMF"

CAPPED_ART_17 = (
    " Capped at Unverified, because a low-confidence link cannot make a "
    "subcategory Missing or Partial: Art. 17."
)
NO_EVIDENCE = (
    "The EU AI Act evidence holds nothing for this subcategory. Add an attestation "
    "under framework_inputs.NIST_AI_RMF.attested in the manifest."
)
UNUSED = (
    " The attestation recorded for this subcategory is not used: it counts only "
    "when every mapped article is not applicable or decided by an attestation."
)

_ATTESTATION = Attestation(
    statement="Risk management is reviewed every quarter.",
    attested_by="Compliance lead",
    attested_at="2026-11-01",
)


def _row(article: str, status: GapStatus, ref: str = "x") -> ArticleGapStatus:
    return ArticleGapStatus(
        article=article,
        status=status,
        source=ArticleGapSource.RULE,
        evidence_ref=ref,
    )


def _gap(
    rows: list[ArticleGapStatus], not_applicable: dict[str, str] | None = None
) -> GapReport:
    return GapReport(
        system_id="sys",
        commit_ref="HEAD",
        generated_at="2026-11-03T00:00:00Z",
        articles=rows,
        not_applicable=not_applicable or {},
    )


def _sub(report, subcategory: str):
    return next(r for r in report.subcategories if r.subcategory == subcategory)


def _na_text(subcat_id: str, articles: str) -> str:
    return (
        f"None of the EU AI Act articles mapped to {subcat_id} gives evidence in "
        f"this run (not applicable: {articles}). Add an attestation under "
        "framework_inputs.NIST_AI_RMF.attested in the manifest."
    )


# --- A1: low links are capped ---------------------------------------------------


def test_a_low_link_that_is_missing_reads_unverified_and_says_so() -> None:
    row = _sub(
        build_nist_rmf_report(_gap([_row("Art. 17", GapStatus.MISSING, "qms")])),
        "GOVERN 1.2",
    )
    assert row.status is GapStatus.UNVERIFIED
    assert row.mapping_confidence == "low"
    assert row.confidence_label is ConfidenceLabel.HEURISTIC_ESTIMATE
    assert row.source_eu_ai_act_articles == ["Art. 17"]
    assert row.rationale == (
        "Re-projected via data/nist_ai_rmf_subcategories.json (mapping "
        "confidence=low) from existing EU AI Act evidence: Art. 17 -> missing "
        f"(source=rule, evidence=qms).{CAPPED_ART_17}"
    )


def test_a_low_link_that_is_partial_reads_unverified() -> None:
    row = _sub(
        build_nist_rmf_report(_gap([_row("Art. 17", GapStatus.PARTIAL)])),
        "GOVERN 1.2",
    )
    assert row.status is GapStatus.UNVERIFIED
    assert "Art. 17 -> partial" in row.rationale
    assert row.rationale.endswith(CAPPED_ART_17)


def test_a_medium_link_that_is_missing_stays_missing() -> None:
    row = _sub(
        build_nist_rmf_report(_gap([_row("Art. 14", GapStatus.MISSING)])), "MAP 3.5"
    )
    assert row.status is GapStatus.MISSING
    assert row.mapping_confidence == "medium"
    assert "Capped" not in row.rationale


def test_a_medium_link_that_is_missing_still_fails_beside_a_capped_low_one() -> None:
    row = _sub(
        build_nist_rmf_report(
            _gap(
                [_row("Art. 9", GapStatus.MISSING), _row("Art. 17", GapStatus.MISSING)]
            )
        ),
        "GOVERN 1.4",
    )
    assert row.status is GapStatus.MISSING
    assert row.mapping_confidence == "low"  # still the lowest link
    assert row.rationale.endswith(CAPPED_ART_17)  # only the low link is named


def test_a_met_medium_link_beside_a_missing_low_one_reads_unverified() -> None:
    row = _sub(
        build_nist_rmf_report(
            _gap([_row("Art. 9", GapStatus.MET), _row("Art. 17", GapStatus.MISSING)])
        ),
        "GOVERN 1.4",
    )
    assert row.status is GapStatus.UNVERIFIED


def test_met_and_unverified_low_links_are_never_capped() -> None:
    met = _sub(
        build_nist_rmf_report(_gap([_row("Art. 17", GapStatus.MET)])), "GOVERN 1.2"
    )
    assert met.status is GapStatus.MET
    assert "Capped" not in met.rationale
    unverified = _sub(
        build_nist_rmf_report(_gap([_row("Art. 17", GapStatus.UNVERIFIED)])),
        "GOVERN 1.2",
    )
    assert unverified.status is GapStatus.UNVERIFIED
    assert "Capped" not in unverified.rationale


def test_the_gate_fails_a_medium_missing_row_and_not_a_low_one(tmp_path: Path) -> None:
    manifest = SystemManifest(system_id="sys", intended_purpose="credit scoring")
    reports = evaluate_targets(
        manifest,
        ["EU_AI_ACT", NIST],
        commit_ref="abc",
        repo_root=tmp_path,
        today=TODAY,
    )
    failing = gate_failures(reports, [NIST], "partial")
    assert f"{NIST}:MANAGE 1.3" in failing
    assert f"{NIST}:GOVERN 1.2" not in failing


# --- A2: rows with nothing applicable take an attestation ---------------------------


def test_the_attestable_set_is_computed_from_the_data() -> None:
    attestable = attestable_subcategories()
    assert len(attestable) == 49
    assert {f"{NIST}:MANAGE 1.3", f"{NIST}:MAP 3.4", f"{NIST}:GOVERN 2.1"} <= attestable
    # The four rows that lost their only EU link were attestable before and stay so,
    # as does MANAGE 2.3 beside Art. 20. MANAGE 2.4 keeps Art. 14, which always applies.
    assert {
        f"{NIST}:{sid}"
        for sid in (
            "GOVERN 1.6",
            "MEASURE 1.3",
            "MEASURE 2.12",
            "MANAGE 3.2",
            "MANAGE 2.3",
        )
    } <= attestable
    assert f"{NIST}:MANAGE 2.4" not in attestable
    assert f"{NIST}:GOVERN 1.1" not in attestable
    assert f"{NIST}:MAP 3.5" not in attestable


def test_a_not_applicable_row_is_unverified_until_attested() -> None:
    row = _sub(
        build_nist_rmf_report(_gap([], {"Art. 9": "x"})),
        "MANAGE 1.3",
    )
    assert row.status is GapStatus.UNVERIFIED
    assert row.confidence_label is ConfidenceLabel.NOT_ASSESSED
    assert row.mapping_confidence is None
    assert row.source_eu_ai_act_articles == []
    assert row.rationale == _na_text("MANAGE 1.3", "Art. 9")


def test_a_not_applicable_row_is_met_once_attested() -> None:
    gap = _gap([], {"Art. 9": "x"})
    attested = {f"{NIST}:MANAGE 1.3": _ATTESTATION}
    row = _sub(build_nist_rmf_report(gap, attested, TODAY), "MANAGE 1.3")
    assert row.status is GapStatus.MET
    assert row.confidence_label is ConfidenceLabel.ATTESTED
    assert row.rationale == _ATTESTATION.statement
    view = nist_rmf_as_gap_report(gap, attested, TODAY)
    gap_row = next(r for r in view.articles if r.article == f"{NIST}:MANAGE 1.3")
    assert gap_row.source is ArticleGapSource.ATTESTATION
    assert gap_row.evidence_ref == "attestation:Compliance lead@2026-11-01"


def test_an_expired_attestation_on_a_not_applicable_row_reads_unverified() -> None:
    attestation = _ATTESTATION.model_copy(update={"valid_until": date(2026, 11, 2)})
    row = _sub(
        build_nist_rmf_report(
            _gap([], {"Art. 9": "x"}), {f"{NIST}:MANAGE 1.3": attestation}, TODAY
        ),
        "MANAGE 1.3",
    )
    assert row.status is GapStatus.UNVERIFIED
    assert row.rationale.startswith("Attestation expired on")


def test_an_attestation_is_not_used_while_evidence_decides_the_row() -> None:
    gap = _gap([_row("Art. 9", GapStatus.MISSING, "risk_register")])
    attested = {f"{NIST}:MANAGE 1.3": _ATTESTATION}
    row = _sub(build_nist_rmf_report(gap, attested, TODAY), "MANAGE 1.3")
    assert row.status is GapStatus.MISSING
    assert row.source_eu_ai_act_articles == ["Art. 9"]
    assert row.rationale.endswith(f"evidence=risk_register).{UNUSED}")
    view = nist_rmf_as_gap_report(gap, attested, TODAY)
    gap_row = next(r for r in view.articles if r.article == f"{NIST}:MANAGE 1.3")
    assert gap_row.source is ArticleGapSource.CROSSWALK


def test_an_unused_attestation_is_also_said_when_the_articles_are_absent() -> None:
    row = _sub(
        build_nist_rmf_report(_gap([]), {f"{NIST}:MANAGE 1.3": _ATTESTATION}, TODAY),
        "MANAGE 1.3",
    )
    assert row.status is GapStatus.UNVERIFIED
    assert "none of those articles are present" in row.rationale
    assert row.rationale.endswith(UNUSED)


def test_map_3_4_falls_back_to_an_attestation_when_art_26_is_not_applicable() -> None:
    # Art. 4 is decided by an attestation itself; Art. 26 is not applicable.
    gap = _gap([], {"Art. 26": "x"})
    row = _sub(build_nist_rmf_report(gap), "MAP 3.4")
    assert row.status is GapStatus.UNVERIFIED
    assert row.source_eu_ai_act_articles == []
    assert row.rationale == _na_text("MAP 3.4", "Art. 26")
    attested = {f"{NIST}:MAP 3.4": _ATTESTATION}
    assert _sub(build_nist_rmf_report(gap, attested, TODAY), "MAP 3.4").status is (
        GapStatus.MET
    )


def test_a_row_with_one_applicable_article_is_decided_by_it_alone() -> None:
    # MAP 5.1 maps Art. 9 and Art. 27; Art. 27 is not applicable.
    gap = _gap([_row("Art. 9", GapStatus.MISSING)], {"Art. 27": "x"})
    attested = {f"{NIST}:MAP 5.1": _ATTESTATION}
    row = _sub(build_nist_rmf_report(gap, attested, TODAY), "MAP 5.1")
    assert row.status is GapStatus.MISSING
    assert row.source_eu_ai_act_articles == ["Art. 9"]
    assert row.rationale.endswith(UNUSED)


def test_an_article_that_is_only_absent_is_not_a_not_applicable_one() -> None:
    row = _sub(build_nist_rmf_report(_gap([])), "MANAGE 1.3")
    assert row.status is GapStatus.UNVERIFIED
    assert row.source_eu_ai_act_articles == ["Art. 9"]
    assert row.rationale == (
        "MANAGE 1.3 maps to Art. 9, but none of those articles are present in "
        "this gap report run."
    )


def test_an_unmapped_row_keeps_its_own_text() -> None:
    assert _sub(build_nist_rmf_report(_gap([])), "MANAGE 2.1").rationale == NO_EVIDENCE


# --- through evaluate_targets ---------------------------------------------------------


def _manifest(session: bool, attested: dict[str, Attestation]) -> SystemManifest:
    return SystemManifest(
        system_id="sys",
        intended_purpose="credit scoring",
        checker_session=(
            CheckerSessionRef(
                checker_version="checker-2026-10-26",
                session_id="s-1",
                completed_at="2026-11-01T00:00:00Z",
                obligation_ids=["deployer_general"],
            )
            if session
            else None
        ),
        framework_inputs={NIST: FrameworkInputs(attested=attested)},
    )


def _manage_1_3(manifest: SystemManifest, tmp_path: Path):
    reports = evaluate_targets(
        manifest,
        ["EU_AI_ACT", NIST],
        commit_ref="abc",
        repo_root=tmp_path,
        today=TODAY,
    )
    return next(
        r for r in reports[NIST].report.articles if r.article == f"{NIST}:MANAGE 1.3"
    )


def test_a_checker_session_makes_manage_1_3_attestable(tmp_path: Path) -> None:
    attested = {f"{NIST}:MANAGE 1.3": _ATTESTATION}
    row = _manage_1_3(_manifest(True, attested), tmp_path)
    # MANAGE 1.3 also names a corroborating artifact (risk_register); the empty
    # repo has none, so the valid attestation reads Partial, not Met.
    assert row.status is GapStatus.PARTIAL
    assert row.source is ArticleGapSource.ATTESTATION
    assert row.corroborated is False
    assert row.rationale.startswith("Attested")
    unattested = _manage_1_3(_manifest(True, {}), tmp_path)
    # Without an attestation the row's own artifact probe decides it; the empty
    # repo has no risk register, so it reads Missing on that source.
    assert unattested.status is GapStatus.MISSING
    assert unattested.source is ArticleGapSource.ARTIFACT
    assert unattested.evidence_ref == "risk_register"


def test_without_a_checker_session_the_attestation_is_not_used(tmp_path: Path) -> None:
    row = _manage_1_3(_manifest(False, {f"{NIST}:MANAGE 1.3": _ATTESTATION}), tmp_path)
    assert row.status is GapStatus.MISSING
    assert row.source is ArticleGapSource.CROSSWALK
    assert row.rationale.endswith(UNUSED)


def test_a_row_an_always_applicable_article_decides_still_refuses_an_attestation(
    tmp_path: Path,
) -> None:
    manifest = _manifest(True, {f"{NIST}:GOVERN 1.1": _ATTESTATION})
    with pytest.raises(ValueError, match="takes an attestation"):
        evaluate_targets(
            manifest,
            ["EU_AI_ACT", NIST],
            commit_ref="abc",
            repo_root=tmp_path,
            today=TODAY,
        )
