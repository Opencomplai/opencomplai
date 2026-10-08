"""Tests for the Annex IV dossier generator (REQ-DOC-001)."""

import inspect
import json

import pytest
from opencomplai_core.dossier import (
    PROVIDER_SUPPLIED_PLACEHOLDER,
    validate_dossier_schema,
)
from opencomplai_core.dossier_generator import generate_dossier
from opencomplai_core.engine import assess
from opencomplai_core.models import AssessmentInput, ModelMetadata, SystemManifest


@pytest.fixture(autouse=True)
def _clean_signing_env(monkeypatch):
    for name in (
        "DOSSIER_SIGNING_KEY_PATH",
        "LOCAL_SIGNING_KEY_PATH",
        "LOG_RETENTION_DAYS",
        "SIGNING_KEY_PRIVATE",
    ):
        monkeypatch.delenv(name, raising=False)


def _ed25519_key(tmp_path, name="ed25519"):
    """Write an Ed25519 keypair under tmp_path; return (private, public) paths."""
    from opencomplai_core.signing import generate_keypair

    key_dir = tmp_path / name
    generate_keypair(key_dir)
    return key_dir / "signing.key", key_dir / "signing.pub"


def _make_manifest(system_id: str = "test", purpose: str = "chatbot") -> SystemManifest:
    return SystemManifest(
        system_id=system_id,
        intended_purpose=purpose,
        compliance_target="EU_AI_ACT",
        high_risk_presumption=False,
        commit_ref="abc123",
    )


def _make_risk_result(purpose: str = "chatbot"):
    return assess(
        AssessmentInput(
            model=ModelMetadata(
                name="test",
                version="1.0.0",
                modality="text",
                use_case=purpose,
                deployment_context="production",
            )
        )
    )


def test_generate_dossier_produces_valid_schema():
    """REQ-DOC-001: dossier schema validator must pass for all release candidates."""
    dossier = generate_dossier(_make_manifest(), _make_risk_result())
    assert validate_dossier_schema(dossier) is True


def test_generate_dossier_has_bundle_checksum():
    dossier = generate_dossier(_make_manifest(), _make_risk_result())
    assert dossier.bundle_checksum is not None
    assert dossier.bundle_checksum.startswith("sha256:")


def test_generate_dossier_unsigned_by_default():
    """OSS default: no signing key set, signature must be None."""
    dossier = generate_dossier(_make_manifest(), _make_risk_result())
    assert dossier.signature is None


def test_generate_dossier_for_high_risk_system():
    dossier = generate_dossier(
        _make_manifest(purpose="employment screening"),
        _make_risk_result("employment screening"),
    )
    assert dossier.section5.risk_level == "high"
    assert dossier.section5.rules_failed > 0
    # Validation now fails: Annex IV Sections 6-9 are provider attestations
    # that this engine cannot derive, and a high-risk dossier without them is
    # not a complete Annex IV file. See
    # test_high_risk_dossier_passes_once_sections_6_to_9_are_attested.
    assert validate_dossier_schema(dossier) is False


def test_bundle_checksum_is_deterministic():
    """Same inputs must produce the same bundle_checksum."""
    manifest = _make_manifest()
    risk = _make_risk_result()
    d1 = generate_dossier(manifest, risk)
    d2 = generate_dossier(manifest, risk)
    assert d1.bundle_checksum == d2.bundle_checksum


def test_all_annex_iv_sections_populated():
    """All NINE Annex IV points must be present, plus Art. 12 record-keeping."""
    dossier = generate_dossier(_make_manifest(), _make_risk_result())
    assert dossier.section1.system_name
    assert dossier.section2.training_data_description
    assert dossier.section3.monitoring_approach
    # Section 4 is the appropriateness of the performance metrics (Annex IV
    # pt.4), not logging — logging is Art. 12 and lives in record_keeping.
    assert dossier.section4.appropriateness_rationale
    assert dossier.section5.rationale_hash.startswith("sha256:")
    assert dossier.section6 is not None
    assert dossier.section7 is not None
    assert dossier.section8 is not None
    assert dossier.section9 is not None
    assert dossier.record_keeping is not None
    # Nothing declared in the manifest, so nothing is asserted.
    assert dossier.record_keeping.logging_enabled is False
    assert dossier.record_keeping.evidence_vault_enabled is False


def test_sections_6_to_9_are_present_and_honestly_labelled():
    """Unattested sections must be explicit placeholders, never silently absent."""
    dossier = generate_dossier(_make_manifest(), _make_risk_result())
    for section in (
        dossier.section6,
        dossier.section7,
        dossier.section8,
        dossier.section9,
    ):
        assert section.provider_supplied is False
        assert "provider attestation" in section.note


def test_high_risk_dossier_missing_sections_6_to_9_fails_validation():
    """A 5-of-9 dossier must not pass the release gate as complete Annex IV."""
    dossier = generate_dossier(
        _make_manifest(purpose="employment screening"),
        _make_risk_result("employment screening"),
    )
    assert dossier.section1.risk_class == "high"
    assert dossier.annex_iv_complete is False
    assert validate_dossier_schema(dossier) is False


def test_high_risk_dossier_passes_once_sections_6_to_9_are_attested():
    manifest = _make_manifest(purpose="employment screening")
    dossier = generate_dossier(manifest, _make_risk_result("employment screening"))

    dossier.section3.provider_supplied = True
    dossier.section4.provider_supplied = True
    for section in (
        dossier.section6,
        dossier.section7,
        dossier.section8,
        dossier.section9,
    ):
        section.provider_supplied = True
    dossier.annex_iv_complete = True

    assert validate_dossier_schema(dossier) is True


def test_non_high_risk_dossier_is_not_gated_on_provider_attestations():
    """Annex IV pt.6-9 attestation is a high-risk obligation."""
    dossier = generate_dossier(_make_manifest(), _make_risk_result())
    assert dossier.section1.risk_class != "high"
    assert dossier.annex_iv_complete is True
    assert validate_dossier_schema(dossier) is True


def test_section2_overrides_from_manifest():
    """Gap #3: manifest section2 fields must flow into the dossier."""
    manifest = SystemManifest(
        system_id="test",
        intended_purpose="chatbot",
        compliance_target="EU_AI_ACT",
        high_risk_presumption=False,
        commit_ref="abc123",
        training_data_description="500k anonymised support tickets, EN/FR/DE.",
        model_architecture="Transformer encoder-decoder, 7B params, fine-tuned.",
        performance_metrics={"exact_match": 0.82, "rouge_l": 0.71},
        known_limitations=["Degrades on legal jargon", "No multimodal input"],
    )
    dossier = generate_dossier(manifest, _make_risk_result())
    assert dossier.section2.training_data_description.startswith("500k")
    assert "Transformer" in dossier.section2.model_architecture
    assert dossier.section2.performance_metrics == {
        "exact_match": 0.82,
        "rouge_l": 0.71,
    }
    assert "Degrades on legal jargon" in dossier.section2.known_limitations


def test_section2_stubbed_when_manifest_silent():
    """If the customer does not provide Section 2 inputs, fall back to the stub."""
    dossier = generate_dossier(_make_manifest(), _make_risk_result())
    assert (
        dossier.section2.training_data_description == "Not specified in this release."
    )
    assert dossier.section2.model_architecture == "Not specified in this release."
    assert dossier.section2.performance_metrics == {}
    assert dossier.section2.known_limitations == []


def test_section3_overrides_from_manifest():
    """Section 3 (oversight, monitoring, incident response) must flow from manifest."""
    manifest = SystemManifest(
        system_id="test",
        intended_purpose="chatbot",
        compliance_target="EU_AI_ACT",
        high_risk_presumption=True,
        commit_ref="abc123",
        human_oversight_measures=[
            "Two-person review on every override",
            "Daily bias dashboard review",
        ],
        monitoring_approach="Datadog + custom drift checks every 6h",
        incident_response_procedure="Runbook at runbooks/ai-incident.md",
    )
    dossier = generate_dossier(manifest, _make_risk_result())
    assert (
        "Two-person review on every override"
        in dossier.section3.human_oversight_measures
    )
    assert (
        dossier.section3.monitoring_approach == "Datadog + custom drift checks every 6h"
    )
    assert (
        dossier.section3.incident_response_procedure
        == "Runbook at runbooks/ai-incident.md"
    )
    assert dossier.section3.provider_supplied is True


def test_section3_stubbed_when_manifest_silent():
    """Falls back to the placeholder when nothing is provided — never a
    fabricated attestation."""
    dossier = generate_dossier(_make_manifest(), _make_risk_result())
    assert dossier.section3.human_oversight_measures == []
    assert dossier.section3.monitoring_approach == PROVIDER_SUPPLIED_PLACEHOLDER
    assert dossier.section3.incident_response_procedure == PROVIDER_SUPPLIED_PLACEHOLDER
    assert dossier.section3.provider_supplied is False


def test_ledger_root_hash_embedded_when_supplied():
    """Gap #4: dossier must anchor to the supplied ledger root."""
    root = "sha256:" + ("a" * 64)
    dossier = generate_dossier(
        _make_manifest(), _make_risk_result(), ledger_root_hash=root
    )
    assert dossier.record_keeping.ledger_root_hash == root


def test_signature_status_unsigned_by_default():
    """Gap #5: OSS default must self-describe as unsigned."""
    dossier = generate_dossier(_make_manifest(), _make_risk_result())
    assert dossier.signature is None
    assert dossier.signature_status == "unsigned"


def test_local_signing_key_path_no_longer_signs(tmp_path, monkeypatch):
    """LOCAL_SIGNING_KEY_PATH alone leaves the dossier unsigned, with a warning."""
    key_path = tmp_path / "signing.key"
    key_path.write_bytes(b"opencomplai-test-signing-key")
    monkeypatch.setenv("LOCAL_SIGNING_KEY_PATH", str(key_path))
    with pytest.warns(UserWarning, match="LOCAL_SIGNING_KEY_PATH"):
        dossier = generate_dossier(_make_manifest(), _make_risk_result())
    assert dossier.signature is None
    assert dossier.signature_status == "unsigned"


def test_signing_key_private_alone_signs(tmp_path, monkeypatch):
    """SIGNING_KEY_PRIVATE alone (no DOSSIER_SIGNING_KEY_PATH) signs."""
    import base64

    from opencomplai_core.dossier_generator import BUNDLE_EXCLUDE
    from opencomplai_core.signing import SigningDomain, verify_bundle_bytes

    priv_path, pub_path = _ed25519_key(tmp_path)
    monkeypatch.setenv(
        "SIGNING_KEY_PRIVATE", base64.b64encode(priv_path.read_bytes()).decode()
    )
    dossier = generate_dossier(_make_manifest(), _make_risk_result())
    assert dossier.signature is not None
    assert dossier.signature_status == "ed25519"
    bundle_json = dossier.model_dump_json(exclude=BUNDLE_EXCLUDE)
    assert verify_bundle_bytes(
        bundle_json.encode("utf-8"),
        dossier.signature,
        pub_path,
        SigningDomain.DOSSIER_BUNDLE,
    )


def test_no_hmac_code_remains():
    from opencomplai_core import dossier_generator

    source = inspect.getsource(dossier_generator).lower()
    assert "hmac" not in source
    assert not hasattr(dossier_generator, "_sign_bundle")


def test_failed_ed25519_signing_warns_and_stays_unsigned(tmp_path, monkeypatch):
    bad_key = tmp_path / "garbage.key"
    bad_key.write_bytes(b"not a pem key\n")
    monkeypatch.setenv("DOSSIER_SIGNING_KEY_PATH", str(bad_key))
    with pytest.warns(UserWarning, match="signing failed") as caught:
        dossier = generate_dossier(_make_manifest(), _make_risk_result())
    assert dossier.signature is None
    assert dossier.signature_status == "unsigned"
    assert "not a pem key" not in " ".join(str(w.message) for w in caught)


def test_signature_status_ed25519_when_pro_key_configured(tmp_path, monkeypatch):
    """Ed25519 path signs and is verifiable with only the public key."""
    from opencomplai_core.dossier_generator import BUNDLE_EXCLUDE
    from opencomplai_core.signing import SigningDomain, verify_bundle_bytes

    priv_path, pub_path = _ed25519_key(tmp_path)
    monkeypatch.setenv("DOSSIER_SIGNING_KEY_PATH", str(priv_path))
    dossier = generate_dossier(_make_manifest(), _make_risk_result())
    assert dossier.signature is not None
    assert dossier.signature_status == "ed25519"

    bundle_json = dossier.model_dump_json(exclude=BUNDLE_EXCLUDE)
    assert verify_bundle_bytes(
        bundle_json.encode("utf-8"),
        dossier.signature,
        pub_path,
        SigningDomain.DOSSIER_BUNDLE,
    )
    # The same signature must not pass as any other kind of attestation.
    assert not verify_bundle_bytes(
        bundle_json.encode("utf-8"), dossier.signature, pub_path, SigningDomain.BADGE
    )


def test_signed_dossier_uses_bundle_exclude_constant(tmp_path, monkeypatch):
    import hashlib

    from opencomplai_core.dossier_generator import BUNDLE_EXCLUDE

    assert BUNDLE_EXCLUDE == {
        "dossier_id",
        "generated_at",
        "bundle_checksum",
        "signature",
        "signature_status",
        "section2_complete",
    }
    priv_path, _ = _ed25519_key(tmp_path)
    monkeypatch.setenv("DOSSIER_SIGNING_KEY_PATH", str(priv_path))
    dossier = generate_dossier(_make_manifest(), _make_risk_result())
    digest = hashlib.sha256(
        dossier.model_dump_json(exclude=BUNDLE_EXCLUDE).encode()
    ).hexdigest()
    assert dossier.bundle_checksum == f"sha256:{digest}"


def test_ed25519_still_signs_when_local_signing_key_path_also_set(
    tmp_path, monkeypatch
):
    ed_path, _ = _ed25519_key(tmp_path)
    local = tmp_path / "local.key"
    local.write_bytes(b"some-secret")
    monkeypatch.setenv("LOCAL_SIGNING_KEY_PATH", str(local))
    monkeypatch.setenv("DOSSIER_SIGNING_KEY_PATH", str(ed_path))
    dossier = generate_dossier(_make_manifest(), _make_risk_result())
    assert dossier.signature_status == "ed25519"


def test_signature_status_does_not_change_bundle_checksum(tmp_path, monkeypatch):
    """signature_status is envelope metadata - it must not feed the checksum."""
    unsigned = generate_dossier(_make_manifest(), _make_risk_result())

    priv_path, _ = _ed25519_key(tmp_path)
    monkeypatch.setenv("DOSSIER_SIGNING_KEY_PATH", str(priv_path))
    signed = generate_dossier(_make_manifest(), _make_risk_result())

    assert unsigned.bundle_checksum == signed.bundle_checksum
    assert unsigned.signature_status != signed.signature_status


# ---------------------------------------------------------------------------
# Art. 12 record keeping: declared by the provider, never assumed
# ---------------------------------------------------------------------------


def test_manifest_without_record_keeping_declares_nothing():
    dossier = generate_dossier(_make_manifest(), _make_risk_result())
    rk = dossier.record_keeping
    assert rk.logging_enabled is False
    assert rk.evidence_vault_enabled is False
    assert rk.provider_supplied is False
    serialised = json.loads(dossier.model_dump_json())["record_keeping"]
    assert "log_retention_days" not in serialised


def test_declared_record_keeping_is_copied_and_env_retention_ignored(monkeypatch):
    monkeypatch.setenv("LOG_RETENTION_DAYS", "9999")
    manifest = _make_manifest().model_copy(
        update={
            "record_keeping": {
                "logging_enabled": True,
                "log_retention_days": 180,
                "evidence_vault_enabled": False,
            }
        }
    )
    rk = generate_dossier(manifest, _make_risk_result()).record_keeping
    assert rk.provider_supplied is True
    assert rk.logging_enabled is True
    assert rk.log_retention_days == 180
    assert rk.evidence_vault_enabled is False

    # Declared block without retention: the env value must never fill the gap.
    manifest = _make_manifest().model_copy(
        update={"record_keeping": {"logging_enabled": True}}
    )
    dossier = generate_dossier(manifest, _make_risk_result())
    assert dossier.record_keeping.log_retention_days is None
    assert "9999" not in dossier.model_dump_json()


def test_ledger_root_hash_still_recorded_without_declaration():
    root = "sha256:" + ("b" * 64)
    rk = generate_dossier(
        _make_manifest(), _make_risk_result(), ledger_root_hash=root
    ).record_keeping
    assert rk.ledger_root_hash == root
    assert rk.provider_supplied is False


# ---------------------------------------------------------------------------
# Item 5 — HIGH-risk safety rail: section2_complete flag
# ---------------------------------------------------------------------------


def test_high_risk_with_stub_section2_marks_incomplete():
    """A HIGH-risk dossier with stub Section 2 must self-flag as incomplete."""
    dossier = generate_dossier(
        _make_manifest(purpose="employment screening"),  # triggers HIGH risk
        _make_risk_result("employment screening"),
    )
    assert dossier.section5.risk_level == "high"
    assert dossier.section2_complete is False


def test_high_risk_with_populated_section2_marks_complete():
    """A HIGH-risk dossier with real Section 2 content must report complete."""
    manifest = SystemManifest(
        system_id="test",
        intended_purpose="employment screening",
        compliance_target="EU_AI_ACT",
        high_risk_presumption=True,
        commit_ref="abc123",
        training_data_description="real training data description here",
        model_architecture="real model architecture description here",
    )
    dossier = generate_dossier(manifest, _make_risk_result("employment screening"))
    assert dossier.section5.risk_level == "high"
    assert dossier.section2_complete is True


def test_minimal_risk_does_not_require_section2():
    """At MINIMAL risk, stub Section 2 is acceptable — section2_complete must be True."""
    dossier = generate_dossier(_make_manifest(purpose="chatbot"), _make_risk_result())
    # MINIMAL risk: stubs are fine, section2_complete must not be False.
    assert dossier.section2_complete is True


def test_section2_complete_excluded_from_bundle_checksum():
    """section2_complete is a derived metadata field — it must not feed the checksum."""
    # A HIGH-risk dossier (section2_complete=False) and a manually patched copy
    # with section2_complete=True must have the same bundle_checksum.
    manifest = _make_manifest(purpose="employment screening")
    risk = _make_risk_result("employment screening")
    dossier = generate_dossier(manifest, risk)
    assert dossier.section2_complete is False  # pre-condition

    # Patch the flag and recompute checksum manually — should be identical.
    patched = dossier.model_copy(update={"section2_complete": True})
    bundle_json_original = dossier.model_dump_json(
        exclude={
            "dossier_id",
            "generated_at",
            "bundle_checksum",
            "signature",
            "signature_status",
            "section2_complete",
        }
    )
    bundle_json_patched = patched.model_dump_json(
        exclude={
            "dossier_id",
            "generated_at",
            "bundle_checksum",
            "signature",
            "signature_status",
            "section2_complete",
        }
    )
    assert bundle_json_original == bundle_json_patched
    assert dossier.bundle_checksum == patched.bundle_checksum


# ---------------------------------------------------------------------------
# ANNEX-FIELDS — SystemManifest Annex IV attestation fields (Sections 3, 4, 6-9)
# ---------------------------------------------------------------------------


def _make_high_risk_manifest_with_annex_iv_attestations() -> SystemManifest:
    return SystemManifest(
        system_id="test",
        intended_purpose="employment screening",
        compliance_target="EU_AI_ACT",
        high_risk_presumption=True,
        commit_ref="abc123",
        training_data_description="real training data description here",
        model_architecture="real model architecture description here",
        human_oversight_measures=["Two-person review on every override"],
        monitoring_approach="Datadog + custom drift checks every 6h",
        incident_response_procedure="Runbook at runbooks/ai-incident.md",
        metrics_appropriateness_rationale=(
            "Precision/recall are appropriate for a binary screening decision."
        ),
        lifecycle_changes=[
            "2026-03-01: Recalibrated decision threshold after Q1 drift review"
        ],
        change_log_reference="CHANGELOG.md#v1.1",
        harmonised_standards=[
            "EN ISO/IEC 42001:2023 — AI management system controls applied organisation-wide"
        ],
        alternative_solutions=None,
        eu_declaration_of_conformity_ref="DoC-2026-001",
        post_market_monitoring_plan_ref="docs/pmm-plan.md",
        post_market_monitoring_summary=(
            "2026-01-15: Quarterly drift review completed with sign-off from the AI safety lead."
        ),
    )


def test_annex_iv_attestations_supplied_marks_sections_complete_for_high_risk():
    """With all Section 3/4/6-9 fields set, every attested section — and the
    dossier as a whole — must report complete for a HIGH-risk system."""
    manifest = _make_high_risk_manifest_with_annex_iv_attestations()
    dossier = generate_dossier(manifest, _make_risk_result("employment screening"))

    assert dossier.section1.risk_class == "high"
    assert dossier.section3.provider_supplied is True
    assert dossier.section4.provider_supplied is True
    for section in (
        dossier.section6,
        dossier.section7,
        dossier.section8,
        dossier.section9,
    ):
        assert section.provider_supplied is True
    assert dossier.annex_iv_complete is True
    assert validate_dossier_schema(dossier) is True


def test_section8_declaration_sha256_round_trips_with_reference():
    """A manifest carrying both the DoC reference and its evidence-vault
    upload hash must surface both, unchanged, on Section 8 (D-6)."""
    manifest = _make_manifest().model_copy(
        update={
            "eu_declaration_of_conformity_ref": "DoC-2026-001",
            "eu_declaration_of_conformity_sha256": "a" * 64,
        }
    )
    dossier = generate_dossier(manifest, _make_risk_result())

    assert dossier.section8.declaration_reference == "DoC-2026-001"
    assert dossier.section8.declaration_sha256 == "a" * 64


def test_section8_declaration_sha256_absent_without_reference():
    """A hash with nothing to hash-check against is meaningless: it must not
    surface unless a declaration_reference is also present."""
    manifest = _make_manifest().model_copy(
        update={"eu_declaration_of_conformity_sha256": "a" * 64}
    )
    dossier = generate_dossier(manifest, _make_risk_result())

    assert dossier.section8.declaration_reference is None
    assert dossier.section8.declaration_sha256 is None


def test_annex_iv_attestations_absent_keeps_high_risk_dossier_incomplete():
    """Regression on the c92ea74 gate: without the attestation fields, a
    HIGH-risk dossier must still be flagged incomplete, not silently pass."""
    manifest = _make_manifest(purpose="employment screening")
    dossier = generate_dossier(manifest, _make_risk_result("employment screening"))

    assert dossier.section1.risk_class == "high"
    assert dossier.section3.provider_supplied is False
    assert dossier.section4.provider_supplied is False
    for section in (
        dossier.section6,
        dossier.section7,
        dossier.section8,
        dossier.section9,
    ):
        assert section.provider_supplied is False
    assert dossier.annex_iv_complete is False
    assert validate_dossier_schema(dossier) is False


def test_annex_iv_high_risk_gate_rejects_section3_unset_even_with_4_and_6_9_attested():
    """Sections 4 and 6-9 fully attested but Section 3 untouched must still
    fail the HIGH-risk gate — Section 3 is now part of annex_iv_complete."""
    manifest = _make_high_risk_manifest_with_annex_iv_attestations()
    manifest = manifest.model_copy(
        update={
            "human_oversight_measures": [],
            "monitoring_approach": None,
            "incident_response_procedure": None,
        }
    )
    dossier = generate_dossier(manifest, _make_risk_result("employment screening"))

    assert dossier.section1.risk_class == "high"
    assert dossier.section3.provider_supplied is False
    assert dossier.section4.provider_supplied is True
    for section in (
        dossier.section6,
        dossier.section7,
        dossier.section8,
        dossier.section9,
    ):
        assert section.provider_supplied is True
    assert dossier.annex_iv_complete is False
    assert validate_dossier_schema(dossier) is False


def test_annex_iv_high_risk_gate_rejects_section3_partially_set():
    """Only monitoring_approach supplied — oversight measures and incident
    response still missing — must not count as provider-supplied."""
    manifest = _make_high_risk_manifest_with_annex_iv_attestations()
    manifest = manifest.model_copy(
        update={
            "human_oversight_measures": [],
            "incident_response_procedure": None,
        }
    )
    dossier = generate_dossier(manifest, _make_risk_result("employment screening"))

    assert (
        dossier.section3.monitoring_approach == "Datadog + custom drift checks every 6h"
    )
    assert dossier.section3.provider_supplied is False
    assert dossier.annex_iv_complete is False
    assert validate_dossier_schema(dossier) is False


def test_high_risk_presumption_gates_completeness_despite_non_matching_purpose():
    """FINDING 48.6: a declared high_risk_presumption must gate Section 2 /
    Annex IV completeness the same as a genuine 'high' classification, even
    when intended_purpose text doesn't keyword-match any Annex III rule."""
    manifest = SystemManifest(
        system_id="test",
        intended_purpose="chatbot",
        compliance_target="EU_AI_ACT",
        high_risk_presumption=True,
        commit_ref="abc123",
    )
    risk_result = _make_risk_result("chatbot")
    assert risk_result.risk_level.value != "high"  # purpose text doesn't match

    dossier = generate_dossier(manifest, risk_result)

    # The presumption must not fabricate the assessed classification...
    assert dossier.section1.risk_class != "high"
    # ...but it must still gate completeness as if the system were high-risk.
    assert dossier.section2_complete is False
    assert dossier.annex_iv_complete is False
    assert validate_dossier_schema(dossier, presumed_high=True) is False


def test_high_risk_presumption_with_full_attestations_passes_gate():
    """The same presumed-high, non-matching-purpose system passes once all
    Section 2 and Annex IV attestations are actually supplied."""
    manifest = _make_high_risk_manifest_with_annex_iv_attestations().model_copy(
        update={"intended_purpose": "chatbot"}
    )
    risk_result = _make_risk_result("chatbot")
    assert risk_result.risk_level.value != "high"

    dossier = generate_dossier(manifest, risk_result)
    assert dossier.section2_complete is True
    assert dossier.annex_iv_complete is True
    assert validate_dossier_schema(dossier, presumed_high=True) is True


def test_genuine_high_classification_gates_even_without_presumption():
    """The presumed_high flag must not become the only path to strict
    gating — a genuinely 'high' classification (no presumption declared)
    must still require full attestation."""
    manifest = _make_manifest(purpose="employment screening")
    assert manifest.high_risk_presumption is False
    dossier = generate_dossier(manifest, _make_risk_result("employment screening"))

    assert dossier.section1.risk_class == "high"
    assert dossier.annex_iv_complete is False
    assert validate_dossier_schema(dossier, presumed_high=False) is False


def test_annex_iv_attestations_absent_does_not_affect_minimal_risk():
    """MINIMAL-risk dossiers were never gated on Sections 4/6-9 — behaviour
    must be unchanged now that the manifest can carry those fields."""
    dossier = generate_dossier(_make_manifest(purpose="chatbot"), _make_risk_result())

    assert dossier.section1.risk_class != "high"
    assert dossier.annex_iv_complete is True
    assert validate_dossier_schema(dossier) is True


# ---------------------------------------------------------------------------
# D-7 — `provider_supplied` honesty: a single arbitrary string must not be
# enough to flip Section 4/6/7/9's provider_supplied to True.
# ---------------------------------------------------------------------------


def test_section4_bare_string_rationale_does_not_flip_provider_supplied():
    """A too-short, non-stub string in metrics_appropriateness_rationale
    must not count as a real justification."""
    manifest = _make_manifest().model_copy(
        update={"metrics_appropriateness_rationale": "x"}
    )
    dossier = generate_dossier(manifest, _make_risk_result())
    assert dossier.section4.provider_supplied is False


def test_section6_bare_string_change_without_ref_does_not_flip_provider_supplied():
    """A bare arbitrary change entry, with no change-log reference either,
    must not count as a lifecycle-change attestation."""
    manifest = _make_manifest().model_copy(update={"lifecycle_changes": ["x"]})
    dossier = generate_dossier(manifest, _make_risk_result())
    assert dossier.section6.provider_supplied is False


def test_section6_dated_entry_without_ref_flips_provider_supplied_true():
    """A properly dated change entry is sufficient on its own, with no
    change-log reference needed."""
    manifest = _make_manifest().model_copy(
        update={"lifecycle_changes": ["2026-02-01: Rolled back a risky feature flag"]}
    )
    dossier = generate_dossier(manifest, _make_risk_result())
    assert dossier.section6.provider_supplied is True


def test_section7_bare_string_standard_does_not_flip_provider_supplied():
    """Accept criterion: harmonised_standards: ["x"] — a bare arbitrary
    string matching no catalogue id and no documented pattern — must leave
    provider_supplied False."""
    manifest = _make_manifest().model_copy(update={"harmonised_standards": ["x"]})
    dossier = generate_dossier(manifest, _make_risk_result())
    assert dossier.section7.provider_supplied is False


def test_section7_documented_pattern_flips_provider_supplied_true():
    """Accept criterion: an entry matching the documented free-text pattern
    "<standard id/name> — <one-line reason>" must flip provider_supplied
    True, with no catalogue involved (CP-4 hasn't landed yet)."""
    manifest = _make_manifest().model_copy(
        update={
            "harmonised_standards": [
                "EN ISO/IEC 42001:2023 — AI management system controls applied"
            ]
        }
    )
    dossier = generate_dossier(manifest, _make_risk_result())
    assert dossier.section7.provider_supplied is True


def test_section9_bare_string_summary_without_ref_does_not_flip_provider_supplied():
    """A bare arbitrary plan_summary, with no monitoring-plan reference
    either, must not count as a post-market-monitoring attestation."""
    manifest = _make_manifest().model_copy(
        update={"post_market_monitoring_summary": "x"}
    )
    dossier = generate_dossier(manifest, _make_risk_result())
    assert dossier.section9.provider_supplied is False


# ---------------------------------------------------------------------------
# CP-4 — harmonised-standards catalogue match warning (alongside CP-2's D-7
# provider_supplied checks above, which these tests must not disturb).
# ---------------------------------------------------------------------------


def test_section7_catalogue_id_match_is_silent(recwarn):
    """A harmonised_standards entry matching a catalogue id emits no
    warning."""
    manifest = _make_manifest().model_copy(
        update={"harmonised_standards": ["EN-18286"]}
    )
    generate_dossier(manifest, _make_risk_result())
    assert len(recwarn) == 0


def test_section7_unmatched_entry_emits_warning():
    """A harmonised_standards entry that matches no catalogue id emits a
    warning — not a hard fail; generation still succeeds and
    provider_supplied is computed exactly as before (CP-2 untouched)."""
    manifest = _make_manifest().model_copy(update={"harmonised_standards": ["x"]})
    with pytest.warns(UserWarning, match="does not match a known"):
        dossier = generate_dossier(manifest, _make_risk_result())
    # CP-2's structural check is unaffected by the new warning.
    assert dossier.section7.provider_supplied is False


def test_section7_documented_pattern_entry_still_warns_if_not_a_catalogue_id():
    """The documented free-text pattern satisfies CP-2's provider_supplied
    honesty check, but is still a separate, unmatched catalogue id and so
    still warns — only a literal catalogue id match is silent."""
    manifest = _make_manifest().model_copy(
        update={
            "harmonised_standards": [
                "EN ISO/IEC 42001:2023 — AI management system controls applied"
            ]
        }
    )
    with pytest.warns(UserWarning, match="does not match a known"):
        dossier = generate_dossier(manifest, _make_risk_result())
    assert dossier.section7.provider_supplied is True


def test_section7_alternative_solutions_free_text_never_warns(recwarn):
    """The separate alternative_solutions field is never checked against the
    catalogue — free-text alternative solutions stay legitimate."""
    manifest = _make_manifest().model_copy(
        update={
            "harmonised_standards": [],
            "alternative_solutions": "Bespoke internal control framework applied",
        }
    )
    generate_dossier(manifest, _make_risk_result())
    assert len(recwarn) == 0


# --- structured human oversight in Annex IV section 3 (SU-20a2) ---

_OVERSIGHT_BLOCK = {
    "roles": [
        {
            "role": "Duty officer",
            "authority": "May suspend the system",
            "can_intervene": True,
            "conditions": ["Drift alarm fires"],
            "training_ref": "training/oversight.md",
        }
    ],
    "escalation": "Duty officer, then CTO",
    "evidence_refs": ["docs/oversight.md"],
}
_SECTION3_OLD_KEYS = {
    "human_oversight_measures",
    "monitoring_approach",
    "incident_response_procedure",
    "provider_supplied",
}


def _oversight_manifest(**extra) -> SystemManifest:
    return SystemManifest(
        system_id="test",
        intended_purpose="chatbot",
        compliance_target="EU_AI_ACT",
        high_risk_presumption=True,
        commit_ref="abc123",
        **extra,
    )


def test_section3_omits_human_oversight_when_absent():
    dossier = generate_dossier(_make_manifest(), _make_risk_result())
    assert set(dossier.section3.model_dump()) == _SECTION3_OLD_KEYS
    assert set(json.loads(dossier.model_dump_json())["section3"]) == _SECTION3_OLD_KEYS


def test_bundle_checksum_unchanged_when_oversight_absent():
    import hashlib

    from opencomplai_core.dossier_generator import BUNDLE_EXCLUDE

    dossier = generate_dossier(_make_manifest(), _make_risk_result())
    text = dossier.model_dump_json(exclude=BUNDLE_EXCLUDE)
    assert 'human_oversight"' not in text
    digest = f"sha256:{hashlib.sha256(text.encode()).hexdigest()}"
    assert dossier.bundle_checksum == digest


def test_section3_structured_oversight_counts_only_with_monitoring_and_incident():
    full = {
        "monitoring_approach": "Datadog drift checks",
        "incident_response_procedure": "runbooks/ai-incident.md",
    }
    both = generate_dossier(
        _oversight_manifest(human_oversight=_OVERSIGHT_BLOCK, **full),
        _make_risk_result(),
    )
    assert both.section3.provider_supplied is True
    assert both.section3.human_oversight_measures == []
    alone = generate_dossier(
        _oversight_manifest(human_oversight=_OVERSIGHT_BLOCK), _make_risk_result()
    )
    assert alone.section3.provider_supplied is False
    legacy = generate_dossier(
        _oversight_manifest(human_oversight_measures=["Two-person review"], **full),
        _make_risk_result(),
    )
    assert legacy.section3.provider_supplied is True


def test_section3_structured_oversight_without_roles_does_not_count():
    from opencomplai_core.models import HumanOversight

    manifest = _oversight_manifest(
        monitoring_approach="Datadog drift checks",
        incident_response_procedure="runbooks/ai-incident.md",
    )
    manifest.human_oversight = HumanOversight.model_construct(
        roles=[], escalation="Call the CTO", evidence_refs=[]
    )
    dossier = generate_dossier(manifest, _make_risk_result())
    assert dossier.section3.provider_supplied is False


def test_section3_legacy_only_manifest_unchanged():
    dossier = generate_dossier(
        _oversight_manifest(
            human_oversight_measures=["Daily bias dashboard review"],
            monitoring_approach="Datadog drift checks",
            incident_response_procedure="runbooks/ai-incident.md",
        ),
        _make_risk_result(),
    )
    assert dossier.section3.human_oversight_measures == ["Daily bias dashboard review"]
    assert dossier.section3.human_oversight is None
    assert set(dossier.section3.model_dump()) == _SECTION3_OLD_KEYS
    assert dossier.section3.provider_supplied is True


def test_structured_oversight_copied_verbatim():
    manifest = _oversight_manifest(human_oversight=_OVERSIGHT_BLOCK)
    dossier = generate_dossier(manifest, _make_risk_result())
    assert dossier.section3.human_oversight.model_dump(
        mode="json"
    ) == manifest.human_oversight.model_dump(mode="json")
    assert json.loads(dossier.model_dump_json())["section3"]["human_oversight"] == (
        manifest.human_oversight.model_dump(mode="json")
    )


_INVENTORY_BLOCK = {
    "agents": [
        {
            "id": "triage",
            "name": "Triage agent",
            "tools": [{"name": "search", "kind": "function"}],
            "mandate": {"permitted_actions": ["tool:search"]},
        }
    ]
}


def _inventory_manifest(with_block: bool, **extra) -> SystemManifest:
    kwargs = {"agent_inventory": _INVENTORY_BLOCK} if with_block else {}
    return SystemManifest(
        system_id="test",
        intended_purpose="chatbot",
        compliance_target="EU_AI_ACT",
        high_risk_presumption=True,
        commit_ref="abc123",
        **kwargs,
        **extra,
    )


def test_dossier_omits_agent_inventory_when_absent():
    dossier = generate_dossier(_inventory_manifest(False), _make_risk_result())
    assert dossier.agent_inventory is None
    assert "agent_inventory" not in dossier.model_dump_json()
    assert "agent_inventory" not in dossier.model_dump()


def test_bundle_checksum_unchanged_when_inventory_absent():
    import hashlib

    from opencomplai_core.dossier_generator import BUNDLE_EXCLUDE

    dossier = generate_dossier(_inventory_manifest(False), _make_risk_result())
    digest = hashlib.sha256(
        dossier.model_dump_json(exclude=BUNDLE_EXCLUDE).encode()
    ).hexdigest()
    assert dossier.bundle_checksum == f"sha256:{digest}"


def test_agent_inventory_copied_verbatim():
    manifest = _inventory_manifest(True)
    dossier = generate_dossier(manifest, _make_risk_result())
    expected = manifest.agent_inventory.model_dump(mode="json")
    assert dossier.agent_inventory.model_dump(mode="json") == expected
    assert json.loads(dossier.model_dump_json())["agent_inventory"] == expected


def test_agent_inventory_does_not_change_annex_iv_complete():
    without = generate_dossier(_inventory_manifest(False), _make_risk_result())
    with_block = generate_dossier(_inventory_manifest(True), _make_risk_result())
    assert with_block.annex_iv_complete == without.annex_iv_complete
    assert with_block.section3.provider_supplied == without.section3.provider_supplied


def test_agent_inventory_changes_checksum_when_present():
    without = generate_dossier(_inventory_manifest(False), _make_risk_result())
    with_block = generate_dossier(_inventory_manifest(True), _make_risk_result())
    assert with_block.bundle_checksum != without.bundle_checksum
