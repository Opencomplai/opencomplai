"""Deterministic compliance checker engine."""

from __future__ import annotations

from typing import Any

from opencomplai_core.compliance_checker.catalog import (
    get_obligation,
    get_status_change,
)
from opencomplai_core.compliance_checker.models import (
    CHECKER_VERSION,
    CheckerSession,
    ComplianceCheckerResult,
    EntityType,
    ObligationItem,
    StatusChangeItem,
)

__all__ = ["CHECKER_VERSION", "evaluate"]


def _answer_bool(answers: dict[str, Any], key: str, default: bool = False) -> bool:
    value = answers.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"true", "yes", "1"}
    return bool(value)


def _answer_entity(answers: dict[str, Any]) -> EntityType:
    raw = answers.get("e1_entity_type", EntityType.PROVIDER.value)
    return EntityType(raw)


def _determine_high_risk(answers: dict[str, Any]) -> bool:
    # Art. 6(1) is conjunctive: an Annex I product is high-risk only if it has
    # an AI safety component AND is required to undergo third-party conformity
    # assessment. hr1 alone (self-certified Annex I product) does not trigger
    # high-risk.
    hr1 = _answer_bool(answers, "hr1_annex_i") and _answer_bool(
        answers, "hr8_conformity_assessment"
    )
    hr2 = _answer_bool(answers, "hr2_annex_iii")
    if not (hr1 or hr2):
        return False
    # Art. 6(3) final subparagraph: an Annex III system that performs profiling
    # of natural persons is always high-risk, overriding the (a)-(d) exceptions
    # below. Must be evaluated ahead of them.
    if hr2 and _answer_bool(answers, "hr7_profiling"):
        return True
    # The Art. 6(3)(a)-(d) exceptions are an Annex III derogation only (final
    # subparagraph of Art. 6(3)); an Annex I trigger has no such exception.
    if hr2 and not hr1:
        if _answer_bool(answers, "hr3_art_6_3"):
            return False
        if _answer_bool(answers, "hr4_narrow_task"):
            return False
        if _answer_bool(answers, "hr5_no_significant_risk"):
            return False
        if _answer_bool(answers, "hr6_accessory"):
            return False
    return True


def _relies_on_art_6_3_derogation(answers: dict[str, Any]) -> bool:
    """Annex III system the provider assesses as not high-risk (Art. 6(3))."""
    annex_i = _answer_bool(answers, "hr1_annex_i") and _answer_bool(
        answers, "hr8_conformity_assessment"
    )
    return (
        _answer_bool(answers, "hr2_annex_iii")
        and not annex_i
        and not _answer_bool(answers, "hr7_profiling")
        and any(
            _answer_bool(answers, k)
            for k in (
                "hr3_art_6_3",
                "hr4_narrow_task",
                "hr5_no_significant_risk",
                "hr6_accessory",
            )
        )
    )


def _dedupe_obligations(items: list[ObligationItem]) -> list[ObligationItem]:
    seen: set[str] = set()
    ordered: list[ObligationItem] = []
    for item in items:
        if item.id in seen:
            continue
        seen.add(item.id)
        ordered.append(item)
    return ordered


def _dedupe_status(items: list[StatusChangeItem]) -> list[StatusChangeItem]:
    seen: set[str] = set()
    ordered: list[StatusChangeItem] = []
    for item in items:
        if item.id in seen:
            continue
        seen.add(item.id)
        ordered.append(item)
    return ordered


def _build_result(
    *,
    in_scope: bool,
    path: list[str],
    status_ids: list[str],
    obligation_ids: list[str],
    is_high_risk: bool = False,
    is_prohibited: bool = False,
    effective_entity: EntityType | None = None,
    answers: dict[str, Any] | None = None,
) -> ComplianceCheckerResult:
    return ComplianceCheckerResult(
        checker_version=CHECKER_VERSION,
        in_scope=in_scope,
        determination_path=path,
        status_changes=[get_status_change(status_id) for status_id in status_ids],
        obligations=_dedupe_obligations(
            [get_obligation(obligation_id) for obligation_id in obligation_ids]
        ),
        is_high_risk=is_high_risk,
        is_prohibited=is_prohibited,
        effective_entity=effective_entity,
        answers=answers or {},
    )


def _entity_obligations(
    entity: EntityType,
    *,
    is_high_risk: bool,
) -> list[str]:
    obligation_ids: list[str] = []

    if entity == EntityType.PROVIDER:
        if is_high_risk:
            obligation_ids.append("provider_high_risk")
    elif entity == EntityType.DEPLOYER:
        if is_high_risk:
            obligation_ids.extend(["deployer_high_risk", "deployer_general"])
        else:
            obligation_ids.append("deployer_general")
    elif entity == EntityType.DISTRIBUTOR:
        if is_high_risk:
            obligation_ids.append("distributor")
    elif entity == EntityType.IMPORTER:
        if is_high_risk:
            obligation_ids.append("importer")
    elif entity == EntityType.PRODUCT_MANUFACTURER:
        obligation_ids.append("product_manufacturer")
        if is_high_risk:
            obligation_ids.append("provider_high_risk")

    return obligation_ids


def evaluate(session: CheckerSession) -> ComplianceCheckerResult:
    """Evaluate a checker session using FLI July 2025 flowchart logic."""
    answers = session.answers
    path: list[str] = []
    status_ids: list[str] = []
    obligation_ids: list[str] = []

    if not _answer_bool(answers, "gate_is_ai_system", default=True):
        path.append("gate:no")
        return _build_result(
            in_scope=False,
            path=path,
            status_ids=["out_of_scope"],
            obligation_ids=[],
            answers=answers,
        )
    path.append("gate:yes")

    entity = _answer_entity(answers)
    effective_entity = entity
    path.append(f"e1:{entity.value}")

    if entity == EntityType.AUTHORISED_REP:
        return _build_result(
            in_scope=True,
            path=path,
            status_ids=[],
            obligation_ids=["authorised_representative"],
            effective_entity=effective_entity,
            answers=answers,
        )

    if _answer_bool(answers, "e2_modifications"):
        if entity == EntityType.PROVIDER:
            status_ids.append("handover")
            path.append("e2:handover")
        else:
            status_ids.append("become_provider")
            effective_entity = EntityType.PROVIDER
            path.append("e2:become_provider")

    if entity == EntityType.PRODUCT_MANUFACTURER:
        integration = answers.get("e3_product_integration", "none")
        if integration == "none":
            path.append("e3:none")
            return _build_result(
                in_scope=False,
                path=path,
                status_ids=_dedupe_status_ids([*status_ids, "out_of_scope"]),
                obligation_ids=[],
                effective_entity=entity,
                answers=answers,
            )

    is_high_risk = _determine_high_risk(answers)
    if is_high_risk:
        status_ids.append("high_risk")
        path.append("hr:high_risk")

    if not _answer_bool(answers, "s1_in_scope", default=True):
        path.append("s1:none")
        return _build_result(
            in_scope=False,
            path=path,
            status_ids=_dedupe_status_ids([*status_ids, "out_of_scope"]),
            obligation_ids=[],
            is_high_risk=is_high_risk,
            effective_entity=effective_entity,
            answers=answers,
        )
    path.append("s1:in_scope")

    scope_region = answers.get("s1_scope_region", "eu")
    hr1 = _answer_bool(answers, "hr1_annex_i")
    hr2 = _answer_bool(answers, "hr2_annex_iii")
    if (
        effective_entity == EntityType.DEPLOYER
        and scope_region == "eu"
        and hr2
        and not hr1
        and is_high_risk
    ):
        status_ids.append("high_risk_exception")
        path.append("s1:high_risk_exception")

    if _answer_bool(answers, "r2_excluded"):
        path.append("r2:excluded")
        return _build_result(
            in_scope=False,
            path=path,
            status_ids=_dedupe_status_ids([*status_ids, "out_of_scope"]),
            obligation_ids=[],
            is_high_risk=is_high_risk,
            effective_entity=effective_entity,
            answers=answers,
        )

    if _answer_bool(answers, "r3_prohibited"):
        path.append("r3:prohibited")
        return _build_result(
            in_scope=True,
            path=path,
            status_ids=_dedupe_status_ids([*status_ids, "prohibited"]),
            obligation_ids=["prohibited"],
            is_high_risk=is_high_risk,
            is_prohibited=True,
            effective_entity=effective_entity,
            answers=answers,
        )

    if effective_entity in {EntityType.PROVIDER, EntityType.DEPLOYER}:
        obligation_ids.append("ai_literacy")
        path.append("e1:ai_literacy")

    if _answer_bool(answers, "s1_gpai"):
        status_ids.append("gpai")
        obligation_ids.append("gpai_provider")
        path.append("r1:gpai")
        if _answer_bool(answers, "s1_gpai_systemic_risk"):
            obligation_ids.append("gpai_systemic_risk")
            path.append("r1:gpai_systemic_risk")

    obligation_ids.extend(
        _entity_obligations(effective_entity, is_high_risk=is_high_risk)
    )

    if effective_entity == EntityType.PROVIDER and _relies_on_art_6_3_derogation(
        answers
    ):
        obligation_ids.append("provider_art_6_4_registration")
        path.append("hr:derogation_registration")

    if _answer_bool(answers, "r4_transparency"):
        # Art. 50 disclosure duties apply in addition to high-risk obligations,
        # not instead of them, so the obligation itself is never gated on
        # is_high_risk. Only the "transparency_only" status — which communicates
        # that this is the sole obligation tier — stays high-risk-gated.
        obligation_ids.append("transparency")
        path.append("r4:transparency")
        if not is_high_risk:
            non_literacy = [oid for oid in obligation_ids if oid != "ai_literacy"]
            if obligation_ids == ["ai_literacy", "transparency"] or (
                len(non_literacy) == 1 and non_literacy[0] == "transparency"
            ):
                status_ids.append("transparency_only")

    if (
        _answer_bool(answers, "r5_fria")
        and is_high_risk
        # Art. 27 applies to Art. 6(2) (Annex III) systems only.
        and _answer_bool(answers, "hr2_annex_iii")
        and effective_entity == EntityType.DEPLOYER
    ):
        obligation_ids.append("fria")
        path.append("r5:fria")

    return _build_result(
        in_scope=True,
        path=path,
        status_ids=_dedupe_status_ids(status_ids),
        obligation_ids=obligation_ids,
        is_high_risk=is_high_risk,
        effective_entity=effective_entity,
        answers=answers,
    )


def _dedupe_status_ids(status_ids: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for status_id in status_ids:
        if status_id in seen:
            continue
        seen.add(status_id)
        ordered.append(status_id)
    return ordered
