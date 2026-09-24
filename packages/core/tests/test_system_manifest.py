"""
Unit tests for the ANNEX-FIELDS SystemManifest additions (Annex IV Sections
4, 6-9 provider attestations) and the multi-framework fields
(compliance_targets, framework_inputs).

Covers: the eight fields round-trip through JSON, and a legacy manifest JSON
written before these fields existed still validates, falling back to the
documented defaults (None / empty list). A manifest that leaves the
multi-framework fields unset serialises to the same bytes as before they
existed; set, they round-trip; FrameworkInputs rejects unknown keys and
empty strings.
"""

from __future__ import annotations

import json

import pytest
from opencomplai_core.models import FrameworkInputs, SystemManifest
from pydantic import ValidationError


def _manifest_kwargs(**overrides: object) -> dict:
    base: dict[str, object] = {
        "system_id": "sys-1",
        "intended_purpose": "credit scoring",
        "compliance_target": "EU_AI_ACT",
        "high_risk_presumption": True,
        "commit_ref": "abc123",
        "training_data_description": "internal loan applications 2018-2024",
        "model_architecture": "gradient boosted trees",
    }
    base.update(overrides)
    return base


def test_annex_iv_attestation_fields_round_trip_through_json():
    """The eight Annex IV Section 4/6-9 fields must survive a JSON round-trip
    unchanged, since they flow from `opencomplai init` to the doc-generator
    purely through the serialized manifest."""
    manifest = SystemManifest(
        **_manifest_kwargs(
            metrics_appropriateness_rationale="Recall matches the screening use case.",
            lifecycle_changes=["v1.1: recalibrated threshold"],
            change_log_reference="CHANGELOG.md#v1.1",
            harmonised_standards=["EN ISO/IEC 42001:2023"],
            alternative_solutions="Manual review fallback pending certification.",
            eu_declaration_of_conformity_ref="DoC-2026-001",
            post_market_monitoring_plan_ref="docs/pmm-plan.md",
            post_market_monitoring_summary="Quarterly drift review with sign-off.",
        )
    )

    round_tripped = SystemManifest.model_validate_json(manifest.model_dump_json())

    assert round_tripped.metrics_appropriateness_rationale == (
        "Recall matches the screening use case."
    )
    assert round_tripped.lifecycle_changes == ["v1.1: recalibrated threshold"]
    assert round_tripped.change_log_reference == "CHANGELOG.md#v1.1"
    assert round_tripped.harmonised_standards == ["EN ISO/IEC 42001:2023"]
    assert round_tripped.alternative_solutions == (
        "Manual review fallback pending certification."
    )
    assert round_tripped.eu_declaration_of_conformity_ref == "DoC-2026-001"
    assert round_tripped.post_market_monitoring_plan_ref == "docs/pmm-plan.md"
    assert round_tripped.post_market_monitoring_summary == (
        "Quarterly drift review with sign-off."
    )


def test_legacy_manifest_json_without_annex_iv_fields_still_validates():
    """A manifest JSON persisted before ANNEX-FIELDS existed (no Section 4/6-9
    keys at all) must still validate, defaulting the new fields to None/[]."""
    legacy_json = json.dumps(_manifest_kwargs())

    manifest = SystemManifest.model_validate_json(legacy_json)

    assert manifest.metrics_appropriateness_rationale is None
    assert manifest.lifecycle_changes == []
    assert manifest.change_log_reference is None
    assert manifest.harmonised_standards == []
    assert manifest.alternative_solutions is None
    assert manifest.eu_declaration_of_conformity_ref is None
    assert manifest.post_market_monitoring_plan_ref is None
    assert manifest.post_market_monitoring_summary is None


# Every key `opencomplai init` wrote before compliance_targets/framework_inputs
# existed, in the order it wrote them.
_LEGACY_MANIFEST = {
    "system_id": "sys-1",
    "intended_purpose": "credit scoring",
    "compliance_target": "EU_AI_ACT",
    "high_risk_presumption": True,
    "commit_ref": "abc123",
    "training_data_description": "internal loan applications 2018-2024",
    "model_architecture": "gradient boosted trees",
    "performance_metrics": {"auc": 0.91},
    "known_limitations": [],
    "human_oversight_measures": [],
    "monitoring_approach": None,
    "incident_response_procedure": None,
    "metrics_appropriateness_rationale": None,
    "lifecycle_changes": [],
    "change_log_reference": None,
    "harmonised_standards": [],
    "alternative_solutions": None,
    "eu_declaration_of_conformity_ref": None,
    "eu_declaration_of_conformity_sha256": None,
    "post_market_monitoring_plan_ref": None,
    "post_market_monitoring_summary": None,
    "operator_role": None,
    "checker_session": None,
}


def test_manifest_without_framework_fields_serialises_to_identical_bytes():
    legacy_json = json.dumps(_LEGACY_MANIFEST, indent=2)

    manifest = SystemManifest.model_validate_json(legacy_json)

    assert manifest.compliance_targets is None
    assert manifest.framework_inputs == {}
    assert manifest.model_dump_json(indent=2) == legacy_json
    assert json.dumps(manifest.model_dump(mode="json"), indent=2) == legacy_json
    assert list(manifest.model_dump()) == list(_LEGACY_MANIFEST)


def test_framework_fields_round_trip_through_json():
    manifest = SystemManifest(
        **_manifest_kwargs(
            compliance_targets=["EU_AI_ACT", "NIST_AI_RMF"],
            framework_inputs={
                "NIST_AI_RMF": {
                    "excluded": {"NIST_AI_RMF:MAP 5.2": "No external deployment."},
                    "attested": {
                        "NIST_AI_RMF:GOVERN 1.1": {
                            "statement": "Legal review of AI obligations done.",
                            "attested_by": "jane.doe@example.com",
                            "attested_at": "2026-09-01",
                        }
                    },
                }
            },
        )
    )

    dumped = manifest.model_dump(mode="json")
    assert dumped["compliance_targets"] == ["EU_AI_ACT", "NIST_AI_RMF"]
    assert dumped["framework_inputs"]["NIST_AI_RMF"]["excluded"] == {
        "NIST_AI_RMF:MAP 5.2": "No external deployment."
    }

    round_tripped = SystemManifest.model_validate_json(manifest.model_dump_json())

    assert round_tripped == manifest
    attestation = round_tripped.framework_inputs["NIST_AI_RMF"].attested[
        "NIST_AI_RMF:GOVERN 1.1"
    ]
    assert attestation.attested_by == "jane.doe@example.com"


def test_empty_compliance_targets_is_rejected():
    with pytest.raises(ValidationError):
        SystemManifest(**_manifest_kwargs(compliance_targets=[]))


@pytest.mark.parametrize(
    "inputs",
    [
        {"waived": {}},
        {
            "attested": {
                "FIXTURE:REQ-1": {
                    "statement": "s",
                    "attested_by": "a",
                    "attested_at": "2026-09-01",
                    "signature": "x",
                }
            }
        },
    ],
    ids=["unknown-framework-inputs-key", "unknown-attestation-key"],
)
def test_framework_inputs_rejects_extra_keys(inputs):
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        FrameworkInputs.model_validate(inputs)


@pytest.mark.parametrize(
    "inputs",
    [
        {"excluded": {"FIXTURE:REQ-1": ""}},
        {"excluded": {"": "not applicable"}},
        {
            "attested": {
                "": {
                    "statement": "s",
                    "attested_by": "a",
                    "attested_at": "2026-09-01",
                }
            }
        },
        {
            "attested": {
                "FIXTURE:REQ-1": {
                    "statement": "",
                    "attested_by": "a",
                    "attested_at": "2026-09-01",
                }
            }
        },
        {
            "attested": {
                "FIXTURE:REQ-1": {
                    "statement": "s",
                    "attested_by": "",
                    "attested_at": "2026-09-01",
                }
            }
        },
        {
            "attested": {
                "FIXTURE:REQ-1": {
                    "statement": "s",
                    "attested_by": "a",
                    "attested_at": "",
                }
            }
        },
    ],
    ids=[
        "empty-exclusion-reason",
        "empty-excluded-id",
        "empty-attested-id",
        "empty-statement",
        "empty-attested-by",
        "empty-attested-at",
    ],
)
def test_framework_inputs_rejects_empty_strings(inputs):
    with pytest.raises(ValidationError, match="at least 1 character"):
        FrameworkInputs.model_validate(inputs)


def test_manifest_rejects_invalid_framework_inputs():
    with pytest.raises(ValidationError):
        SystemManifest(
            **_manifest_kwargs(
                framework_inputs={"NIST_AI_RMF": {"excluded": {"x": ""}}}
            )
        )
