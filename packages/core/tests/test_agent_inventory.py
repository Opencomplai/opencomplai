"""Agent inventory model, omit-when-absent wiring and deep graph checks."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from opencomplai_core.agent_inventory import AgentInventory, check_inventory
from opencomplai_core.control_identity import fingerprint_manifest
from opencomplai_core.models import SystemManifest
from pydantic import ValidationError

_LEGACY_MANIFEST = json.loads(
    (Path(__file__).parent / "fixtures" / "legacy_manifest.json").read_text(
        encoding="utf-8"
    )
)


def _inv(*agents: dict) -> AgentInventory:
    return AgentInventory.model_validate({"agents": list(agents)})


def _a(id: str, parent: str | None = None, **extra) -> dict:
    return {"id": id, "name": id.upper(), "parent_id": parent, **extra}


def test_manifest_without_inventory_serialises_identically():
    legacy_json = json.dumps(_LEGACY_MANIFEST, indent=2)
    manifest = SystemManifest.model_validate_json(legacy_json)
    assert manifest.agent_inventory is None
    assert manifest.model_dump_json(indent=2) == legacy_json


def test_valid_inventory_round_trips():
    inv = AgentInventory.model_validate(
        {
            "agents": [
                _a(
                    "root",
                    tools=[
                        {
                            "name": "search",
                            "kind": "mcp",
                            "scope": "read",
                            "side_effects": False,
                            "requires_approval": False,
                        }
                    ],
                    models=[{"provider": "acme", "model": "m1", "via": "gateway"}],
                    mandate={
                        "permitted_actions": ["tool:search"],
                        "prohibited_actions": ["pay"],
                        "limits": {"max_spend": 10, "dry_run": True, "region": "eu"},
                        "granted_by": "cto",
                        "granted_at": "2026-01-01",
                        "expires_at": "2027-01-01T00:00:00",
                        "review_cadence": "quarterly",
                    },
                    delegation={"may_delegate_to": ["child"], "max_depth": 1},
                    guardrails=[{"kind": "pii-filter", "evidence_ref": "docs/g.md"}],
                    logging={
                        "decision_log_ref": "logs/d.jsonl",
                        "captures_intent": True,
                    },
                ),
                _a("child", "root"),
            ],
            "responsibility_map": {
                "customer_obligations": ["review output"],
                "upstream_provider_obligations": ["model card"],
            },
        }
    )
    assert check_inventory(inv) == []
    assert AgentInventory.model_validate_json(inv.model_dump_json()) == inv


def test_unknown_field_rejected():
    with pytest.raises(ValidationError):
        AgentInventory.model_validate({"agents": [_a("a")], "bogus": 1})


def test_duplicate_agent_id_rejected():
    with pytest.raises(ValidationError, match="duplicate agent id 'a'"):
        _inv(_a("a"), _a("a"))


def test_bad_mandate_date_rejected():
    with pytest.raises(ValidationError):
        _inv(_a("a", mandate={"granted_at": "yesterday"}))


def test_dangling_parent_reported():
    errors = check_inventory(_inv(_a("a", "ghost")))
    assert errors
    assert "'a'" in errors[0]
    assert "dangling parent" in errors[0]


def test_cycle_detected():
    selfish = check_inventory(_inv(_a("a", "a")))
    assert any("'a'" in e and "cycle" in e for e in selfish)
    loop = check_inventory(_inv(_a("a", "c"), _a("b", "a"), _a("c", "b")))
    assert any("cycle" in e for e in loop)
    # an agent hanging below the loop must not hang the walk either
    below = check_inventory(
        _inv(_a("a", "b"), _a("b", "a"), _a("z", "a", delegation={"max_depth": 0}))
    )
    assert any("cycle" in e for e in below)
    assert not any("depth" in e for e in below)


def test_delegation_depth_exceeded():
    inv = _inv(_a("r", delegation={"max_depth": 1}), _a("m", "r"), _a("leaf", "m"))
    assert check_inventory(inv) == ["agent 'r': delegation depth 2 exceeds max_depth 1"]


def test_delegation_depth_at_limit_passes():
    inv = _inv(_a("r", delegation={"max_depth": 2}), _a("m", "r"), _a("leaf", "m"))
    assert check_inventory(inv) == []


def test_dangling_delegate_reported():
    errors = check_inventory(_inv(_a("a", delegation={"may_delegate_to": ["nope"]})))
    assert errors
    assert "'a'" in errors[0]
    assert "dangling delegate" in errors[0]


def test_unknown_tool_ref_reported():
    inv = _inv(_a("a", mandate={"permitted_actions": ["tool:ghost"]}))
    errors = check_inventory(inv)
    assert errors
    assert "'a'" in errors[0]
    assert "unknown tool ref" in errors[0]
    inv = _inv(_a("a", mandate={"prohibited_actions": ["tool:ghost"]}))
    assert check_inventory(inv)


def test_known_tool_ref_passes():
    inv = _inv(
        _a(
            "a",
            tools=[{"name": "t", "kind": "function"}],
            mandate={"permitted_actions": ["tool:t", "free text"]},
        )
    )
    assert check_inventory(inv) == []


def test_fingerprint_ignores_inventory():
    base = SystemManifest.model_validate(_LEGACY_MANIFEST)
    with_inv = base.model_copy(update={"agent_inventory": _inv(_a("a"))})
    assert fingerprint_manifest(with_inv) == fingerprint_manifest(base)
