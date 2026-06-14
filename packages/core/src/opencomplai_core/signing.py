"""
Ed25519 signing helpers for ScanStatusArtifact and dossier checksums.

OSS mode: signature=None (unsigned).
Pro/Enterprise: sign_artifact() produces a base64-encoded Ed25519 signature.

Key loading order (runtime signing functions only):
  1. SIGNING_KEY_PRIVATE env var — base64-encoded PEM (used on Vercel / secrets manager)
  2. key_path argument — filesystem path (used by Docker / local setup)
"""

from __future__ import annotations

import base64
import json
import os
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from opencomplai_core.models import ScanStatusArtifact


def generate_keypair(key_dir: Path) -> str:
    """
    Generate an Ed25519 signing keypair in key_dir.

    Writes:
      key_dir/signing.key  — private key (PEM, chmod 600)
      key_dir/signing.pub  — public key (PEM)

    Returns the install_id UUID that should be stored in config.
    """
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    key_dir.mkdir(parents=True, exist_ok=True)

    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    signing_key_path = key_dir / "signing.key"
    signing_key_path.write_bytes(private_bytes)
    signing_key_path.chmod(0o600)
    (key_dir / "signing.pub").write_bytes(public_bytes)

    return str(uuid.uuid4())


def _load_private_key_bytes(key_path: Path) -> bytes:
    """
    Load private key PEM bytes.

    Checks SIGNING_KEY_PRIVATE env var first (base64-encoded PEM for Vercel /
    secrets-manager deployments); falls back to reading key_path from disk.
    """
    env_key = os.environ.get("SIGNING_KEY_PRIVATE")
    if env_key:
        return base64.b64decode(env_key)
    return key_path.read_bytes()


def sign_artifact(artifact: ScanStatusArtifact, key_path: Path) -> str:
    """
    Sign a ScanStatusArtifact with the Ed25519 private key at key_path.

    The signature covers json.dumps(artifact.model_dump(exclude={"signature"}), sort_keys=True).
    Returns a base64-encoded signature string.
    """
    from cryptography.hazmat.primitives import serialization

    private_bytes = _load_private_key_bytes(key_path)
    private_key = serialization.load_pem_private_key(private_bytes, password=None)

    payload = _canonical_payload(artifact)
    sig_bytes = private_key.sign(payload)
    return base64.b64encode(sig_bytes).decode("utf-8")


def sign_bundle_bytes(bundle_bytes: bytes, key_path: Path) -> str:
    """
    Sign arbitrary canonical bundle bytes (e.g. the Annex IV dossier bundle
    JSON) with the Ed25519 private key at key_path.

    Returned signature is base64-encoded. Verifiable with verify_bundle_bytes
    using the corresponding public key. This is the asymmetric path that
    Pro/Enterprise dossiers use; OSS falls back to HMAC (no public key needed)
    or remains unsigned.
    """
    from cryptography.hazmat.primitives import serialization

    private_bytes = _load_private_key_bytes(key_path)
    private_key = serialization.load_pem_private_key(private_bytes, password=None)
    sig_bytes = private_key.sign(bundle_bytes)
    return base64.b64encode(sig_bytes).decode("utf-8")


def verify_bundle_bytes(
    bundle_bytes: bytes, signature_b64: str, pub_key_path: Path
) -> bool:
    """Verify a bundle-bytes signature produced by sign_bundle_bytes."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import serialization

    pub_bytes = pub_key_path.read_bytes()
    public_key = serialization.load_pem_public_key(pub_bytes)
    try:
        public_key.verify(base64.b64decode(signature_b64), bundle_bytes)
        return True
    except InvalidSignature:
        return False


def verify_artifact(artifact: ScanStatusArtifact, pub_key_path: Path) -> bool:
    """
    Verify a ScanStatusArtifact signature against the public key at pub_key_path.

    Returns True if the signature is valid, False if absent or invalid.
    """
    if artifact.signature is None:
        return False

    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import serialization

    pub_bytes = pub_key_path.read_bytes()
    public_key = serialization.load_pem_public_key(pub_bytes)

    payload = _canonical_payload(artifact)
    sig_bytes = base64.b64decode(artifact.signature)
    try:
        public_key.verify(sig_bytes, payload)
        return True
    except InvalidSignature:
        return False


def _canonical_payload(artifact: ScanStatusArtifact) -> bytes:
    """Return the deterministic bytes that are signed/verified."""
    data = artifact.model_dump(exclude={"signature"})
    return json.dumps(data, sort_keys=True, default=str).encode("utf-8")
