"""The six Art. 13(3) manifest fields vanish from output when unset."""

from __future__ import annotations

import json

from opencomplai_core.models import SystemManifest

ART13_FIELDS = (
    "provider_contact",
    "foreseeable_misuse",
    "input_data_specifications",
    "predetermined_changes",
    "expected_lifetime_and_maintenance",
    "log_interpretation",
)

_BASE = {
    "system_id": "sys-1",
    "intended_purpose": "credit scoring",
    "compliance_target": "EU_AI_ACT",
    "high_risk_presumption": True,
    "commit_ref": "abc123",
}


def test_unset_art13_fields_are_omitted_from_serialised_manifest():
    manifest = SystemManifest(**_BASE)
    dumped = json.loads(manifest.model_dump_json())
    for name in ART13_FIELDS:
        assert name not in dumped
        assert name not in manifest.model_dump()


def test_set_art13_fields_round_trip():
    manifest = SystemManifest(
        **_BASE,
        provider_contact="Acme AI, ops@example.com",
        foreseeable_misuse=["used on minors"],
        input_data_specifications="PDF, UTF-8, under 5 MB",
        predetermined_changes=["quarterly recalibration"],
        expected_lifetime_and_maintenance="5 years, patched monthly",
        log_interpretation="JSON lines, one event per decision",
    )
    dumped = json.loads(manifest.model_dump_json())
    for name in ART13_FIELDS:
        assert name in dumped
    again = SystemManifest.model_validate_json(manifest.model_dump_json())
    assert again == manifest
