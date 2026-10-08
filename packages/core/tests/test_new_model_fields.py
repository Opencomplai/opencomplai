"""The 0.9.0 model fields are declared, but absent from output while unset.

Every new field is omitted from serialised output while it holds its default,
so legacy manifests, reports, goldens and signatures stay byte-identical.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from opencomplai_core.control_identity import fingerprint_manifest
from opencomplai_core.gap_report import build_gap_report
from opencomplai_core.models import (
    CheckerSessionRef,
    GapReport,
    RecordKeeping,
    ScanResult,
    ScanStatusArtifact,
    SystemManifest,
)
from opencomplai_core.signing import (
    _canonical_payload,
    canonical_json_bytes,
    generate_keypair,
    sign_artifact,
    verify_artifact,
)
from pydantic import ValidationError

_MANIFEST_KEYS_BEFORE = [
    "system_id",
    "intended_purpose",
    "compliance_target",
    "high_risk_presumption",
    "commit_ref",
    "training_data_description",
    "model_architecture",
    "performance_metrics",
    "known_limitations",
    "human_oversight_measures",
    "monitoring_approach",
    "incident_response_procedure",
    "metrics_appropriateness_rationale",
    "lifecycle_changes",
    "change_log_reference",
    "harmonised_standards",
    "alternative_solutions",
    "eu_declaration_of_conformity_ref",
    "eu_declaration_of_conformity_sha256",
    "post_market_monitoring_plan_ref",
    "post_market_monitoring_summary",
    "operator_role",
    "checker_session",
]
_ARTIFACT_KEYS_BEFORE = [
    "install_id",
    "system_id",
    "commit_ref",
    "result",
    "failed_controls",
    "evidence_hashes",
    "rationale_hash",
    "duration_ms",
    "pending_verifications_count",
    "signature",
    "eval_summary",
    "scan_summary",
    "gap_report",
    "nist_rmf_report",
    "controls",
]
_CHECKER_KEYS_BEFORE = [
    "checker_version",
    "session_id",
    "completed_at",
    "report_json_path",
    "verdict",
]
_GAP_KEYS_BEFORE = [
    "system_id",
    "commit_ref",
    "generated_at",
    "articles",
    "evidence_hashes",
    "principle_summary",
]

_NEW_MANIFEST = {"operator_roles", "organisation_size", "record_keeping"}
_NEW_ARTIFACT = {
    "rule_set_version",
    "cli_version",
    "schema_version",
    "manifest_sha256",
    "timestamp",
    "policy_bundle_version",
}
_NEW_CHECKER = {"obligation_ids", "rationale"}
_NEW_GAP = {"not_applicable"}


def _manifest(**overrides: object) -> SystemManifest:
    base: dict[str, object] = {
        "system_id": "sys-1",
        "intended_purpose": "credit scoring",
        "compliance_target": "EU_AI_ACT",
        "high_risk_presumption": True,
        "commit_ref": "abc123",
        "training_data_description": "internal loan applications 2018-2024",
        "model_architecture": "gradient boosted trees",
        "operator_role": "provider",
    }
    base.update(overrides)
    return SystemManifest(**base)  # type: ignore[arg-type]


def _artifact(**overrides: object) -> ScanStatusArtifact:
    base: dict[str, object] = {
        "install_id": "test-install-uuid",
        "system_id": "test-sys",
        "commit_ref": "abc123",
        "result": ScanResult.PASS,
        "evidence_hashes": ["sha256:aabbcc"],
        "rationale_hash": "sha256:ddeeff",
        "duration_ms": 1500,
    }
    base.update(overrides)
    return ScanStatusArtifact(**base)  # type: ignore[arg-type]


def _checker(**overrides: object) -> CheckerSessionRef:
    base: dict[str, object] = {
        "checker_version": "checker-2025-07-28",
        "session_id": "s-1",
        "completed_at": "2026-01-01T00:00:00Z",
    }
    base.update(overrides)
    return CheckerSessionRef(**base)  # type: ignore[arg-type]


def _gap(**overrides: object) -> GapReport:
    base: dict[str, object] = {
        "system_id": "sys-1",
        "commit_ref": "abc123",
        "generated_at": "2026-01-01T00:00:00Z",
    }
    base.update(overrides)
    return GapReport(**base)  # type: ignore[arg-type]


_DEFAULTS = [
    pytest.param(_manifest, _MANIFEST_KEYS_BEFORE, _NEW_MANIFEST, id="SystemManifest"),
    pytest.param(_checker, _CHECKER_KEYS_BEFORE, _NEW_CHECKER, id="CheckerSessionRef"),
    pytest.param(_gap, _GAP_KEYS_BEFORE, _NEW_GAP, id="GapReport"),
    pytest.param(
        _artifact, _ARTIFACT_KEYS_BEFORE, _NEW_ARTIFACT, id="ScanStatusArtifact"
    ),
]


@pytest.mark.parametrize(("build", "keys_before", "new"), _DEFAULTS)
def test_defaults_are_absent_from_every_serialisation(build, keys_before, new):
    model = build()
    python_dump = model.model_dump()
    json_dump = model.model_dump(mode="json")
    from_json = json.loads(model.model_dump_json())

    for dump in (python_dump, json_dump, from_json):
        assert not new & set(dump), f"default {sorted(new & set(dump))} was serialised"
    assert list(python_dump) == [k for k in keys_before if k in python_dump], (
        "existing key order changed"
    )
    # The model still declares every new field.
    assert new <= set(type(model).model_fields)


@pytest.mark.parametrize(
    ("model", "keys_before"),
    [(_manifest(), _MANIFEST_KEYS_BEFORE), (_artifact(), _ARTIFACT_KEYS_BEFORE)],
)
def test_default_key_set_equals_pre_change_key_set(model, keys_before):
    assert list(model.model_dump()) == keys_before


def test_populated_fields_round_trip():
    manifest = _manifest(
        operator_roles=["provider", "deployer"],
        organisation_size="micro",
        record_keeping=RecordKeeping(
            logging_enabled=True, log_retention_days=180, evidence_vault_enabled=True
        ),
    )
    restored = SystemManifest.model_validate_json(manifest.model_dump_json())
    assert restored == manifest
    assert restored.operator_roles == ["provider", "deployer"]
    assert restored.record_keeping is not None
    assert restored.record_keeping.log_retention_days == 180

    checker = _checker(obligation_ids=["OBL-1"], rationale=["because"])
    assert CheckerSessionRef.model_validate_json(checker.model_dump_json()) == checker

    gap = _gap(not_applicable={"Art. 50": "not a chatbot"})
    assert GapReport.model_validate_json(gap.model_dump_json()) == gap
    assert gap.model_dump()["not_applicable"] == {"Art. 50": "not a chatbot"}

    artifact = _artifact(
        rule_set_version="r1",
        cli_version="0.9.0",
        schema_version="2",
        manifest_sha256="a" * 64,
        timestamp="2026-01-01T00:00:00Z",
        policy_bundle_version="p1",
    )
    assert (
        ScanStatusArtifact.model_validate_json(artifact.model_dump_json()) == artifact
    )
    assert _NEW_ARTIFACT <= set(artifact.model_dump())


def test_record_keeping_is_closed_and_validated():
    with pytest.raises(ValidationError):
        RecordKeeping(log_retention_days=0)
    with pytest.raises(ValidationError):
        RecordKeeping(ledger_root_hash="x")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        _manifest(organisation_size="huge")


def test_legacy_manifest_and_checker_ref_json_load_and_reserialise_identically():
    legacy_checker = {
        "checker_version": "checker-2025-07-28",
        "session_id": "s-1",
        "completed_at": "2026-01-01T00:00:00Z",
        "report_json_path": "",
        "verdict": None,
    }
    legacy_manifest = dict.fromkeys(_MANIFEST_KEYS_BEFORE)
    legacy_manifest.update(
        system_id="sys-1",
        intended_purpose="credit scoring",
        compliance_target="EU_AI_ACT",
        high_risk_presumption=True,
        commit_ref="abc123",
        training_data_description="loans",
        model_architecture="gbt",
        performance_metrics={"auc": 0.91},
        known_limitations=[],
        human_oversight_measures=[],
        lifecycle_changes=[],
        harmonised_standards=[],
        checker_session=legacy_checker,
    )
    text = json.dumps(legacy_manifest, indent=2)
    manifest = SystemManifest.model_validate_json(text)
    assert manifest.operator_roles == []
    assert manifest.model_dump_json(indent=2) == text

    ref_text = json.dumps(legacy_checker, indent=2)
    ref = CheckerSessionRef.model_validate_json(ref_text)
    assert ref.model_dump_json(indent=2) == ref_text


# Computed on the function before `operator_roles` was watched.
_PINNED_FINGERPRINT = "d2571a2508d43b73bbf9571ebb4a09398b615687749dbe8088cbca420b632f93"


def test_fingerprint_unchanged_when_operator_roles_empty():
    manifest = _manifest()
    assert fingerprint_manifest(manifest) == _PINNED_FINGERPRINT
    # A raw dict (e.g. a manifest loaded without the serializer) with an explicit
    # empty list must hash the same as one without the key.
    raw = {**manifest.model_dump(), "operator_roles": []}
    assert fingerprint_manifest(raw) == _PINNED_FINGERPRINT


def test_fingerprint_changes_when_operator_roles_set():
    with_roles = _manifest(operator_roles=["provider", "deployer"])
    assert fingerprint_manifest(with_roles) != _PINNED_FINGERPRINT
    other = _manifest(operator_roles=["provider"])
    assert fingerprint_manifest(other) != fingerprint_manifest(with_roles)


def test_signature_covers_provenance_fields_only_when_set(tmp_path: Path):
    key_dir = tmp_path / ".opencomplai"
    generate_keypair(key_dir)

    plain = _artifact()
    old_bytes = canonical_json_bytes(
        {k: v for k, v in plain.model_dump(mode="json").items() if k != "signature"}
    )
    assert _canonical_payload(plain) == old_bytes
    assert b"cli_version" not in old_bytes

    stamped = _artifact(cli_version="0.9.0")
    assert _canonical_payload(stamped) != old_bytes
    assert b'"cli_version": "0.9.0"' in _canonical_payload(stamped)

    sig = sign_artifact(stamped, key_dir / "signing.key")
    signed = stamped.model_copy(update={"signature": sig})
    assert verify_artifact(signed, key_dir / "signing.pub") is True
    tampered = signed.model_copy(update={"cli_version": "0.9.1"})
    assert verify_artifact(tampered, key_dir / "signing.pub") is False


def test_build_gap_report_ignores_manifest_and_session():
    # No recorded obligation ids means unknown applicability (SU-14a): no change.
    manifest = _manifest(
        operator_roles=["deployer"], checker_session=_checker(obligation_ids=[])
    )
    plain = build_gap_report("sys-9", "HEAD")
    with_inputs = build_gap_report(
        "sys-9",
        "HEAD",
        manifest=manifest,
        checker_session=manifest.checker_session,
    )
    skip = {"generated_at"}
    assert with_inputs.model_dump(exclude=skip) == plain.model_dump(exclude=skip)
    assert with_inputs.system_id == "sys-9"
    assert "not_applicable" not in with_inputs.model_dump()
