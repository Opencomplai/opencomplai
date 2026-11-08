"""EU AI Act Art. 4 takes an attestation and NIST does not inherit it.

Art. 4 (AI literacy) is an organisational duty no code can show. Its row reads
Met only from `framework_inputs.EU_AI_ACT.attested`; every other EU article keeps
the verdict its own sources give. The NIST subcategories that map to Art. 4
treat that row as no evidence (ADR-framework-packs 2026-11c).
"""

from __future__ import annotations

from datetime import date

import pytest
from opencomplai_core.frameworks import (
    EU_AI_ACT,
    evaluate_targets,
)
from opencomplai_core.gap_report import (
    build_gap_report,
    load_gap_article_map,
    stale_attestation_warnings,
)
from opencomplai_core.models import (
    ArticleGapSource,
    ArticleGapStatus,
    Attestation,
    CheckerSessionRef,
    ConfidenceLabel,
    FrameworkInputs,
    FrameworkScope,
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
ISO = "ISO_IEC_27001"
NIST = "NIST_AI_RMF"


def _att(**over: object) -> Attestation:
    base: dict[str, object] = {
        "statement": "Staff complete AI literacy training every year.",
        "attested_by": "Jane Doe",
        "attested_at": "2026-06-01",
    }
    return Attestation.model_validate({**base, **over})


def _manifest(**inputs: FrameworkInputs) -> SystemManifest:
    return SystemManifest(
        system_id="sys", intended_purpose="credit scoring", framework_inputs=inputs
    )


def _eu_rows(manifest: SystemManifest, targets: list[str] | None = None, **kw):
    reports = evaluate_targets(
        manifest, targets or [EU_AI_ACT], commit_ref="abc", today=TODAY, **kw
    )
    return {row.article: row for row in reports[EU_AI_ACT].report.articles}


# --- Art. 4 ------------------------------------------------------------------


def test_art_4_is_unverified_without_an_attestation() -> None:
    row = _eu_rows(_manifest())["Art. 4"]
    assert row.status is GapStatus.UNVERIFIED
    assert row.source is ArticleGapSource.ATTESTATION
    assert row.confidence_label is ConfidenceLabel.NOT_ASSESSED
    assert row.evidence_ref == "none"
    assert row.rationale == (
        "No attestation recorded. Add one under "
        "framework_inputs.EU_AI_ACT.attested in the manifest."
    )


def test_art_4_is_met_when_attested() -> None:
    manifest = _manifest(
        EU_AI_ACT=FrameworkInputs(attested={"Art. 4": _att(record_id="rec_7")})
    )
    row = _eu_rows(manifest)["Art. 4"]
    assert row.status is GapStatus.MET
    assert row.source is ArticleGapSource.ATTESTATION
    assert row.confidence_label is ConfidenceLabel.ATTESTED
    assert row.evidence_ref == "attestation:Jane Doe@2026-06-01#rec_7"
    assert row.rationale == "Staff complete AI literacy training every year."


def test_art_4_reads_unverified_again_when_the_attestation_has_expired() -> None:
    manifest = _manifest(
        EU_AI_ACT=FrameworkInputs(
            attested={"Art. 4": _att(valid_until=date(2026, 11, 2))}
        )
    )
    row = _eu_rows(manifest)["Art. 4"]
    assert row.status is GapStatus.UNVERIFIED
    assert row.rationale == (
        "Attestation expired on 2026-11-02. Renew it under "
        "framework_inputs.EU_AI_ACT.attested in the manifest."
    )


def test_attesting_art_4_changes_no_other_eu_row() -> None:
    plain = _eu_rows(_manifest())
    attested = _eu_rows(
        _manifest(EU_AI_ACT=FrameworkInputs(attested={"Art. 4": _att()}))
    )
    assert plain.keys() == attested.keys()
    assert {a for a in plain if plain[a] != attested[a]} == {"Art. 4"}


def test_the_eu_attestation_applies_when_the_eu_act_is_not_a_target() -> None:
    manifest = _manifest(
        EU_AI_ACT=FrameworkInputs(attested={"Art. 4": _att()}),
        **{ISO: FrameworkInputs()},
    )
    assert _eu_rows(manifest, [ISO])["Art. 4"].status is GapStatus.MET


def test_art_4_is_not_withdrawn_by_a_checker_session_that_omits_ai_literacy() -> None:
    # Art. 4 has never carried applies_when_any: a session that recorded other
    # obligations still leaves it in the report, as it did with the obligation source.
    session = CheckerSessionRef(
        checker_version="checker-2026-10-26",
        session_id="s-1",
        completed_at="2026-11-03T00:00:00Z",
        obligation_ids=["prohibited"],
    )
    report = build_gap_report("s", "abc", checker_session=session, today=TODAY)
    assert "Art. 4" in {row.article for row in report.articles}
    assert "Art. 4" not in report.not_applicable


@pytest.mark.parametrize("article", ["Art. 9", "Art. 26", "Art. 99"])
def test_no_other_eu_article_takes_an_attestation(article: str) -> None:
    manifest = _manifest(EU_AI_ACT=FrameworkInputs(attested={article: _att()}))
    with pytest.raises(
        ValueError,
        match=rf"framework_inputs\.EU_AI_ACT\.attested: '{article}' is not a "
        "EU_AI_ACT requirement that takes an attestation",
    ):
        evaluate_targets(manifest, [EU_AI_ACT], commit_ref="abc")


def test_the_prefixed_art_4_key_is_refused() -> None:
    # The EU AI Act spells its ids without a prefix, in the manifest as in the report.
    manifest = _manifest(
        EU_AI_ACT=FrameworkInputs(attested={"EU_AI_ACT:Art. 4": _att()})
    )
    with pytest.raises(
        ValueError,
        match=r"framework_inputs\.EU_AI_ACT\.attested: 'EU_AI_ACT:Art\. 4' is not a "
        "EU_AI_ACT requirement that takes an attestation",
    ):
        evaluate_targets(manifest, [EU_AI_ACT], commit_ref="abc")


def test_the_eu_act_still_refuses_exclusions_and_scope() -> None:
    for inputs in (
        FrameworkInputs(excluded={"Art. 4": "Not relevant."}),
        FrameworkInputs(scope=FrameworkScope(trains_models=False)),
    ):
        with pytest.raises(ValueError, match=r"framework_inputs\.EU_AI_ACT"):
            evaluate_targets(_manifest(EU_AI_ACT=inputs), [EU_AI_ACT], commit_ref="abc")


def test_an_undated_art_4_attestation_goes_stale_after_a_year() -> None:
    warnings = stale_attestation_warnings(
        {"Art. 4": _att(attested_at="2025-10-01")}, load_gap_article_map(), TODAY
    )
    assert warnings == [
        "Art. 4: attested on 2025-10-01, more than 365 days ago. "
        "Re-attest it, or set valid_until on the attestation."
    ]


def test_art_4_alone_is_the_eu_row_with_an_attestation_source() -> None:
    taking = {
        article
        for article, config in load_gap_article_map().items()
        if any(s["kind"] == "attestation" for s in config["sources"])
    }
    assert taking == {"Art. 4"}


# --- NIST AI RMF does not inherit Art. 4 -------------------------------------


def _gap_report(**statuses: tuple[GapStatus, ArticleGapSource]) -> GapReport:
    return GapReport(
        system_id="s",
        commit_ref="c",
        generated_at="2026-11-03T00:00:00Z",
        articles=[
            ArticleGapStatus(
                article=article.replace("_", ". "),  # Art_4 -> "Art. 4"
                status=status,
                source=source,
                evidence_ref="x",
                rationale="r",
            )
            for article, (status, source) in statuses.items()
        ],
    )


ATTESTED_ART_4 = (GapStatus.MET, ArticleGapSource.ATTESTATION)


def _sub(report, subcategory: str):
    return next(r for r in report.subcategories if r.subcategory == subcategory)


def test_govern_2_2_takes_an_attestation_and_map_3_4_does_not() -> None:
    attestable = attestable_subcategories()
    assert f"{NIST}:GOVERN 2.2" in attestable
    assert f"{NIST}:MAP 3.4" not in attestable
    assert f"{NIST}:GOVERN 2.1" not in attestable  # Art. 17, a code-decided article
    assert f"{NIST}:MANAGE 2.1" in attestable  # no EU mapping at all


def test_an_attested_art_4_is_not_a_met_govern_2_2() -> None:
    report = build_nist_rmf_report(_gap_report(Art_4=ATTESTED_ART_4), {}, TODAY)
    row = _sub(report, "GOVERN 2.2")
    assert row.status is GapStatus.UNVERIFIED
    assert row.confidence_label is ConfidenceLabel.NOT_ASSESSED
    assert row.rationale == (
        "The EU AI Act evidence holds nothing for this subcategory. Add an "
        "attestation under framework_inputs.NIST_AI_RMF.attested in the manifest."
    )


def test_govern_2_2_is_met_by_its_own_nist_attestation() -> None:
    key = f"{NIST}:GOVERN 2.2"
    row = _sub(
        build_nist_rmf_report(_gap_report(), {key: _att(record_id="rec_2")}, TODAY),
        "GOVERN 2.2",
    )
    assert row.status is GapStatus.MET
    assert row.confidence_label is ConfidenceLabel.ATTESTED
    gap = nist_rmf_as_gap_report(_gap_report(), {key: _att(record_id="rec_2")}, TODAY)
    gap_row = next(r for r in gap.articles if r.article == key)
    assert gap_row.source is ArticleGapSource.ATTESTATION
    assert gap_row.evidence_ref == "attestation:Jane Doe@2026-06-01#rec_2"


def test_an_expired_govern_2_2_attestation_reads_unverified() -> None:
    key = f"{NIST}:GOVERN 2.2"
    row = _sub(
        build_nist_rmf_report(
            _gap_report(), {key: _att(valid_until=date(2026, 11, 2))}, TODAY
        ),
        "GOVERN 2.2",
    )
    assert row.status is GapStatus.UNVERIFIED
    assert row.rationale.startswith("Attestation expired on 2026-11-02.")


def test_map_3_4_is_decided_by_art_26_alone() -> None:
    report = build_nist_rmf_report(
        _gap_report(
            Art_4=ATTESTED_ART_4, Art_26=(GapStatus.MISSING, ArticleGapSource.ARTIFACT)
        ),
        {},
        TODAY,
    )
    row = _sub(report, "MAP 3.4")
    assert row.status is GapStatus.MISSING
    assert row.source_eu_ai_act_articles == ["Art. 26"]
    assert "Art. 4 ->" not in row.rationale
    assert row.rationale.endswith(
        "Set aside, because an attestation decides it and is no evidence for "
        "another framework: Art. 4."
    )


def test_map_3_4_has_no_evidence_when_only_art_4_is_in_the_report() -> None:
    row = _sub(
        build_nist_rmf_report(_gap_report(Art_4=ATTESTED_ART_4), {}, TODAY), "MAP 3.4"
    )
    assert row.status is GapStatus.UNVERIFIED
    assert row.source_eu_ai_act_articles == ["Art. 4", "Art. 26"]
    assert "none of those articles are present" in row.rationale
    assert row.rationale.endswith("another framework: Art. 4.")


@pytest.mark.parametrize(
    "art_4", [ATTESTED_ART_4, (GapStatus.UNVERIFIED, ArticleGapSource.ATTESTATION)]
)
def test_a_set_aside_art_4_holds_map_3_4_at_unverified(
    art_4: tuple[GapStatus, ArticleGapSource],
) -> None:
    # Attested or not, Art. 4 is no evidence for NIST: a Met Art. 26 alone never
    # makes MAP 3.4 Met, as before an attestation could decide Art. 4.
    report = build_nist_rmf_report(
        _gap_report(Art_4=art_4, Art_26=(GapStatus.MET, ArticleGapSource.ARTIFACT)),
        {},
        TODAY,
    )
    row = _sub(report, "MAP 3.4")
    assert row.status is GapStatus.UNVERIFIED
    assert row.source_eu_ai_act_articles == ["Art. 26"]


def test_an_ordinary_nist_row_reads_as_it_always_did() -> None:
    row = _sub(
        build_nist_rmf_report(
            _gap_report(Art_14=(GapStatus.MISSING, ArticleGapSource.ARTIFACT)),
            {},
            TODAY,
        ),
        "MAP 3.5",
    )
    assert "Set aside" not in row.rationale


def test_nist_attestations_through_evaluate_targets() -> None:
    ok = _manifest(**{NIST: FrameworkInputs(attested={f"{NIST}:GOVERN 2.2": _att()})})
    reports = evaluate_targets(ok, [NIST], commit_ref="abc", today=TODAY)
    govern = next(
        r for r in reports[NIST].report.articles if r.article == f"{NIST}:GOVERN 2.2"
    )
    assert govern.status is GapStatus.MET

    bad = _manifest(**{NIST: FrameworkInputs(attested={f"{NIST}:MAP 3.4": _att()})})
    with pytest.raises(ValueError, match=r"MAP 3\.4"):
        evaluate_targets(bad, [NIST], commit_ref="abc", today=TODAY)


def test_attesting_art_4_leaves_the_nist_rows_unchanged() -> None:
    def nist(manifest: SystemManifest):
        report = evaluate_targets(manifest, [NIST], commit_ref="abc", today=TODAY)
        return {r.article: r for r in report[NIST].report.articles}

    plain = nist(_manifest())
    attested = nist(_manifest(EU_AI_ACT=FrameworkInputs(attested={"Art. 4": _att()})))
    assert plain == attested
