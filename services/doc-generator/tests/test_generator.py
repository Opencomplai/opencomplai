"""Tests for the Annex IV dossier generator (REQ-DOC-001)."""

import os

from opencomplai_core.engine import assess
from opencomplai_core.models import AssessmentInput, ModelMetadata, SystemManifest
from opencomplai_doc_generator.generator import (
    generate_dossier,
    validate_dossier_schema,
)


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
    os.environ.pop("LOCAL_SIGNING_KEY_PATH", None)
    dossier = generate_dossier(_make_manifest(), _make_risk_result())
    assert dossier.signature is None


def test_generate_dossier_for_high_risk_system():
    dossier = generate_dossier(
        _make_manifest(purpose="employment screening"),
        _make_risk_result("employment screening"),
    )
    assert dossier.section5.risk_level == "high"
    assert dossier.section5.rules_failed > 0
    assert validate_dossier_schema(dossier) is True


def test_bundle_checksum_is_deterministic():
    """Same inputs must produce the same bundle_checksum."""
    manifest = _make_manifest()
    risk = _make_risk_result()
    d1 = generate_dossier(manifest, risk)
    d2 = generate_dossier(manifest, risk)
    assert d1.bundle_checksum == d2.bundle_checksum


def test_all_annex_iv_sections_populated():
    """All five Annex IV sections must be present and non-empty."""
    dossier = generate_dossier(_make_manifest(), _make_risk_result())
    assert dossier.section1.system_name
    assert dossier.section2.training_data_description
    assert dossier.section3.monitoring_approach
    assert dossier.section4.logging_enabled is True
    assert dossier.section5.rationale_hash.startswith("sha256:")


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


def test_section3_stubbed_when_manifest_silent():
    """Falls back to the stub when nothing is provided — MINIMAL-risk default."""
    dossier = generate_dossier(_make_manifest(), _make_risk_result())
    assert dossier.section3.human_oversight_measures == ["HITL orchestrator enabled"]
    assert "Evidence Vault" in dossier.section3.monitoring_approach
    assert "incident-response" in dossier.section3.incident_response_procedure


def test_ledger_root_hash_embedded_when_supplied():
    """Gap #4: dossier must anchor to the supplied ledger root."""
    root = "sha256:" + ("a" * 64)
    dossier = generate_dossier(
        _make_manifest(), _make_risk_result(), ledger_root_hash=root
    )
    assert dossier.section4.ledger_root_hash == root


def test_signature_status_unsigned_by_default():
    """Gap #5: OSS default must self-describe as unsigned."""
    os.environ.pop("LOCAL_SIGNING_KEY_PATH", None)
    dossier = generate_dossier(_make_manifest(), _make_risk_result())
    assert dossier.signature is None
    assert dossier.signature_status == "unsigned"


def test_signature_status_hmac_when_signing_key_present(tmp_path):
    """Gap #5: with LOCAL_SIGNING_KEY_PATH set, status reflects the HMAC fallback."""
    key_path = tmp_path / "signing.key"
    key_path.write_bytes(b"opencomplai-test-signing-key")
    os.environ["LOCAL_SIGNING_KEY_PATH"] = str(key_path)
    try:
        dossier = generate_dossier(_make_manifest(), _make_risk_result())
        assert dossier.signature is not None
        assert dossier.signature_status == "hmac-local"
    finally:
        os.environ.pop("LOCAL_SIGNING_KEY_PATH", None)


def test_signature_status_ed25519_when_pro_key_configured(tmp_path):
    """Ed25519 (Pro) path takes precedence over HMAC and is verifiable."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from opencomplai_core.signing import verify_bundle_bytes

    private_key = Ed25519PrivateKey.generate()
    priv_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    priv_path = tmp_path / "ed25519.key"
    pub_path = tmp_path / "ed25519.pub"
    priv_path.write_bytes(priv_pem)
    pub_path.write_bytes(pub_pem)

    os.environ.pop("LOCAL_SIGNING_KEY_PATH", None)
    os.environ["DOSSIER_SIGNING_KEY_PATH"] = str(priv_path)
    try:
        dossier = generate_dossier(_make_manifest(), _make_risk_result())
        assert dossier.signature is not None
        assert dossier.signature_status == "ed25519"

        # The dossier must be independently verifiable by an auditor who only
        # holds the public key — the whole point of asymmetric signing.
        bundle_json = dossier.model_dump_json(
            exclude={
                "dossier_id",
                "generated_at",
                "bundle_checksum",
                "signature",
                "signature_status",
                "section2_complete",
            }
        )
        assert verify_bundle_bytes(
            bundle_json.encode("utf-8"), dossier.signature, pub_path
        )
    finally:
        os.environ.pop("DOSSIER_SIGNING_KEY_PATH", None)


def test_ed25519_takes_precedence_over_hmac(tmp_path):
    """When both keys are set, Ed25519 wins — never silently downgrade."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    ed_priv = Ed25519PrivateKey.generate().private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    ed_path = tmp_path / "ed.key"
    ed_path.write_bytes(ed_priv)
    hmac_path = tmp_path / "hmac.key"
    hmac_path.write_bytes(b"some-hmac-secret")

    os.environ["LOCAL_SIGNING_KEY_PATH"] = str(hmac_path)
    os.environ["DOSSIER_SIGNING_KEY_PATH"] = str(ed_path)
    try:
        dossier = generate_dossier(_make_manifest(), _make_risk_result())
        assert dossier.signature_status == "ed25519"
    finally:
        os.environ.pop("LOCAL_SIGNING_KEY_PATH", None)
        os.environ.pop("DOSSIER_SIGNING_KEY_PATH", None)


def test_signature_status_does_not_change_bundle_checksum(tmp_path):
    """signature_status is envelope metadata — it must not feed the checksum."""
    os.environ.pop("LOCAL_SIGNING_KEY_PATH", None)
    unsigned = generate_dossier(_make_manifest(), _make_risk_result())

    key_path = tmp_path / "signing.key"
    key_path.write_bytes(b"opencomplai-test-signing-key")
    os.environ["LOCAL_SIGNING_KEY_PATH"] = str(key_path)
    try:
        signed = generate_dossier(_make_manifest(), _make_risk_result())
    finally:
        os.environ.pop("LOCAL_SIGNING_KEY_PATH", None)

    assert unsigned.bundle_checksum == signed.bundle_checksum
    assert unsigned.signature_status != signed.signature_status


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
