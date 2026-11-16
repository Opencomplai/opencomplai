"""The conditions the framework-mapping review attached to its accepted rows.

Several rows were accepted on the footing that an EU AI Act article resolves to "not
applicable" for most operators. Each test below checks that footing against the checker
engine and the NIST re-projection, with the checker session the engine itself produces.
Without a recorded checker session no article moves to not applicable, so these conditions
hold for a run that has one.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from opencomplai_core.compliance_checker.engine import evaluate
from opencomplai_core.compliance_checker.models import CheckerSession
from opencomplai_core.framework_crosswalk import get_crosswalk
from opencomplai_core.frameworks import (
    EU_AI_ACT,
    FRAMEWORKS,
    evaluate_targets,
    load_requirements_map,
)
from opencomplai_core.models import (
    Attestation,
    CheckerSessionRef,
    ConfidenceLabel,
    GapReport,
    GapStatus,
    RmfSubcategoryStatus,
    SystemManifest,
)
from opencomplai_core.nist_rmf_report import build_nist_rmf_report

TODAY = date(2026, 11, 9)

# Checker answers per operator, for the Annex III case unless the name says otherwise.
PROVIDER: dict[str, Any] = {"e1_entity_type": "provider", "hr2_annex_iii": True}
PROVIDER_NOT_HIGH_RISK: dict[str, Any] = {"e1_entity_type": "provider"}
DEPLOYER_IN_ART_27: dict[str, Any] = {
    "e1_entity_type": "deployer",
    "hr2_annex_iii": True,
    "r5_fria": True,
}
DEPLOYER_OUTSIDE_ART_27: dict[str, Any] = {**DEPLOYER_IN_ART_27, "r5_fria": False}
# Art. 27 covers Annex III systems only, so an Annex I deployer is outside it too.
DEPLOYER_ANNEX_I: dict[str, Any] = {
    "e1_entity_type": "deployer",
    "hr1_annex_i": True,
    "hr8_conformity_assessment": True,
    "r5_fria": True,
}
GPAI: dict[str, Any] = {"e1_entity_type": "provider", "s1_gpai": True}
GPAI_SYSTEMIC: dict[str, Any] = {**GPAI, "s1_gpai_systemic_risk": True}

_ATTESTATION = Attestation(
    statement="Operators are trained each year.",
    attested_by="Compliance lead",
    attested_at="2026-11-01",
)


def _checker_session(answers: dict[str, Any]) -> CheckerSessionRef:
    result = evaluate(CheckerSession(answers={"gate_is_ai_system": True, **answers}))
    return CheckerSessionRef(
        checker_version=result.checker_version,
        session_id="s-1",
        completed_at="2026-11-09T00:00:00Z",
        obligation_ids=[item.id for item in result.obligations],
    )


def _eu(answers: dict[str, Any]) -> GapReport:
    manifest = SystemManifest(
        system_id="sys",
        intended_purpose="credit scoring",
        checker_session=_checker_session(answers),
    )
    return evaluate_targets(manifest, [EU_AI_ACT], commit_ref="abc", today=TODAY)[
        EU_AI_ACT
    ].report


def _force(eu: GapReport, article: str, status: GapStatus) -> GapReport:
    """The same report with one article's row set to `status`."""
    rows = [
        r.model_copy(update={"status": status}) if r.article == article else r
        for r in eu.articles
    ]
    return eu.model_copy(update={"articles": rows})


def _sub(
    eu: GapReport, sid: str, attested: dict[str, Attestation] | None = None
) -> RmfSubcategoryStatus:
    report = build_nist_rmf_report(eu, attested, TODAY)
    return next(r for r in report.subcategories if r.subcategory == sid)


def _cited(eu: GapReport, sid: str) -> list[str]:
    return _sub(eu, sid).source_eu_ai_act_articles


def test_the_checker_records_fria_only_for_an_annex_iii_deployer_art_27_binds() -> None:
    """NIST AI RMF / GOVERN 4.2 and MAP 5.1 rest on this: the checker records the
    `fria` obligation only for a deployer of an Annex III high-risk system who is a
    public body, a provider of public services or a credit or insurance deployer."""
    assert "fria" in _checker_session(DEPLOYER_IN_ART_27).obligation_ids
    for answers in (PROVIDER, DEPLOYER_OUTSIDE_ART_27, DEPLOYER_ANNEX_I):
        assert "fria" not in _checker_session(answers).obligation_ids, answers


def test_govern_4_2_cites_art_27_only_for_a_deployer_it_binds() -> None:
    """NIST AI RMF / GOVERN 4.2: the fundamental rights assessment (Art. 27) is not
    applicable for a provider and for a deployer outside Art. 27(1), so the row neither
    cites nor depends on it there; a deployer the article binds keeps it."""
    for answers in (PROVIDER, DEPLOYER_OUTSIDE_ART_27, DEPLOYER_ANNEX_I):
        eu = _eu(answers)
        assert "Art. 27" in eu.not_applicable, answers
        assert "Art. 27" not in _cited(eu, "GOVERN 4.2"), answers
    eu = _eu(DEPLOYER_IN_ART_27)
    assert "Art. 27" not in eu.not_applicable
    assert "Art. 27" in _cited(eu, "GOVERN 4.2")


def test_map_5_1_cites_art_27_only_for_a_deployer_it_binds() -> None:
    """NIST AI RMF / MAP 5.1: the same Art. 27 condition as GOVERN 4.2. For a provider the
    medium Art. 9 link carries the row alone, so a missing Art. 9 reads Missing; a
    deployer the fundamental rights assessment binds is read through Art. 27."""
    provider = _eu(PROVIDER)
    assert "Art. 27" in provider.not_applicable
    assert _cited(provider, "MAP 5.1") == ["Art. 9"]
    row = _sub(_force(provider, "Art. 9", GapStatus.MISSING), "MAP 5.1")
    assert (row.status, row.mapping_confidence) == (GapStatus.MISSING, "medium")

    outside = _eu(DEPLOYER_OUTSIDE_ART_27)
    assert "Art. 27" in outside.not_applicable
    assert _cited(outside, "MAP 5.1") == []  # Art. 9 does not bind a deployer either

    bound = _eu(DEPLOYER_IN_ART_27)
    assert "Art. 27" not in bound.not_applicable
    assert _cited(bound, "MAP 5.1") == ["Art. 27"]


def test_map_3_4_takes_an_attestation_when_art_26_is_not_applicable() -> None:
    """NIST AI RMF / MAP 3.4: for a provider-only operator Art. 26 is not applicable, so
    the row (Art. 4 is attestation-led too) reads Unverified until attested and is Met
    once attested; for a deployer of a high-risk system Art. 26 stays and the row is read
    from it, with an attestation recorded for it left unused."""
    key = "NIST_AI_RMF:MAP 3.4"
    for answers in (PROVIDER, PROVIDER_NOT_HIGH_RISK, GPAI):
        eu = _eu(answers)
        assert "Art. 26" in eu.not_applicable, answers
        row = _sub(eu, "MAP 3.4")
        assert row.status is GapStatus.UNVERIFIED, answers
        assert row.confidence_label is ConfidenceLabel.NOT_ASSESSED, answers
        assert row.source_eu_ai_act_articles == [], answers
        assert "not applicable: Art. 26" in row.rationale, answers
        attested = _sub(eu, "MAP 3.4", {key: _ATTESTATION})
        assert attested.status is GapStatus.MET, answers
        assert attested.confidence_label is ConfidenceLabel.ATTESTED, answers

    deployer = _eu(DEPLOYER_OUTSIDE_ART_27)
    assert "Art. 26" not in deployer.not_applicable
    row = _sub(deployer, "MAP 3.4", {key: _ATTESTATION})
    assert row.source_eu_ai_act_articles == ["Art. 26"]
    assert row.status is GapStatus.UNVERIFIED  # the attestation does not lift it
    assert "is not used" in row.rationale


def test_map_4_1_cites_art_53_only_for_a_general_purpose_model_provider() -> None:
    """NIST AI RMF / MAP 4.1: Art. 53 binds providers of general-purpose AI models only,
    so it is not applicable for any other operator and Art. 25, the supplier-agreement
    link, is what the row reads; a provider who answered the GPAI question keeps Art. 53."""
    for answers in (PROVIDER, PROVIDER_NOT_HIGH_RISK, DEPLOYER_IN_ART_27):
        eu = _eu(answers)
        assert "Art. 53" in eu.not_applicable, answers
        assert _cited(eu, "MAP 4.1") == ["Art. 25"], answers
    for answers in (GPAI, GPAI_SYSTEMIC):
        eu = _eu(answers)
        assert "Art. 53" not in eu.not_applicable, answers
        assert _cited(eu, "MAP 4.1") == ["Art. 25", "Art. 53"], answers


def test_measure_2_7_cites_art_55_only_for_a_systemic_risk_model_provider() -> None:
    """NIST AI RMF / MEASURE 2.7: Art. 55 binds providers of general-purpose models with
    systemic risk only, so it is not applicable otherwise (a plain GPAI provider
    included) and the medium Art. 15 link alone carries the row, so a missing Art. 15
    reads Missing; a systemic-risk provider keeps Art. 55 beside it."""
    for answers in (PROVIDER, PROVIDER_NOT_HIGH_RISK, GPAI):
        eu = _eu(answers)
        assert "Art. 55" in eu.not_applicable, answers
        assert _cited(eu, "MEASURE 2.7") == ["Art. 15"], answers
        row = _sub(_force(eu, "Art. 15", GapStatus.MISSING), "MEASURE 2.7")
        assert (row.status, row.mapping_confidence) == (GapStatus.MISSING, "medium")
    eu = _eu(GPAI_SYSTEMIC)
    assert "Art. 55" not in eu.not_applicable
    assert _cited(eu, "MEASURE 2.7") == ["Art. 15", "Art. 55"]


def test_iso_42001_scope_and_improvement_clauses_carry_the_reviewed_links() -> None:
    """ISO 42001 / Clause 4.3 and Clause 10.1: the scope clause links Art. 6, because
    classification decides which systems fall in scope, and continual improvement
    links Art. 17 beside Art. 72. The links are informational: both rows stay decided
    by an attestation alone."""
    rows = load_requirements_map(FRAMEWORKS["ISO_IEC_42001"].requirements)
    assert rows["ISO_IEC_42001:Clause 4.3"]["eu_ai_act"] == ["Art. 6"]
    assert rows["ISO_IEC_42001:Clause 10.1"]["eu_ai_act"] == ["Art. 17", "Art. 72"]
    # A corroborating artifact only backs an attestation up; it does not decide the row.
    for rid in ("ISO_IEC_42001:Clause 4.3", "ISO_IEC_42001:Clause 10.1"):
        deciding = {
            s["kind"] for s in rows[rid]["sources"] if s.get("role") != "corroborating"
        }
        assert deciding == {"attestation"}


def test_the_art_4_crosswalk_row_names_a_4_6_for_human_resources() -> None:
    """ISO 42001 / A.4.6: the crosswalk's Art. 4 row points at A.4.6 (human resources),
    not at A.4.5 (system and computing resources), as the review asked."""
    annex_a = get_crosswalk()["Art. 4"].iso_42001_annex_a_control
    assert annex_a is not None
    assert annex_a.startswith("A.4.6")
    assert "A.4.5" not in annex_a
