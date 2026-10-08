"""
Ed25519 signing helpers for ScanStatusArtifact and dossier checksums.

OSS mode: signature=None (unsigned).
Pro/Enterprise: sign_artifact() produces a base64-encoded Ed25519 signature.

Key loading order (``resolve_key``, used by the runtime signing functions):
  1. SIGNING_KEY_PRIVATE env var — base64-encoded PEM (used on Vercel / secrets manager)
  2. key_path argument — filesystem path (used by Docker / local setup)
  Neither present: ``SigningKeyError`` (never a silent unsigned result).

Signing domains cover scan-status artifacts, dossier bundles, badges, approval
tokens and the shared signed logs, attestations and deployer packs.
"""

from __future__ import annotations

import base64
import json
import os
import uuid
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from opencomplai_core.models import ScanStatusArtifact


_DOMAIN_PREFIX = b"opencomplai.sig.v1"


class SigningDomain(StrEnum):
    """
    What a signature is *for*.

    One Ed25519 keypair signs several unrelated message formats in this system:
    scan-status artifacts, Annex IV dossier bundles, compliance badges,
    approval tokens, signed hash-chain logs (oversight, agent, incident),
    agent attestations and deployer packs. Nothing in the signed bytes said which
    was which, and that was not theoretical — a signature produced by
    ``opencomplai check --sign`` verified, unmodified, as a valid
    compliance-badge signature for the same artifact, because both sides
    serialise with ``json.dumps(..., sort_keys=True)`` and the two preimages
    come out byte-identical.

    Binding the purpose into the signed bytes is what makes a signature mean
    "this key attests *this artifact*" rather than "this key signed *these
    bytes*, for some purpose you must infer from context".
    """

    ARTIFACT = "scan-status-artifact"
    DOSSIER_BUNDLE = "annex-iv-dossier-bundle"
    BADGE = "compliance-badge"
    APPROVAL_TOKEN = "hitl-approval-token"
    OVERSIGHT_LOG = "oversight-log"
    AGENT_LOG = "agent-log"
    INCIDENT_LOG = "incident-log"
    ATTESTATION = "agent-attestation"
    DEPLOYER_PACK = "deployer-pack"
    # Committed classification-acceptance and trap-approval records.
    CLASSIFICATION_ACCEPTANCE = "classification-acceptance"


def domain_separated(domain: SigningDomain, payload: bytes) -> bytes:
    """
    Bind ``payload`` to a purpose before signing.

    ``opencomplai.sig.v1\\x00<domain>\\x00<payload>``. The version sits in the
    prefix so a future scheme change is a new prefix rather than a silent
    reinterpretation of the same bytes, and the NUL separators make the framing
    unambiguous — no domain value contains a NUL, so no payload can be
    constructed that shifts the boundary and impersonates another domain.
    """
    return _DOMAIN_PREFIX + b"\x00" + domain.value.encode("ascii") + b"\x00" + payload


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


class SigningKeyError(FileNotFoundError):
    """No usable signing key. Subclasses FileNotFoundError for old ``except`` sites."""


def resolve_key(key_path: Path | None = None) -> bytes:
    """
    Return private-key PEM bytes, or raise ``SigningKeyError``.

    Order: ``SIGNING_KEY_PRIVATE`` env (base64 PEM), then ``key_path`` if the file
    exists. Whitespace in the env value (line wraps, trailing newline) is ignored.
    A non-empty env value that is not a valid Ed25519 PEM raises instead
    of falling through to the file, so a broken secret is never masked by a stale
    local key. Key material is never placed in a message.
    """
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    env_key = os.environ.get("SIGNING_KEY_PRIVATE")
    if env_key:
        try:
            pem = base64.b64decode("".join(env_key.split()), validate=True)
            key = serialization.load_pem_private_key(pem, password=None)
            if not isinstance(key, Ed25519PrivateKey):
                raise ValueError("not an Ed25519 key")
        except Exception:
            raise SigningKeyError(
                "SIGNING_KEY_PRIVATE is set but is not a base64-encoded Ed25519 PEM"
            ) from None
        return pem
    if key_path is not None and key_path.is_file():
        return key_path.read_bytes()
    raise SigningKeyError(
        "No signing key: set SIGNING_KEY_PRIVATE (base64 PEM) or provide a key "
        "file (run `opencomplai init` to create one)"
    )


def _load_private_key_bytes(key_path: Path) -> bytes:
    """Load private key PEM bytes (see ``resolve_key``)."""
    return resolve_key(key_path)


def sign_artifact(artifact: ScanStatusArtifact, key_path: Path) -> str:
    """
    Sign a ScanStatusArtifact with the Ed25519 private key at key_path.

    The signature covers ``domain_separated(SigningDomain.ARTIFACT,
    _canonical_payload(artifact))``.

    The domain tag is applied here, around the canonical payload, rather than
    inside ``_canonical_payload``. That is deliberate: ``_canonical_payload``'s
    output is a published cross-implementation contract — ``dashboard_ingest``
    reimplements it in ``canonical.py`` and a parity test fails the build on the
    first divergent byte — so the canonicalisation and the signing envelope have
    to stay separable.
    """
    from cryptography.hazmat.primitives import serialization

    private_bytes = _load_private_key_bytes(key_path)
    private_key = serialization.load_pem_private_key(private_bytes, password=None)

    payload = domain_separated(SigningDomain.ARTIFACT, _canonical_payload(artifact))
    sig_bytes = private_key.sign(payload)
    return base64.b64encode(sig_bytes).decode("utf-8")


def sign_bundle_bytes(
    bundle_bytes: bytes, key_path: Path, domain: SigningDomain
) -> str:
    """
    Sign canonical bundle bytes for one specific purpose.

    ``domain`` is required and has no default. It used to be absent entirely,
    and the result was that this function would sign anything and
    ``verify_bundle_bytes`` would accept anything the key had ever signed — a
    dossier-bundle signature and a compliance-badge signature were the same
    object. Defaulting the parameter would have kept every existing caller
    silently on the ambiguous path, which is the failure this change exists to
    remove.

    Returned signature is base64-encoded, and verifies only via
    ``verify_bundle_bytes`` with the *same* domain. This is the Ed25519 path every
    bundle domain signs through; there is no symmetric fallback, and a dossier
    with no Ed25519 key stays unsigned.
    """
    from cryptography.hazmat.primitives import serialization

    private_bytes = _load_private_key_bytes(key_path)
    private_key = serialization.load_pem_private_key(private_bytes, password=None)
    sig_bytes = private_key.sign(domain_separated(domain, bundle_bytes))
    return base64.b64encode(sig_bytes).decode("utf-8")


def verify_bundle_bytes(
    bundle_bytes: bytes,
    signature_b64: str,
    pub_key_path: Path,
    domain: SigningDomain,
) -> bool:
    """
    Verify a bundle-bytes signature produced by ``sign_bundle_bytes`` for
    ``domain``. A signature made for a *different* domain does not verify here —
    that is the entire point.

    **This is a hard cutover: signatures made before domain separation do not
    verify, and there is deliberately no option to accept them.** An
    accept-both window was considered and rejected. Nothing in this system ever
    re-verifies a stored signature — badge rows are inert attestations,
    dossier signatures are never verified in production — so "existing
    signatures stop verifying" has no code path to break. What such a window
    *would* do is keep the confusion alive under a flag: while untagged
    signatures are accepted, a signature minted in one context still passes as
    another, which is the defect being removed. See the migration note in
    ``docs/src/architecture/data-model.md``.
    """
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import serialization

    pub_bytes = pub_key_path.read_bytes()
    public_key = serialization.load_pem_public_key(pub_bytes)
    try:
        public_key.verify(
            base64.b64decode(signature_b64), domain_separated(domain, bundle_bytes)
        )
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

    sig_bytes = base64.b64decode(artifact.signature)
    payload = domain_separated(SigningDomain.ARTIFACT, _canonical_payload(artifact))
    try:
        public_key.verify(sig_bytes, payload)
        return True
    except InvalidSignature:
        return False


def canonical_json_bytes(data: dict) -> bytes:
    """
    The one canonical JSON serialisation used for anything this key signs.

    ``badges.py`` used to re-implement this inline as
    ``json.dumps(artifact, sort_keys=True)`` — the same call minus
    ``default=str``. The two agreed byte-for-byte only because badge artifacts
    happen to contain JSON-native scalars; a datetime or Decimal appearing in
    one and not the other would have made a valid signature stop verifying,
    with no test catching it. Having one implementation is what makes the
    domain tags meaningful rather than decorative.

    ``default=str`` is retained for parity with ``dashboard_ingest.canonical``,
    which must match this byte-for-byte. It is a defensive fallback, not a
    licence to sign arbitrary objects — a value it has to stringify is a bug in
    the caller, not a supported case.
    """
    return json.dumps(data, sort_keys=True, default=str).encode("utf-8")


def _canonical_payload(artifact: ScanStatusArtifact) -> bytes:
    """Return the deterministic bytes that are signed/verified."""
    return canonical_json_bytes(artifact.model_dump(exclude={"signature"}))
