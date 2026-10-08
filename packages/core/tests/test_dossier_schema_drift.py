"""
data/annex_iv_dossier.schema.json is generated from
`AnnexIVDossier.model_json_schema()` (scripts/generate_dossier_schema.py) so
external consumers (the doc-generator service, dashboard-saas, auditors) have
a machine-readable JSON Schema for the dossier without hand-maintaining one
that can silently fall out of sync with the pydantic model.

This test fails loud — mirroring control_catalog.get_catalog()'s fail-loud
convention — if the committed file ever disagrees with a fresh
model_json_schema() call: regenerate with `python scripts/generate_dossier_schema.py`
after any AnnexIVDossier/AnnexIVSection* model change, and commit the result.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
from opencomplai_core.dossier import AnnexIVDossier

_SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "opencomplai_core"
    / "data"
    / "annex_iv_dossier.schema.json"
)


def _committed_schema() -> dict:
    assert _SCHEMA_PATH.is_file(), (
        f"{_SCHEMA_PATH} is missing — run `python scripts/generate_dossier_schema.py`"
    )
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def test_schema_file_matches_model() -> None:
    fresh = AnnexIVDossier.model_json_schema()
    committed = _committed_schema()
    assert committed == fresh, (
        "data/annex_iv_dossier.schema.json has drifted from "
        "AnnexIVDossier.model_json_schema() — run "
        "`python scripts/generate_dossier_schema.py` and commit the result."
    )


def test_schema_validates_a_sample_dossier() -> None:
    """A representative HIGH-risk-complete dossier must satisfy the committed schema."""
    sample = AnnexIVDossier(
        dossier_id="11111111-1111-1111-1111-111111111111",
        system_id="sample-system",
        commit_ref="abc1234",
        generated_at="2026-09-18T00:00:00+00:00",
        section1={
            "system_name": "sample-system",
            "system_version": "abc1234",
            "provider_name": "Sample Provider",
            "intended_purpose": "Demonstration only.",
            "compliance_target": "EU_AI_ACT",
            "risk_class": "low",
            "deployment_context": "production",
        },
        section2={
            "training_data_description": "Synthetic sample data.",
            "model_architecture": "Sample architecture.",
        },
        section3={},
        section4={},
        section5={
            "risk_assessment_id": "ra_sample",
            "risk_level": "low",
            "rules_evaluated": 1,
            "rules_passed": 1,
            "rules_failed": 0,
            "rationale_hash": "sha256:0" * 8,
        },
        bundle_checksum="sha256:" + "0" * 64,
    )
    jsonschema.validate(
        instance=json.loads(sample.model_dump_json()), schema=_committed_schema()
    )


def test_record_keeping_retention_is_optional_in_schema() -> None:
    record_keeping = _committed_schema()["$defs"]["ArticleTwelveRecordKeeping"]
    assert record_keeping.get("required", []) == []
    assert "provider_supplied" in record_keeping["properties"]
    assert "log_retention_days" in record_keeping["properties"]


def test_section3_human_oversight_is_optional_in_schema() -> None:
    schema = _committed_schema()
    section3 = schema["$defs"]["AnnexIVSection3"]
    assert "human_oversight" in section3["properties"]
    assert "human_oversight" not in section3.get("required", [])
    legacy = AnnexIVDossier(
        dossier_id="11111111-1111-1111-1111-111111111111",
        system_id="s",
        commit_ref="abc1234",
        generated_at="2026-09-18T00:00:00+00:00",
        section1={
            "system_name": "s",
            "system_version": "v",
            "provider_name": "p",
            "intended_purpose": "x",
            "compliance_target": "EU_AI_ACT",
            "risk_class": "low",
            "deployment_context": "production",
        },
        section2={"training_data_description": "t", "model_architecture": "m"},
        section3={},
        section4={},
        section5={
            "risk_assessment_id": "ra",
            "risk_level": "low",
            "rules_evaluated": 1,
            "rules_passed": 1,
            "rules_failed": 0,
            "rationale_hash": "sha256:0",
        },
        bundle_checksum="sha256:" + "0" * 64,
    )
    instance = json.loads(legacy.model_dump_json())
    assert "human_oversight" not in instance["section3"]
    jsonschema.validate(instance=instance, schema=schema)


def test_agent_inventory_is_optional_in_schema() -> None:
    schema = _committed_schema()
    assert "agent_inventory" in schema["properties"]
    assert "agent_inventory" not in schema.get("required", [])
    assert "AgentInventory" in schema["$defs"]
    # A dossier without the block still validates (the key is simply absent).
    test_section3_human_oversight_is_optional_in_schema()


def test_compliance_target_description_names_the_iso_pack() -> None:
    target = _committed_schema()["$defs"]["ComplianceTarget"]
    description = target["description"]
    assert "ISO_IEC_42001" in description
    assert "attestation-led" in description
    assert "mapped only, not a target" not in description
    assert "never as an assessment target" not in description
    # E-13: ISO is a framework pack, never a new enum member.
    assert target["enum"] == ["EU_AI_ACT", "NIST_AI_RMF"]
