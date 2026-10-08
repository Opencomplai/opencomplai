"""Smoke tests for the FLI compliance checker engine."""

from __future__ import annotations

from opencomplai_core.compliance_checker.catalog import (
    load_help_content,
    load_obligations,
    load_status_changes,
)
from opencomplai_core.compliance_checker.engine import CHECKER_VERSION, evaluate
from opencomplai_core.compliance_checker.models import CheckerSession, EntityType


def test_checker_version_constant():
    assert CHECKER_VERSION == "checker-2026-10-05"


def test_catalogs_load():
    obligations = load_obligations()
    status_changes = load_status_changes()
    help_content = load_help_content()
    assert "ai_literacy" in obligations
    assert "out_of_scope" in status_changes
    assert "ai_system_definition" in help_content


def test_not_ai_system_out_of_scope():
    result = evaluate(CheckerSession(answers={"gate_is_ai_system": False}))
    assert result.in_scope is False
    assert [item.id for item in result.status_changes] == ["out_of_scope"]
    assert result.obligations == []


def test_authorised_rep_only_obligation():
    result = evaluate(
        CheckerSession(
            answers={
                "gate_is_ai_system": True,
                "e1_entity_type": EntityType.AUTHORISED_REP.value,
            }
        )
    )
    assert result.in_scope is True
    assert [item.id for item in result.obligations] == ["authorised_representative"]
    assert result.status_changes == []


def test_provider_high_risk_gets_literacy_and_provider_obligations():
    result = evaluate(
        CheckerSession(
            answers={
                "gate_is_ai_system": True,
                "e1_entity_type": "provider",
                "hr2_annex_iii": True,
                "s1_in_scope": True,
            }
        )
    )
    obligation_ids = [item.id for item in result.obligations]
    assert "ai_literacy" in obligation_ids
    assert "provider_high_risk" in obligation_ids
    assert result.is_high_risk is True


def test_distributor_obligations_only_when_high_risk():
    low_risk = evaluate(
        CheckerSession(
            answers={
                "gate_is_ai_system": True,
                "e1_entity_type": "distributor",
                "s1_in_scope": True,
            }
        )
    )
    high_risk = evaluate(
        CheckerSession(
            answers={
                "gate_is_ai_system": True,
                "e1_entity_type": "distributor",
                "hr2_annex_iii": True,
                "s1_in_scope": True,
            }
        )
    )
    assert "distributor" not in [item.id for item in low_risk.obligations]
    assert "distributor" in [item.id for item in high_risk.obligations]


def test_become_provider_on_deployer_modification():
    result = evaluate(
        CheckerSession(
            answers={
                "gate_is_ai_system": True,
                "e1_entity_type": "deployer",
                "e2_modifications": True,
                "hr2_annex_iii": True,
                "s1_in_scope": True,
            }
        )
    )
    assert result.effective_entity == EntityType.PROVIDER
    assert "become_provider" in [item.id for item in result.status_changes]
    assert "provider_high_risk" in [item.id for item in result.obligations]


def test_deterministic_json_hash():
    session = CheckerSession(
        answers={
            "gate_is_ai_system": True,
            "e1_entity_type": "deployer",
            "hr2_annex_iii": True,
            "s1_in_scope": True,
            "s1_scope_region": "eu",
        }
    )
    first = evaluate(session)
    second = evaluate(session)
    assert first.model_dump_json() == second.model_dump_json()


def test_transparency_obligation_survives_high_risk():
    """H-09 regression: Art. 50 duties apply in addition to high-risk obligations."""
    result = evaluate(
        CheckerSession(
            answers={
                "gate_is_ai_system": True,
                "e1_entity_type": "provider",
                "hr2_annex_iii": True,
                "s1_in_scope": True,
                "r4_transparency": True,
            }
        )
    )
    assert result.is_high_risk is True
    assert "transparency" in [item.id for item in result.obligations]
    # transparency_only communicates "sole obligation tier" and must not fire
    # once high-risk obligations are also present.
    assert "transparency_only" not in [item.id for item in result.status_changes]


def test_transparency_only_status_still_gated_on_not_high_risk():
    result = evaluate(
        CheckerSession(
            answers={
                "gate_is_ai_system": True,
                "e1_entity_type": "provider",
                "s1_in_scope": True,
                "r4_transparency": True,
            }
        )
    )
    assert result.is_high_risk is False
    assert [item.id for item in result.obligations] == ["ai_literacy", "transparency"]
    assert "transparency_only" in [item.id for item in result.status_changes]


def test_annex_iii_profiling_overrides_art_6_3_exceptions():
    """H-10 golden case: profiling forces high-risk even if all four exceptions apply."""
    result = evaluate(
        CheckerSession(
            answers={
                "gate_is_ai_system": True,
                "e1_entity_type": "provider",
                "hr2_annex_iii": True,
                "hr7_profiling": True,
                "hr3_art_6_3": True,
                "hr4_narrow_task": True,
                "hr5_no_significant_risk": True,
                "hr6_accessory": True,
                "s1_in_scope": True,
            }
        )
    )
    assert result.is_high_risk is True


def test_annex_iii_exceptions_still_apply_without_profiling():
    """Negative case: without profiling, the Art. 6(3) exceptions still negate high-risk."""
    result = evaluate(
        CheckerSession(
            answers={
                "gate_is_ai_system": True,
                "e1_entity_type": "provider",
                "hr2_annex_iii": True,
                "hr7_profiling": False,
                "hr3_art_6_3": True,
                "hr4_narrow_task": True,
                "hr5_no_significant_risk": True,
                "hr6_accessory": True,
                "s1_in_scope": True,
            }
        )
    )
    assert result.is_high_risk is False


def test_profiling_override_requires_annex_iii():
    """Profiling alone (without Annex III applying) must not force high-risk."""
    result = evaluate(
        CheckerSession(
            answers={
                "gate_is_ai_system": True,
                "e1_entity_type": "provider",
                "hr2_annex_iii": False,
                "hr7_profiling": True,
                "s1_in_scope": True,
            }
        )
    )
    assert result.is_high_risk is False


def test_prohibited_short_circuits_other_obligations():
    result = evaluate(
        CheckerSession(
            answers={
                "gate_is_ai_system": True,
                "e1_entity_type": "provider",
                "hr2_annex_iii": True,
                "s1_in_scope": True,
                "r3_prohibited": True,
            }
        )
    )
    assert result.is_prohibited is True
    assert [item.id for item in result.obligations] == ["prohibited"]


def test_annex_i_alone_without_conformity_assessment_is_not_high_risk():
    """Art. 6(1) is conjunctive: a self-certified Annex I product (safety
    component present, but no required third-party conformity assessment) is
    not high-risk."""
    result = evaluate(
        CheckerSession(
            answers={
                "gate_is_ai_system": True,
                "e1_entity_type": "provider",
                "hr1_annex_i": True,
                "hr8_conformity_assessment": False,
                "s1_in_scope": True,
            }
        )
    )
    assert result.is_high_risk is False


def test_annex_i_with_conformity_assessment_is_high_risk():
    """Both Art. 6(1) prongs true (safety component + required third-party
    conformity assessment) triggers high-risk with no Art. 6(3) derogation
    available, since that derogation is Annex III-only."""
    result = evaluate(
        CheckerSession(
            answers={
                "gate_is_ai_system": True,
                "e1_entity_type": "provider",
                "hr1_annex_i": True,
                "hr8_conformity_assessment": True,
                "s1_in_scope": True,
            }
        )
    )
    assert result.is_high_risk is True


def test_art_6_3_exceptions_do_not_apply_to_annex_i_trigger():
    """The Art. 6(3)(a)-(d) exceptions are an Annex III derogation only; they
    must not excuse a high-risk Annex I trigger even when all four are set."""
    result = evaluate(
        CheckerSession(
            answers={
                "gate_is_ai_system": True,
                "e1_entity_type": "provider",
                "hr1_annex_i": True,
                "hr8_conformity_assessment": True,
                "hr3_art_6_3": True,
                "hr4_narrow_task": True,
                "hr5_no_significant_risk": True,
                "hr6_accessory": True,
                "s1_in_scope": True,
            }
        )
    )
    assert result.is_high_risk is True


def test_art_6_3_exceptions_still_apply_to_annex_iii_only_trigger():
    """Regression guard: the fix that scopes the Art. 6(3) derogation to
    Annex III must not also block it for a system with no Annex I trigger."""
    result = evaluate(
        CheckerSession(
            answers={
                "gate_is_ai_system": True,
                "e1_entity_type": "provider",
                "hr2_annex_iii": True,
                "hr3_art_6_3": True,
                "s1_in_scope": True,
            }
        )
    )
    assert result.is_high_risk is False


def _provider_derogation(**extra):
    answers = {
        "gate_is_ai_system": True,
        "e1_entity_type": "provider",
        "hr2_annex_iii": True,
        "s1_in_scope": True,
        **extra,
    }
    return evaluate(CheckerSession(answers=answers))


def test_provider_derogation_yields_registration_duty():
    for key in (
        "hr3_art_6_3",
        "hr4_narrow_task",
        "hr5_no_significant_risk",
        "hr6_accessory",
    ):
        result = _provider_derogation(**{key: True})
        assert result.is_high_risk is False, key
        assert "provider_art_6_4_registration" in [o.id for o in result.obligations]
        assert "hr:derogation_registration" in result.determination_path


def test_derogation_registration_not_for_deployer_or_profiling():
    deployer = evaluate(
        CheckerSession(
            answers={
                "gate_is_ai_system": True,
                "e1_entity_type": "deployer",
                "hr2_annex_iii": True,
                "hr3_art_6_3": True,
            }
        )
    )
    profiling = _provider_derogation(hr3_art_6_3=True, hr7_profiling=True)
    for result in (deployer, profiling):
        assert "provider_art_6_4_registration" not in [o.id for o in result.obligations]


def test_fria_requires_annex_iii():
    result = evaluate(
        CheckerSession(
            answers={
                "gate_is_ai_system": True,
                "e1_entity_type": "deployer",
                "hr1_annex_i": True,
                "hr8_conformity_assessment": True,
                "r5_fria": True,
            }
        )
    )
    assert result.is_high_risk is True
    assert "fria" not in [o.id for o in result.obligations]
