"""Tests for Ed25519 signing — generate keypair, sign, verify round-trip."""

import json
from pathlib import Path

import pytest
from opencomplai_core.models import (
    FrameworkReport,
    GapReport,
    ScanResult,
    ScanStatusArtifact,
)
from opencomplai_core.signing import (
    SigningDomain,
    SigningKeyError,
    _canonical_payload,
    canonical_json_bytes,
    domain_separated,
    generate_keypair,
    resolve_key,
    sign_artifact,
    sign_bundle_bytes,
    verify_artifact,
    verify_bundle_bytes,
)


@pytest.fixture
def key_dir(tmp_path: Path) -> Path:
    return tmp_path / ".opencomplai"


@pytest.fixture
def keypair(key_dir: Path) -> Path:
    generate_keypair(key_dir)
    return key_dir


@pytest.fixture
def sample_artifact() -> ScanStatusArtifact:
    return ScanStatusArtifact(
        install_id="test-install-uuid",
        system_id="test-sys",
        commit_ref="abc123",
        result=ScanResult.PASS,
        failed_controls=[],
        evidence_hashes=["sha256:aabbcc"],
        rationale_hash="sha256:ddeeff",
        duration_ms=1500,
        pending_verifications_count=0,
        signature=None,
    )


def test_generate_keypair_creates_files(key_dir: Path) -> None:
    install_id = generate_keypair(key_dir)
    assert (key_dir / "signing.key").exists()
    assert (key_dir / "signing.pub").exists()
    assert len(install_id) == 36  # UUID format


def test_generate_keypair_idempotent(key_dir: Path) -> None:
    id1 = generate_keypair(key_dir)
    # Second call should work without error (overwrites existing keys)
    id2 = generate_keypair(key_dir)
    # Both are valid UUIDs; they differ (new key each time)
    assert len(id1) == 36
    assert len(id2) == 36


def test_signing_key_permissions(key_dir: Path) -> None:
    generate_keypair(key_dir)
    mode = (key_dir / "signing.key").stat().st_mode & 0o777
    # On Windows chmod is a no-op but must not raise
    assert mode in (0o600, 0o666, 0o777)


def test_sign_and_verify_round_trip(
    keypair: Path, sample_artifact: ScanStatusArtifact
) -> None:
    sig = sign_artifact(sample_artifact, keypair / "signing.key")
    assert isinstance(sig, str)
    assert len(sig) > 0

    signed_artifact = sample_artifact.model_copy(update={"signature": sig})
    assert verify_artifact(signed_artifact, keypair / "signing.pub") is True


def test_verify_fails_for_tampered_artifact(
    keypair: Path, sample_artifact: ScanStatusArtifact
) -> None:
    sig = sign_artifact(sample_artifact, keypair / "signing.key")
    tampered = sample_artifact.model_copy(
        update={"signature": sig, "system_id": "tampered-sys"}
    )
    assert verify_artifact(tampered, keypair / "signing.pub") is False


def test_verify_returns_false_for_unsigned_artifact(
    keypair: Path, sample_artifact: ScanStatusArtifact
) -> None:
    assert verify_artifact(sample_artifact, keypair / "signing.pub") is False


def test_sign_produces_deterministic_signature_for_same_key(
    keypair: Path, sample_artifact: ScanStatusArtifact
) -> None:
    # Ed25519 is deterministic — same key + same payload → same signature
    sig1 = sign_artifact(sample_artifact, keypair / "signing.key")
    sig2 = sign_artifact(sample_artifact, keypair / "signing.key")
    assert sig1 == sig2


def test_different_results_produce_different_signatures(
    keypair: Path, sample_artifact: ScanStatusArtifact
) -> None:
    sig_pass = sign_artifact(sample_artifact, keypair / "signing.key")
    fail_artifact = sample_artifact.model_copy(
        update={"result": ScanResult.CONTROL_FAIL}
    )
    sig_fail = sign_artifact(fail_artifact, keypair / "signing.key")
    assert sig_pass != sig_fail


def test_stored_pre_framework_reports_artifact_still_verifies() -> None:
    """An artifact signed and written by v0.7.1, before framework_reports
    existed, re-serialises to the same bytes and its signature verifies."""
    fixture = Path(__file__).parent / "fixtures" / "signed_artifact_v071"
    stored = (fixture / "artifact.json").read_text(encoding="utf-8")
    artifact = ScanStatusArtifact.model_validate_json(stored)

    assert artifact.framework_reports is None
    assert artifact.model_dump_json(indent=2) == stored.rstrip("\n")
    unsigned = json.loads(stored)
    del unsigned["signature"]
    assert _canonical_payload(artifact) == canonical_json_bytes(unsigned)
    assert verify_artifact(artifact, fixture / "signing.pub") is True


def test_signature_covers_framework_reports(
    keypair: Path, sample_artifact: ScanStatusArtifact
) -> None:
    report = FrameworkReport(
        framework="NIST_AI_RMF",
        label="NIST AI RMF 1.0",
        data_version="aaaaaaaaaaaa",
        derived_from="EU_AI_ACT",
        disclaimer_ref="DISCLAIMER_V2",
        report=GapReport(system_id="test-sys", commit_ref="abc123", generated_at="t"),
    )
    artifact = sample_artifact.model_copy(
        update={"framework_reports": {"NIST_AI_RMF": report}}
    )
    signed = artifact.model_copy(
        update={"signature": sign_artifact(artifact, keypair / "signing.key")}
    )
    assert verify_artifact(signed, keypair / "signing.pub") is True

    tampered = signed.model_copy(
        update={
            "framework_reports": {
                "NIST_AI_RMF": report.model_copy(update={"gated": True})
            }
        }
    )
    assert verify_artifact(tampered, keypair / "signing.pub") is False


# --- domain separation (EVID-CRYPTO) ---------------------------------------


def test_domain_separated_binds_the_purpose_into_the_signed_bytes():
    payload = b"PAYLOAD"
    artifact = domain_separated(SigningDomain.ARTIFACT, payload)
    badge = domain_separated(SigningDomain.BADGE, payload)

    assert artifact != badge
    assert artifact.endswith(payload)
    assert badge.endswith(payload)
    assert artifact.startswith(b"opencomplai.sig.v1\x00")
    # The version lives in the prefix so a future scheme is a new prefix
    # rather than a silent reinterpretation of the same bytes.
    assert artifact == b"opencomplai.sig.v1\x00scan-status-artifact\x00PAYLOAD"


def test_a_signature_does_not_verify_under_a_different_domain(tmp_path):
    """
    The defect this exists to close.

    `sign_artifact` and the badge verifier used to produce byte-identical
    preimages, so a signature from `opencomplai check --sign` verified
    unmodified as a compliance-badge signature for the same object — one
    attestation silently doing duty as another.
    """
    generate_keypair(tmp_path)
    priv, pub = tmp_path / "signing.key", tmp_path / "signing.pub"
    body = canonical_json_bytes({"system_id": "s", "result": "pass"})

    signature = sign_bundle_bytes(body, priv, SigningDomain.BADGE)

    assert verify_bundle_bytes(body, signature, pub, SigningDomain.BADGE) is True
    for other in (SigningDomain.ARTIFACT, SigningDomain.DOSSIER_BUNDLE):
        assert verify_bundle_bytes(body, signature, pub, other) is False


def test_an_artifact_signature_is_not_a_badge_signature(tmp_path, sample_artifact):
    """End-to-end version of the same property, across the two real entry points."""
    generate_keypair(tmp_path)
    priv, pub = tmp_path / "signing.key", tmp_path / "signing.pub"

    signature = sign_artifact(sample_artifact, priv)
    badge_preimage = canonical_json_bytes(
        sample_artifact.model_dump(exclude={"signature"})
    )

    # Before domain separation this assertion was False: the CLI's signature
    # was accepted verbatim by the badge verifier.
    assert (
        verify_bundle_bytes(badge_preimage, signature, pub, SigningDomain.BADGE)
        is False
    )
    # ...and it still verifies as what it actually is.
    signed = sample_artifact.model_copy(update={"signature": signature})
    assert verify_artifact(signed, pub) is True


def test_approval_token_domain_sign_and_verify_round_trip(tmp_path):
    """HALT-WIRE: the HITL approval token uses its own signing domain
    (`SigningDomain.APPROVAL_TOKEN`), so a token signature verifies only as
    a token — not as an artifact/dossier/badge signature over the same
    bytes, and vice versa."""
    generate_keypair(tmp_path)
    priv, pub = tmp_path / "signing.key", tmp_path / "signing.pub"
    payload = canonical_json_bytes(
        {
            "system_id": "sys-a",
            "commit_ref": "abc123",
            "halted_at": "2026-08-17T00:00:00+00:00",
            "approver": "qa@example.com",
            "issued_at": "2026-08-17T00:05:00+00:00",
        }
    )

    signature = sign_bundle_bytes(payload, priv, SigningDomain.APPROVAL_TOKEN)

    assert (
        verify_bundle_bytes(payload, signature, pub, SigningDomain.APPROVAL_TOKEN)
        is True
    )
    for other in (
        SigningDomain.ARTIFACT,
        SigningDomain.DOSSIER_BUNDLE,
        SigningDomain.BADGE,
    ):
        assert verify_bundle_bytes(payload, signature, pub, other) is False

    tampered = canonical_json_bytes(
        {
            "system_id": "sys-a-tampered",
            "commit_ref": "abc123",
            "halted_at": "2026-08-17T00:00:00+00:00",
            "approver": "qa@example.com",
            "issued_at": "2026-08-17T00:05:00+00:00",
        }
    )
    assert (
        verify_bundle_bytes(tampered, signature, pub, SigningDomain.APPROVAL_TOKEN)
        is False
    )


def test_untagged_legacy_signatures_do_not_verify(tmp_path):
    """
    Hard cutover, pinned.

    Nothing in this system re-verifies a stored signature, so there is no
    population an accept-both window would protect — and while such a window
    was open it would keep accepting exactly the confusable signatures this
    change removes.
    """
    from cryptography.hazmat.primitives import serialization

    generate_keypair(tmp_path)
    priv, pub = tmp_path / "signing.key", tmp_path / "signing.pub"
    body = b"legacy bundle bytes"

    private_key = serialization.load_pem_private_key(priv.read_bytes(), password=None)
    import base64

    legacy = base64.b64encode(private_key.sign(body)).decode()

    for domain in SigningDomain:
        assert verify_bundle_bytes(body, legacy, pub, domain) is False


def test_new_domain_values_are_ascii_and_unique():
    values = [d.value for d in SigningDomain]
    assert len(values) == 10
    assert len(set(values)) == len(values)
    assert all(v.isascii() and "\x00" not in v for v in values)


def test_new_domains_are_mutually_exclusive(keypair: Path):
    payload = b"one payload, many purposes"
    for signed_under in SigningDomain:
        sig = sign_bundle_bytes(payload, keypair / "signing.key", signed_under)
        for checked_under in SigningDomain:
            ok = verify_bundle_bytes(
                payload, sig, keypair / "signing.pub", checked_under
            )
            assert ok is (checked_under is signed_under)


def _b64_pem(key_dir: Path) -> str:
    import base64

    return base64.b64encode((key_dir / "signing.key").read_bytes()).decode()


def test_resolve_key_prefers_env(tmp_path: Path, monkeypatch):
    generate_keypair(tmp_path / "env")
    generate_keypair(tmp_path / "disk")
    monkeypatch.setenv("SIGNING_KEY_PRIVATE", _b64_pem(tmp_path / "env"))
    assert (
        resolve_key(tmp_path / "disk" / "signing.key")
        == (tmp_path / "env" / "signing.key").read_bytes()
    )


def test_resolve_key_falls_back_to_file(keypair: Path, monkeypatch):
    monkeypatch.delenv("SIGNING_KEY_PRIVATE", raising=False)
    path = keypair / "signing.key"
    assert resolve_key(path) == path.read_bytes()


def test_resolve_key_fails_loudly_when_neither_exists(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("SIGNING_KEY_PRIVATE", raising=False)
    for arg in (None, tmp_path / "missing.key"):
        with pytest.raises(SigningKeyError) as exc:
            resolve_key(arg)
        assert isinstance(exc.value, FileNotFoundError)
        assert "SIGNING_KEY_PRIVATE" in str(exc.value)
        assert "opencomplai init" in str(exc.value)


@pytest.mark.parametrize("bad", ["!!not-base64!!", "bm90IGEgcGVt"])
def test_resolve_key_bad_env_does_not_fall_back_to_file(
    keypair: Path, monkeypatch, bad: str
):
    monkeypatch.setenv("SIGNING_KEY_PRIVATE", bad)
    with pytest.raises(SigningKeyError) as exc:
        resolve_key(keypair / "signing.key")
    assert "SIGNING_KEY_PRIVATE" in str(exc.value)
    assert bad not in str(exc.value)


def test_sign_bundle_bytes_still_works_with_env_key(
    keypair: Path, tmp_path: Path, monkeypatch
):
    monkeypatch.setenv("SIGNING_KEY_PRIVATE", _b64_pem(keypair))
    sig = sign_bundle_bytes(b"x", tmp_path / "nope.key", SigningDomain.BADGE)
    assert verify_bundle_bytes(b"x", sig, keypair / "signing.pub", SigningDomain.BADGE)


def _wrapped(b64: str) -> str:
    return "\n".join(b64[i : i + 76] for i in range(0, len(b64), 76))


@pytest.mark.parametrize(
    "shape",
    [
        lambda b: _wrapped(b),  # GNU `base64` output, 76 columns
        lambda b: _wrapped(b) + "\n",
        lambda b: b + "\n",
        lambda b: "  " + b + "\r\n",
    ],
    ids=["wrapped", "wrapped-trailing-newline", "trailing-newline", "padded-crlf"],
)
def test_env_key_tolerates_wrapping_and_trailing_whitespace(
    keypair: Path, tmp_path: Path, monkeypatch, shape
):
    monkeypatch.setenv("SIGNING_KEY_PRIVATE", shape(_b64_pem(keypair)))
    assert resolve_key(None) == (keypair / "signing.key").read_bytes()
    sig = sign_bundle_bytes(b"x", tmp_path / "nope.key", SigningDomain.BADGE)
    assert verify_bundle_bytes(b"x", sig, keypair / "signing.pub", SigningDomain.BADGE)


def test_classification_acceptance_domain_is_exclusive(keypair: Path):
    payload = b'{"record_type":"classification_acceptance"}'
    sig = sign_bundle_bytes(
        payload, keypair / "signing.key", SigningDomain.CLASSIFICATION_ACCEPTANCE
    )
    for domain in SigningDomain:
        ok = verify_bundle_bytes(payload, sig, keypair / "signing.pub", domain)
        assert ok is (domain is SigningDomain.CLASSIFICATION_ACCEPTANCE)
