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
    assert CHECKER_VERSION == "checker-2025-07-28"


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
