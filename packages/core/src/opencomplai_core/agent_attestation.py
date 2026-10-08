"""Signed agent attestations (`agent_attestation/v1`), checked fully offline.

An attestation says one thing: the holder of a signing key vouched for one
agent's mandate hash until an expiry. It makes no compliance claim and carries
no legal wording. Nothing here uploads or stores anything.

Cross-language contract (the browser verifier recomputes these bytes with Node
Ed25519; the committed golden vectors are its parity test):

* The signed bytes are ``domain_separated(SigningDomain.ATTESTATION,
  canonical_json_bytes(<every field except signature>))``.
* ``canonical_json_bytes`` uses Python default separators and ``ensure_ascii``.
  So ``issuer`` is printable ASCII only (reversible decision: allowing Unicode
  would force the JS side to reproduce Unicode escaping) and timestamps are
  ``YYYY-MM-DDTHH:MM:SSZ`` (UTC, whole seconds). Do not relax either without
  telling the consumer.
* ``key_id`` is ONE normalised fingerprint, :func:`key_id_for_public_pem`.
  It is recomputed in SQL and TypeScript over the stored public-key PEM text.
  Never hash the raw ``signing.pub`` bytes (``keys rotate`` prints that value,
  trailing newline included; it does not match the stored, stripped PEM).

This module never reads the clock: callers pass ``now``.
"""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from opencomplai_core.signing import (
    SigningDomain,
    canonical_json_bytes,
    domain_separated,
)

ATTESTATION_SCHEMA_PATH = (
    Path(__file__).parent / "data" / "agent_attestation_v1.schema.json"
)
KEY_ID_STRIP_CHARS = " \t\n\r\x0b\x0c"
_TS = r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"


def _parse_ts(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


class AgentAttestation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["agent_attestation/v1"]
    agent_id: str = Field(min_length=1)
    system_id: str = Field(min_length=1)
    issuer: str = Field(pattern=r"^[\x20-\x7e]{1,128}$")
    mandate_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    issued_at: str = Field(pattern=_TS)
    expires_at: str = Field(pattern=_TS)
    key_id: str = Field(pattern=r"^sha256:[0-9a-f]{16}$")
    signature: str | None = Field(default=None, pattern=r"^[A-Za-z0-9+/]{86}==$")

    @model_validator(mode="after")
    def _dates(self) -> AgentAttestation:
        # strptime also rejects impossible dates (month 13) the pattern lets through.
        if _parse_ts(self.expires_at) <= _parse_ts(self.issued_at):
            raise ValueError("expires_at must be after issued_at")
        return self


@dataclass(frozen=True)
class AttestationVerification:
    status: Literal["verified", "unsigned", "invalid"]
    code: str | None = None


def mandate_sha256(mandate) -> str:
    """Hash of a mandate (model or dict). ``exclude_none`` keeps the hash stable
    if optional mandate fields are added later."""
    d = (
        mandate
        if isinstance(mandate, dict)
        else mandate.model_dump(mode="json", exclude_none=True)
    )
    return "sha256:" + hashlib.sha256(canonical_json_bytes(d)).hexdigest()


def key_id_for_public_pem(pem: bytes | str) -> str:
    """Normalised key fingerprint: sha256 over the UTF-8 PEM text stripped of
    ASCII whitespace at both ends, first 16 hex, prefixed ``sha256:``. The
    dashboard recomputes exactly this over ``signing_keys.public_key_pem``."""
    text = pem.decode("utf-8") if isinstance(pem, bytes) else pem
    digest = hashlib.sha256(text.strip(KEY_ID_STRIP_CHARS).encode("utf-8")).hexdigest()
    return "sha256:" + digest[:16]


def public_pem_for_private_pem(pem: bytes) -> bytes:
    from cryptography.hazmat.primitives import serialization

    key = serialization.load_pem_private_key(pem, password=None)
    return key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )


def signing_payload(att: AgentAttestation) -> bytes:
    return domain_separated(
        SigningDomain.ATTESTATION,
        canonical_json_bytes(att.model_dump(exclude={"signature"})),
    )


def sign_attestation(
    *,
    agent_id: str,
    system_id: str,
    mandate_sha256: str,
    issuer: str,
    issued_at: str,
    expires_at: str,
    private_pem: bytes,
) -> dict:
    """Build and sign an attestation; returns the full dict. No clock."""
    from cryptography.hazmat.primitives import serialization

    att = AgentAttestation(
        schema_version="agent_attestation/v1",
        agent_id=agent_id,
        system_id=system_id,
        issuer=issuer,
        mandate_sha256=mandate_sha256,
        issued_at=issued_at,
        expires_at=expires_at,
        key_id=key_id_for_public_pem(public_pem_for_private_pem(private_pem)),
    )
    key = serialization.load_pem_private_key(private_pem, password=None)
    sig = base64.b64encode(key.sign(signing_payload(att))).decode("ascii")
    return att.model_copy(update={"signature": sig}).model_dump()


def verify_attestation(
    data: dict,
    public_pem: bytes,
    *,
    now: datetime,
    expect_mandate_sha256: str | None = None,
) -> AttestationVerification:
    """Offline check; never raises on bad content. Codes, in check order:
    schema, (unsigned), key_id, signature, expired, not_yet_valid, mandate_mismatch."""
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")

    def bad(code: str) -> AttestationVerification:
        return AttestationVerification("invalid", code)

    try:
        att = AgentAttestation.model_validate(data)
    except (ValidationError, TypeError, ValueError):
        return bad("schema")
    if att.signature is None:
        return AttestationVerification("unsigned")
    try:
        if key_id_for_public_pem(public_pem) != att.key_id:
            return bad("key_id")
    except UnicodeDecodeError:
        return bad("key_id")
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import serialization

    try:
        pub = serialization.load_pem_public_key(public_pem)
        pub.verify(base64.b64decode(att.signature), signing_payload(att))
    except (InvalidSignature, ValueError, TypeError, AttributeError):
        return bad("signature")
    if now >= _parse_ts(att.expires_at):
        return bad("expired")
    if now < _parse_ts(att.issued_at):
        return bad("not_yet_valid")
    if (
        expect_mandate_sha256 is not None
        and att.mandate_sha256 != expect_mandate_sha256
    ):
        return bad("mandate_mismatch")
    return AttestationVerification("verified")
