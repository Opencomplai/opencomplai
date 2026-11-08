"""The attestation bundle: canonical bytes, hash, signature and the artifact ref.

The signature is Ed25519 over the ASCII hex SHA-256 of the canonical payload under
the attestation-bundle signing domain, so a party holding only the artifact's
`{sha256, signature}` can verify it, and the signature is good for nothing else.
"""

from __future__ import annotations

import base64
import hashlib
from datetime import date
from typing import Any

import jsonschema
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from opencomplai_core.attestation_bundle import (
    AttestationBundle,
    bundle_ref,
    bundle_sha256,
    bundle_signing_bytes,
    canonical_payload_bytes,
    verify_bundle_signature,
)
from opencomplai_core.json_schemas import build_attestation_bundle_schema
from opencomplai_core.models import Attestation
from opencomplai_core.signing import SigningDomain, domain_separated
from pydantic import ValidationError

ISSUED = "2026-11-03T09:30:00+00:00"


def _raw(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "schema_version": "attestation_bundle/v1",
        "system_id": "sys-1",
        "issued_at": ISSUED,
        "attestations": {
            "ISO_IEC_27001": {
                "ISO_IEC_27001:A.6.3": {
                    "statement": "Training runs yearly.",
                    "attested_by": "Jane Doe",
                    "attested_at": "2026-06-01",
                    "valid_until": "2027-06-01",
                    "record_id": "rec_1",
                    "evidence": [{"kind": "link", "ref": "https://wiki.example/t"}],
                }
            }
        },
        "excluded": {"SOC_2": {"SOC_2:CC1.1": "No office premises."}},
        "key_id": "dash-2026-11",
        "signature": "AAAA",
    }
    return {**base, **over}


def _sign(raw: dict[str, Any], key: Ed25519PrivateKey) -> AttestationBundle:
    """The issuer's side: hash the unsigned bundle, sign the hex, attach."""
    digest = bundle_sha256(AttestationBundle.model_validate(raw))
    signature = base64.b64encode(key.sign(bundle_signing_bytes(digest))).decode()
    return AttestationBundle.model_validate({**raw, "signature": signature})


@pytest.fixture
def key() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.generate()


def _raw_public(key: Ed25519PrivateKey) -> bytes:
    return key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )


def _pem_public(key: Ed25519PrivateKey) -> bytes:
    return key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )


# --- canonical bytes and hash -------------------------------------------------


def test_canonical_payload_is_sorted_compact_json_without_the_signature() -> None:
    assert canonical_payload_bytes(AttestationBundle.model_validate(_raw())) == (
        b'{"attestations":{"ISO_IEC_27001":{"ISO_IEC_27001:A.6.3":'
        b'{"attested_at":"2026-06-01","attested_by":"Jane Doe",'
        b'"evidence":[{"kind":"link","ref":"https://wiki.example/t"}],'
        b'"record_id":"rec_1","statement":"Training runs yearly.",'
        b'"valid_until":"2027-06-01"}}},'
        b'"excluded":{"SOC_2":{"SOC_2:CC1.1":"No office premises."}},'
        b'"issued_at":"2026-11-03T09:30:00+00:00","key_id":"dash-2026-11",'
        b'"schema_version":"attestation_bundle/v1","system_id":"sys-1"}'
    )


def test_sha256_is_the_hash_of_those_bytes() -> None:
    bundle = AttestationBundle.model_validate(_raw())
    assert (
        bundle_sha256(bundle)
        == hashlib.sha256(canonical_payload_bytes(bundle)).hexdigest()
    )


def test_the_signature_is_not_part_of_the_hash() -> None:
    a = AttestationBundle.model_validate(_raw(signature="AAAA"))
    b = AttestationBundle.model_validate(_raw(signature="BBBB"))
    assert bundle_sha256(a) == bundle_sha256(b)


def test_any_other_change_moves_the_hash() -> None:
    base = bundle_sha256(AttestationBundle.model_validate(_raw()))
    for over in (
        {"system_id": None},
        {"issued_at": "2026-11-03T09:31:00+00:00"},
        {"key_id": "other"},
        {"excluded": {}},
    ):
        assert bundle_sha256(AttestationBundle.model_validate(_raw(**over))) != base


def test_insertion_order_does_not_matter() -> None:
    raw = _raw(excluded={"SOC_2": {"SOC_2:CC1.1": "a", "SOC_2:CC1.2": "b"}})
    flipped = _raw(excluded={"SOC_2": {"SOC_2:CC1.2": "b", "SOC_2:CC1.1": "a"}})
    assert bundle_sha256(AttestationBundle.model_validate(raw)) == bundle_sha256(
        AttestationBundle.model_validate(flipped)
    )


def test_non_ascii_text_is_hashed_as_utf8_not_escaped() -> None:
    raw = _raw(excluded={"SOC_2": {"SOC_2:CC1.1": "Pas de locaux à Zürich"}})
    payload = canonical_payload_bytes(AttestationBundle.model_validate(raw))
    assert "Pas de locaux à Zürich".encode() in payload
    assert b"\\u" not in payload


def test_an_explicit_null_optional_hashes_like_an_omitted_one() -> None:
    row = _raw()["attestations"]["ISO_IEC_27001"]["ISO_IEC_27001:A.6.3"]
    explicit = dict(row, evidence=[], valid_until=None)
    plain = {k: v for k, v in row.items() if k not in ("evidence", "valid_until")}

    def bundle(att: dict[str, Any]) -> AttestationBundle:
        return AttestationBundle.model_validate(
            _raw(attestations={"ISO_IEC_27001": {"ISO_IEC_27001:A.6.3": att}})
        )

    assert bundle_sha256(bundle(explicit)) == bundle_sha256(bundle(plain))


# --- signature ----------------------------------------------------------------


def test_a_signature_over_the_hex_digest_verifies(key: Ed25519PrivateKey) -> None:
    bundle = _sign(_raw(), key)
    assert verify_bundle_signature(bundle, _raw_public(key)) is True
    assert verify_bundle_signature(bundle, _pem_public(key)) is True


def test_the_artifact_pair_alone_is_enough_to_verify(key: Ed25519PrivateKey) -> None:
    ref = bundle_ref(_sign(_raw(), key))
    key.public_key().verify(
        base64.b64decode(ref.signature),
        domain_separated(SigningDomain.ATTESTATION_BUNDLE, ref.sha256.encode("ascii")),
    )


def test_another_key_does_not_verify(key: Ed25519PrivateKey) -> None:
    bundle = _sign(_raw(), key)
    assert verify_bundle_signature(
        bundle, _raw_public(Ed25519PrivateKey.generate())
    ) is (False)


def test_a_tampered_bundle_does_not_verify(key: Ed25519PrivateKey) -> None:
    signed = _sign(_raw(), key)
    tampered = signed.model_copy(update={"system_id": "sys-2"})
    assert verify_bundle_signature(tampered, _raw_public(key)) is False


def test_a_signature_over_the_raw_bytes_instead_of_the_hex_does_not_verify(
    key: Ed25519PrivateKey,
) -> None:
    raw = _raw()
    payload = canonical_payload_bytes(AttestationBundle.model_validate(raw))
    signature = base64.b64encode(key.sign(payload)).decode()
    bundle = AttestationBundle.model_validate({**raw, "signature": signature})
    assert verify_bundle_signature(bundle, _raw_public(key)) is False


def test_a_signature_over_the_bare_hex_digest_does_not_verify(
    key: Ed25519PrivateKey,
) -> None:
    raw = _raw()
    digest = bundle_sha256(AttestationBundle.model_validate(raw))
    signature = base64.b64encode(key.sign(digest.encode("ascii"))).decode()
    bundle = AttestationBundle.model_validate({**raw, "signature": signature})
    assert verify_bundle_signature(bundle, _raw_public(key)) is False


def test_only_a_signature_made_for_the_bundle_domain_verifies(
    key: Ed25519PrivateKey,
) -> None:
    raw = _raw()
    digest = bundle_sha256(AttestationBundle.model_validate(raw)).encode("ascii")
    for domain in SigningDomain:
        signature = base64.b64encode(
            key.sign(domain_separated(domain, digest))
        ).decode()
        bundle = AttestationBundle.model_validate({**raw, "signature": signature})
        expected = domain is SigningDomain.ATTESTATION_BUNDLE
        assert verify_bundle_signature(bundle, _raw_public(key)) is expected


def test_a_signature_that_is_not_base64_is_false_not_an_error(
    key: Ed25519PrivateKey,
) -> None:
    bundle = AttestationBundle.model_validate(_raw(signature="AAAAA"))  # bad padding
    assert verify_bundle_signature(bundle, _raw_public(key)) is False


def test_a_malformed_public_key_raises(key: Ed25519PrivateKey) -> None:
    bundle = _sign(_raw(), key)
    with pytest.raises(ValueError, match="32 bytes"):
        verify_bundle_signature(bundle, b"too short")


# --- the artifact reference -----------------------------------------------------


def test_bundle_ref_copies_hash_and_signature_unchanged(key: Ed25519PrivateKey) -> None:
    bundle = _sign(_raw(), key)
    ref = bundle_ref(bundle)
    assert ref.sha256 == bundle_sha256(bundle)
    assert ref.signature == bundle.signature
    assert ref.key_id == "dash-2026-11"
    assert ref.issued_at == ISSUED
    assert ref.count == 2  # one attestation and one exclusion


# --- validation ---------------------------------------------------------------


def test_an_organisation_bundle_has_a_null_system_id() -> None:
    assert AttestationBundle.model_validate(_raw(system_id=None)).system_id is None


@pytest.mark.parametrize("field", ["system_id", "attestations", "excluded", "key_id"])
def test_every_top_level_field_is_required(field: str) -> None:
    raw = _raw()
    del raw[field]
    with pytest.raises(ValidationError):
        AttestationBundle.model_validate(raw)


@pytest.mark.parametrize(
    "over",
    [
        {"schema_version": "attestation_bundle/v2"},
        {"issued_at": "yesterday"},
        {"issued_at": "2026-11-03"},
        {"issued_at": "2026-13-45T00:00:00+00:00"},
        {"key_id": "has space"},
        {"signature": "not base64!"},
        {"excluded": {"SOC_2": {"SOC_2:CC1.1": "   "}}},
        {
            "attestations": {
                "ISO_IEC_27001": {
                    "ISO_IEC_27001:A.6.3": {
                        "statement": "s",
                        "attested_by": "jane@example.com",
                        "attested_at": "2026-06-01",
                        "record_id": "rec_1",
                    }
                }
            }
        },
        {"extra": 1},
        {
            "attestations": {
                "ISO_IEC_27001": {
                    "ISO_IEC_27001:A.6.3": {
                        "statement": "s",
                        "attested_by": "n",
                        "attested_at": "2026-06-01",
                    }
                }
            }
        },
    ],
)
def test_malformed_bundles_are_rejected(over: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        AttestationBundle.model_validate(_raw(**over))


# --- the published schema is as strict as the model ---------------------------

ROW_ID = "ISO_IEC_27001:A.6.3"
_GONE: Any = object()  # drop the key instead of setting it


def _with_att(**over: Any) -> dict[str, Any]:
    raw = _raw()
    att = raw["attestations"]["ISO_IEC_27001"][ROW_ID]
    for key, value in over.items():
        if value is _GONE:
            del att[key]
        else:
            att[key] = value
    return raw


def _with_justification(text: str) -> dict[str, Any]:
    return _raw(excluded={"SOC_2": {"SOC_2:CC1.1": text}})


def _links(count: int, ref: str = "https://wiki.example/t") -> list[dict[str, str]]:
    return [{"kind": "link", "ref": ref} for _ in range(count)]


_LIMIT_CASES = {
    "record_id missing": (_with_att(record_id=_GONE), False),
    "attested_by is an email": (_with_att(attested_by="jane@example.com"), False),
    "attested_by: 200 chars": (_with_att(attested_by="n" * 200), True),
    "attested_by: 201 chars": (_with_att(attested_by="n" * 201), False),
    "attested_at: a date": (_with_att(attested_at="2026-06-01"), True),
    "attested_at: a UTC timestamp": (
        _with_att(attested_at="2026-06-01T09:30:00Z"),
        True,
    ),
    "attested_at: a timestamp with an offset": (
        _with_att(attested_at="2026-06-01T09:30:00.250+02:00"),
        True,
    ),
    "attested_at: free text": (_with_att(attested_at="last spring"), False),
    "attested_at: 41 chars": (_with_att(attested_at="2026-06-01T" + "0" * 30), False),
    "evidence: 50 items": (_with_att(evidence=_links(50)), True),
    "evidence: 51 items": (_with_att(evidence=_links(51)), False),
    "evidence ref: 2048 chars": (_with_att(evidence=_links(1, "x" * 2048)), True),
    "evidence ref: 2049 chars": (_with_att(evidence=_links(1, "x" * 2049)), False),
    "statement: 4000 chars": (_with_att(statement="s" * 4000), True),
    "statement: 4001 chars": (_with_att(statement="s" * 4001), False),
    "justification: 2000 chars": (_with_justification("j" * 2000), True),
    "justification: 2001 chars": (_with_justification("j" * 2001), False),
    "justification: blank": (_with_justification("   "), False),
    "record_id has a space": (_with_att(record_id="has space"), False),
}


def _model_accepts(raw: dict[str, Any]) -> bool:
    try:
        AttestationBundle.model_validate(raw)
    except ValidationError:
        return False
    return True


def _schema_accepts(raw: dict[str, Any]) -> bool:
    try:
        jsonschema.validate(raw, build_attestation_bundle_schema())
    except jsonschema.ValidationError:
        return False
    return True


@pytest.mark.parametrize("case", _LIMIT_CASES)
def test_schema_and_model_agree_on_every_limit(case: str) -> None:
    raw, accepted = _LIMIT_CASES[case]
    assert _model_accepts(raw) is accepted
    assert _schema_accepts(raw) is accepted


def test_the_base_bundle_passes_both() -> None:
    assert _model_accepts(_raw())
    assert _schema_accepts(_raw())


def test_the_manifest_attestation_keeps_its_looser_limits() -> None:
    long_form = {
        "statement": "s" * 5000,
        "attested_by": "jane@example.com",
        "attested_at": "2026-06-01",
        "evidence": _links(51, "x" * 3000),
    }
    assert Attestation.model_validate(long_form).record_id is None


def test_a_bundle_record_converts_to_the_manifest_attestation() -> None:
    bundle = AttestationBundle.model_validate(_raw())
    record = bundle.attestations["ISO_IEC_27001"][ROW_ID]
    attestation = record.to_attestation()
    assert attestation.record_id == "rec_1"
    assert attestation.valid_until == date(2027, 6, 1)
    assert attestation.model_dump(mode="json") == record.model_dump(mode="json")
