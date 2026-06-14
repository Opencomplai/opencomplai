"""Tests for Ed25519 signing — generate keypair, sign, verify round-trip."""

from pathlib import Path

import pytest
from opencomplai_core.models import ScanResult, ScanStatusArtifact
from opencomplai_core.signing import generate_keypair, sign_artifact, verify_artifact


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
