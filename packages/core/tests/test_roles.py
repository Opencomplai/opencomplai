from __future__ import annotations

from opencomplai_core.models import SystemManifest
from opencomplai_core.roles import effective_roles


def _m(**kw: object) -> SystemManifest:
    return SystemManifest(
        system_id="s",
        intended_purpose="p",
        compliance_target="EU_AI_ACT",
        high_risk_presumption=False,
        commit_ref="c",
        **kw,
    )


def test_roles_prefers_operator_roles():
    assert effective_roles(_m(operator_roles=["provider", "deployer"])) == [
        "provider",
        "deployer",
    ]


def test_roles_falls_back_to_primary():
    assert effective_roles(_m(operator_role="deployer")) == ["deployer"]


def test_roles_empty_when_unset():
    assert effective_roles(_m()) == []


def test_primary_listed_first_and_deduped():
    m = _m(operator_role="deployer", operator_roles=["provider", "deployer"])
    assert effective_roles(m) == ["deployer", "provider"]
