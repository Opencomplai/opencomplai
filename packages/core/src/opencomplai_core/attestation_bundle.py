"""Signed attestation bundle: an organisation's recorded attestations and
exclusions, served to `check` by an endpoint it is configured to fetch from.

The bundle is hashed in its canonical form: the model dumped to JSON without
`signature`, keys sorted, no whitespace, unset optional fields left out. The
signature is Ed25519 over the ASCII hex of that SHA-256 under the
`attestation-bundle` signing domain (`bundle_signing_bytes`), so a party that
holds only `{sha256, signature}` (the scan artifact carries exactly that) can
check it against the issuer's public key without the bundle, and the signature
means nothing for any other kind of signed document.

Nothing here fetches, merges or signs: the issuer signs with its own key, and
the CLI copies the hash and signature into the artifact unchanged.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer,
    model_validator,
)

from opencomplai_core.models import (
    Attestation,
    AttestationBundleRef,
    BundleKeyId,
    BundleSignature,
    BundleTimestamp,
)
from opencomplai_core.serialization import OMIT_EMPTY, OMIT_NONE, omit_by_table
from opencomplai_core.signing import SigningDomain, domain_separated

SCHEMA_ID = "https://schemas.opencomplai.dev/attestation_bundle/v1"
BUNDLE_VERSION = "attestation_bundle/v1"


# The published schema is closed and bounded, so a bundle is held to the limits
# the model enforces. The manifest's `Attestation` keeps its own, looser ones.
MAX_EVIDENCE_PER_ATTESTATION = 50
_Justification = Annotated[
    str,
    Field(
        min_length=1,
        max_length=2000,
        pattern=r"\S",  # not blank
        description="Why the requirement does not apply",
    ),
]


class BundleEvidence(BaseModel):
    """A pointer to the evidence behind a bundled attestation, never the content."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["link", "file", "record"]
    ref: str = Field(
        ..., min_length=1, max_length=2048, description="URL, path or record id"
    )
    sha256: str | None = Field(
        None,
        pattern=r"^[0-9a-f]{64}$",
        description="SHA-256 of the referenced file, when there is one",
    )

    @model_serializer(mode="wrap")
    def _omit_unset_sha256(
        self, handler: SerializerFunctionWrapHandler
    ) -> dict[str, Any]:
        return omit_by_table(self, handler(self), {"sha256": OMIT_NONE})


class BundleAttestation(BaseModel):
    """One record of a bundle: a recorded attestation with a required record id
    and bounded text.

    Personal data: `attested_by` is a display name, never an email, because it
    flows into `evidence_ref` and so into signed artifacts.
    """

    model_config = ConfigDict(extra="forbid")

    statement: str = Field(..., min_length=1, max_length=4000)
    attested_by: str = Field(
        ...,
        min_length=1,
        max_length=200,
        pattern=r"^[^@]+$",
        description="Display name of the attester; an email address is refused",
    )
    attested_at: str = Field(
        ...,
        max_length=40,
        pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}(T[0-9:.]+(Z|[+-][0-9]{2}:[0-9]{2})?)?$",
        description="ISO 8601 date, or timestamp with an optional UTC offset",
    )
    valid_until: date | None = Field(
        None,
        description=(
            "Last day the attestation counts. From the next day the row reads "
            "Unverified until it is renewed. Without it the attestation does not expire."
        ),
    )
    evidence: list[BundleEvidence] = Field(
        default_factory=list,
        max_length=MAX_EVIDENCE_PER_ATTESTATION,
        description="Pointers to the evidence behind the statement",
    )
    record_id: str = Field(
        ...,
        pattern=r"^[A-Za-z0-9_.:-]{1,128}$",
        description="Id of the record the attestation was read from",
    )

    @model_serializer(mode="wrap")
    def _omit_unset_fields(
        self, handler: SerializerFunctionWrapHandler
    ) -> dict[str, Any]:
        # Same bytes as an `Attestation` that leaves the optional fields unset.
        return omit_by_table(
            self, handler(self), {"valid_until": OMIT_NONE, "evidence": OMIT_EMPTY}
        )

    def to_attestation(self) -> Attestation:
        """The manifest `Attestation` this record merges as."""
        return Attestation.model_validate(self.model_dump(mode="json"))


class AttestationBundle(BaseModel):
    """Active attestations and exclusions for one system, or the whole organisation.

    Every top-level field is required, so the signed JSON always carries the
    same keys.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["attestation_bundle/v1"]
    system_id: str | None = Field(
        ..., description="The system the bundle is for; null for organisation-wide"
    )
    issued_at: BundleTimestamp
    attestations: dict[str, dict[str, BundleAttestation]] = Field(
        ...,
        description=(
            "Framework key -> requirement id -> attestation. Every attestation "
            "carries the `record_id` of its record."
        ),
    )
    excluded: dict[str, dict[str, _Justification]] = Field(
        ...,
        description=(
            "Framework key -> requirement id -> why the requirement does not apply"
        ),
    )
    key_id: BundleKeyId
    signature: BundleSignature

    @field_validator("issued_at")
    @classmethod
    def _issued_at_is_iso(cls, value: str) -> str:
        datetime.fromisoformat(value)
        return value

    @model_validator(mode="after")
    def _exclusions_are_justified(self) -> AttestationBundle:
        for framework, reasons in self.excluded.items():
            for rid, reason in reasons.items():
                if not reason.strip():
                    raise ValueError(
                        f"excluded.{framework}.{rid} needs a justification"
                    )
        return self

    @property
    def count(self) -> int:
        """Records the bundle carries: attestations plus exclusions."""
        return sum(len(rows) for rows in self.attestations.values()) + sum(
            len(rows) for rows in self.excluded.values()
        )


def canonical_payload_bytes(bundle: AttestationBundle) -> bytes:
    """The bytes that are hashed: the bundle without its signature."""
    payload = bundle.model_dump(mode="json", exclude={"signature"})
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def bundle_sha256(bundle: AttestationBundle) -> str:
    """Hex SHA-256 of the canonical payload."""
    return hashlib.sha256(canonical_payload_bytes(bundle)).hexdigest()


def bundle_signing_bytes(sha256_hex: str) -> bytes:
    """What the issuer signs: the ASCII hex digest under the attestation-bundle
    signing domain. Takes the digest, not the bundle, so a holder of only the
    artifact's `{sha256, signature}` can rebuild it."""
    return domain_separated(
        SigningDomain.ATTESTATION_BUNDLE, sha256_hex.encode("ascii")
    )


def verify_bundle_signature(bundle: AttestationBundle, public_key_bytes: bytes) -> bool:
    """True when `bundle.signature` is the issuer's Ed25519 signature over
    `bundle_signing_bytes(bundle_sha256(bundle))`.

    `public_key_bytes` is the raw 32-byte key or a PEM public key. A signature
    that is not base64 or does not match returns False; a malformed key raises
    ValueError.
    """
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.hazmat.primitives.serialization import load_pem_public_key

    if public_key_bytes.lstrip().startswith(b"-----BEGIN"):
        key = load_pem_public_key(public_key_bytes)
        if not isinstance(key, Ed25519PublicKey):
            raise ValueError("public key is not an Ed25519 key")
    else:
        key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
    try:
        signature = base64.b64decode(bundle.signature, validate=True)
        key.verify(signature, bundle_signing_bytes(bundle_sha256(bundle)))
    except (binascii.Error, InvalidSignature):
        return False
    return True


def bundle_ref(bundle: AttestationBundle) -> AttestationBundleRef:
    """What a scan artifact records of the bundle it ran with."""
    return AttestationBundleRef(
        sha256=bundle_sha256(bundle),
        signature=bundle.signature,
        key_id=bundle.key_id,
        issued_at=bundle.issued_at,
        count=bundle.count,
    )
