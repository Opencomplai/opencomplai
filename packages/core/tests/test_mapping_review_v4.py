"""The mapping review's change verdicts: links, anchors and evaluators.

Seven NIST AI RMF rows, eight ISO/IEC 42001 rows and four ISO/IEC 27090 rows changed.
The data is pinned row by row; where a change alters a verdict the engine's behaviour
is pinned too.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from opencomplai_core.frameworks import (
    FRAMEWORKS,
    attestation_only_ids,
    evaluate_targets,
    load_requirements_map,
)
from opencomplai_core.models import (
    ArticleGapSource,
    ArticleGapStatus,
    Attestation,
    CheckerSessionRef,
    ConfidenceLabel,
    EvalReport,
    EvaluatorCategory,
    EvaluatorOutcome,
    EvaluatorResult,
    FrameworkInputs,
    GapReport,
    GapStatus,
    SystemManifest,
)
from opencomplai_core.nist_ai_rmf_subcategories import get_subcategories
from opencomplai_core.nist_rmf_report import build_nist_rmf_report

TODAY = date(2026, 11, 9)
NIST = "NIST_AI_RMF"
ISO27 = "ISO_IEC_27090"
ISO42 = "ISO_IEC_42001"
L, M = "low", "medium"

NIST_LINKS = {
    "GOVERN 1.6": (),
    "GOVERN 6.1": (("Art. 25", L), ("Art. 53", L)),
    "MEASURE 1.3": (),
    "MEASURE 2.12": (),
    "MANAGE 2.3": (("Art. 20", L), ("Art. 72", L), ("Art. 73", L)),
    "MANAGE 2.4": (("Art. 14", M), ("Art. 20", L)),
    "MANAGE 3.2": (),
}
ISO42_LINKS = {
    "Clause 6.3": ["Art. 17"],
    "Clause 8.4": ["Art. 9", "Art. 27"],
    "Clause 9.2": ["Art. 17", "Art. 43"],
    "Clause 10.2": ["Art. 20", "Art. 73"],
    "A.2.3": ["Art. 17"],
    "A.5.3": ["Art. 9", "Art. 27"],
    "A.5.4": ["Art. 9", "Art. 27"],
    "A.5.5": ["Art. 9", "Art. 27"],
}
# Rows whose only EU article was dropped: nothing in the EU evidence decides them.
ATTESTATION_LED = ("GOVERN 1.6", "MEASURE 1.3", "MEASURE 2.12", "MANAGE 3.2")
# The articles those rows used to map to; each can read Missing in an ordinary run.
DROPPED = ("Art. 49", "Art. 43", "Art. 53")

SET_ASIDE = (
    " Set aside, because an attestation decides it and is no evidence for another "
    "framework: Art. 20."
)
NO_EVIDENCE = (
    "The EU AI Act evidence holds nothing for this subcategory. Add an attestation "
    "under framework_inputs.NIST_AI_RMF.attested in the manifest."
)

_ATTESTATION = Attestation(
    statement="Reviewed by the compliance lead each quarter.",
    attested_by="Compliance lead",
    attested_at="2026-11-01",
)


def _iso42() -> dict[str, dict]:
    return load_requirements_map(FRAMEWORKS[ISO42].requirements)


def _iso27() -> dict[str, dict]:
    return load_requirements_map(FRAMEWORKS[ISO27].requirements)


# --- links ----------------------------------------------------------------------


@pytest.mark.parametrize("sid", NIST_LINKS)
def test_nist_rows_carry_the_reviewed_eu_links(sid: str) -> None:
    assert get_subcategories()[sid].eu_ai_act == NIST_LINKS[sid]


@pytest.mark.parametrize("cid", ISO42_LINKS)
def test_iso_42001_rows_carry_the_reviewed_eu_links(cid: str) -> None:
    assert _iso42()[f"{ISO42}:{cid}"]["eu_ai_act"] == ISO42_LINKS[cid]


def test_distributor_duties_are_gone_from_govern_6_1() -> None:
    articles = [a for a, _ in get_subcategories()["GOVERN 6.1"].eu_ai_act]
    assert "Art. 24" not in articles


# --- ISO/IEC 27090 data ---------------------------------------------------------


def test_threat_modelling_and_deterioration_have_their_own_anchors() -> None:
    rows = _iso27()
    assert rows[f"{ISO27}:5.6"]["iso_27001"] == ["A.8.25", "A.8.27"]
    assert rows[f"{ISO27}:5.6"]["soc2"] == ["CC3.2"]
    assert rows[f"{ISO27}:7.4"]["iso_27001"] == ["A.8.16", "A.8.29"]
    assert rows[f"{ISO27}:7.4"]["soc2"] == ["CC7.1"]
    # 7.5 keeps the incident and monitoring anchors.
    assert "A.5.26" in rows[f"{ISO27}:7.5"]["iso_27001"]
    assert "CC7.3" in rows[f"{ISO27}:7.5"]["soc2"]


def _evaluators(rid: str) -> list[str]:
    return [s["ref"] for s in _iso27()[rid]["sources"] if s["kind"] == "evaluator"]


def test_prompt_injection_is_decided_by_the_adversarial_evaluator_alone() -> None:
    assert _evaluators(f"{ISO27}:6.9") == ["EVAL_ADVERSARIAL_V1"]


def test_injected_output_has_no_evaluator() -> None:
    assert _evaluators(f"{ISO27}:6.10") == []
    # 6.10 now also names a corroborating artifact, which backs an attestation up
    # without deciding the row, so the deciding sources are read from the data.
    deciding = {
        s["kind"]
        for s in _iso27()[f"{ISO27}:6.10"]["sources"]
        if s.get("role") != "corroborating"
    }
    assert deciding == {"attestation"}
    assert f"{ISO27}:6.10" not in attestation_only_ids(ISO27)


def test_only_the_annex_b_titles_say_the_numbering_is_provisional() -> None:
    marked = {
        rid.split(":", 1)[1]
        for rid, row in _iso27().items()
        if "(provisional numbering)" in row["title"]
    }
    assert marked == {"B.2", "B.3", "B.4", "B.5", "B.6", "B.7"}
    for rid, row in _iso27().items():
        if rid.split(":", 1)[1].startswith("B."):
            assert row["title"].endswith(" (provisional numbering)"), rid
            assert len(row["title"]) <= 80, rid


# --- flags ----------------------------------------------------------------------


def test_every_iso_row_stays_flagged_for_founder_review() -> None:
    for rows in (_iso42(), _iso27()):
        assert rows
        for rid, row in rows.items():
            assert row["needs_founder_review"] is True, rid


# --- behaviour: ISO/IEC 27090 evaluators ----------------------------------------


def _eval_report(**outcomes: EvaluatorOutcome) -> EvalReport:
    categories = {
        "EVAL_ADVERSARIAL_V1": EvaluatorCategory.ADVERSARIAL,
        "EVAL_SAFETY_LEXICAL_V1": EvaluatorCategory.SAFETY,
    }
    results = [
        EvaluatorResult(
            evaluator_id=evaluator_id,
            category=categories[evaluator_id],
            outcome=outcome,
            score=1.0 if outcome is EvaluatorOutcome.PASS else 0.0,
            threshold=0.9,
            metric_name="rate",
            sample_count=10,
            reference="test",
            evidence_hash="sha256:00",
        )
        for evaluator_id, outcome in (
            ("EVAL_ADVERSARIAL_V1", outcomes["adversarial"]),
            ("EVAL_SAFETY_LEXICAL_V1", outcomes["lexical"]),
        )
    ]
    return EvalReport(
        system_id="sys",
        commit_ref="HEAD",
        eval_set_id="SET",
        eval_set_version="1",
        threshold_policy_hash="sha256:00",
        results=results,
        evaluators_run=2,
        evaluators_failed=sum(r.outcome is EvaluatorOutcome.FAIL for r in results),
        evaluators_skipped=0,
        overall_outcome=EvaluatorOutcome.FAIL,
        generated_at="2026-11-09T00:00:00Z",
    )


def _iso27_status(rid: str, eval_report: EvalReport) -> GapStatus:
    manifest = SystemManifest(
        system_id="sys",
        intended_purpose="support chatbot",
        framework_inputs={
            ISO27: FrameworkInputs(attested={f"{ISO27}:{rid}": _ATTESTATION})
        },
    )
    report = evaluate_targets(
        manifest, [ISO27], commit_ref="HEAD", eval_report=eval_report, today=TODAY
    )[ISO27]
    return {r.article: r for r in report.report.articles}[f"{ISO27}:{rid}"].status


PASS, FAIL = EvaluatorOutcome.PASS, EvaluatorOutcome.FAIL


def test_a_failing_lexical_check_no_longer_touches_prompt_injection() -> None:
    report = _eval_report(adversarial=PASS, lexical=FAIL)
    assert _iso27_status("6.9", report) is GapStatus.MET


def test_a_failing_adversarial_check_makes_prompt_injection_missing() -> None:
    report = _eval_report(adversarial=FAIL, lexical=PASS)
    assert _iso27_status("6.9", report) is GapStatus.MISSING


def test_injected_output_is_met_when_attested_whatever_the_lexical_check_says() -> None:
    report = _eval_report(adversarial=PASS, lexical=FAIL)
    assert _iso27_status("6.10", report) is GapStatus.MET


# --- behaviour: NIST rows that take an attestation ------------------------------


def _gap(rows: list[ArticleGapStatus]) -> GapReport:
    return GapReport(
        system_id="sys",
        commit_ref="HEAD",
        generated_at="2026-11-09T00:00:00Z",
        articles=rows,
    )


def _row(
    article: str,
    status: GapStatus,
    source: ArticleGapSource = ArticleGapSource.RULE,
) -> ArticleGapStatus:
    return ArticleGapStatus(
        article=article, status=status, source=source, evidence_ref="x"
    )


def _sub(report, sid: str):
    return next(r for r in report.subcategories if r.subcategory == sid)


@pytest.mark.parametrize("sid", ATTESTATION_LED)
def test_a_dropped_article_cannot_fail_or_pass_the_row(sid: str) -> None:
    gap = _gap([_row(a, GapStatus.MISSING) for a in DROPPED])
    row = _sub(build_nist_rmf_report(gap), sid)
    assert row.status is GapStatus.UNVERIFIED
    assert row.confidence_label is ConfidenceLabel.NOT_ASSESSED
    assert row.source_eu_ai_act_articles == []
    assert row.rationale == NO_EVIDENCE
    met = _gap([_row(a, GapStatus.MET) for a in DROPPED])
    assert _sub(build_nist_rmf_report(met), sid).status is GapStatus.UNVERIFIED


def test_the_four_rows_are_met_with_an_attestation_through_a_full_run(
    tmp_path: Path,
) -> None:
    manifest = SystemManifest(
        system_id="sys",
        intended_purpose="credit scoring",
        framework_inputs={
            NIST: FrameworkInputs(
                attested={f"{NIST}:{sid}": _ATTESTATION for sid in ATTESTATION_LED}
            )
        },
    )
    reports = evaluate_targets(
        manifest,
        ["EU_AI_ACT", NIST],
        commit_ref="abc",
        repo_root=tmp_path,
        today=TODAY,
    )
    rows = {r.article: r for r in reports[NIST].report.articles}
    for sid in ATTESTATION_LED:
        row = rows[f"{NIST}:{sid}"]
        assert row.status is GapStatus.MET, sid
        assert row.source is ArticleGapSource.ATTESTATION, sid
        assert row.confidence_label is ConfidenceLabel.ATTESTED, sid


@pytest.mark.parametrize(
    ("sid", "others"),
    [("MANAGE 2.4", ["Art. 14"]), ("MANAGE 2.3", ["Art. 72", "Art. 73"])],
)
def test_an_attestation_decided_art_20_holds_the_row_at_unverified(
    sid: str, others: list[str]
) -> None:
    gap = _gap(
        [_row(a, GapStatus.MET) for a in others]
        + [_row("Art. 20", GapStatus.MET, ArticleGapSource.ATTESTATION)]
    )
    row = _sub(build_nist_rmf_report(gap), sid)
    assert row.status is GapStatus.UNVERIFIED
    assert row.source_eu_ai_act_articles == others
    assert row.rationale.endswith(SET_ASIDE)


def test_manage_2_4_still_fails_on_its_medium_link() -> None:
    gap = _gap(
        [
            _row("Art. 14", GapStatus.MISSING),
            _row("Art. 20", GapStatus.MET, ArticleGapSource.ATTESTATION),
        ]
    )
    row = _sub(build_nist_rmf_report(gap), "MANAGE 2.4")
    assert row.status is GapStatus.MISSING
    assert row.rationale.endswith(SET_ASIDE)


def test_manage_2_4_takes_no_attestation_of_its_own(tmp_path: Path) -> None:
    manifest = SystemManifest(
        system_id="sys",
        intended_purpose="credit scoring",
        checker_session=CheckerSessionRef(
            checker_version="checker-2026-10-26",
            session_id="s-1",
            completed_at="2026-11-01T00:00:00Z",
            obligation_ids=["deployer_general"],
        ),
        framework_inputs={
            NIST: FrameworkInputs(attested={f"{NIST}:MANAGE 2.4": _ATTESTATION})
        },
    )
    with pytest.raises(ValueError, match="takes an attestation"):
        evaluate_targets(
            manifest,
            ["EU_AI_ACT", NIST],
            commit_ref="abc",
            repo_root=tmp_path,
            today=TODAY,
        )
