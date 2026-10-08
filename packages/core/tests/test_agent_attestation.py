"""agent_attestation/v1: signing, offline verification, pinned schema, golden vectors.

The committed vectors in fixtures/agent_attestation_vectors.json are the parity
contract for the dashboard's TypeScript verifier (SU-33b): it reads the same
file, including `key_id_vectors`. Regenerate, never hand-edit:
    OPENCOMPLAI_UPDATE_GOLDEN=1 pytest packages/core/tests/test_agent_attestation.py -k vectors
"""

from __future__ import annotations

import base64
import copy
import json
import os
import socket
from datetime import UTC, datetime
from pathlib import Path

import jsonschema
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from opencomplai_core import agent_attestation as aa
from opencomplai_core.agent_attestation import (
    ATTESTATION_SCHEMA_PATH,
    AgentAttestation,
    key_id_for_public_pem,
    mandate_sha256,
    public_pem_for_private_pem,
    sign_attestation,
    signing_payload,
    verify_attestation,
)
from opencomplai_core.agent_inventory import AgentMandate
from opencomplai_core.signing import (
    SigningDomain,
    canonical_json_bytes,
    domain_separated,
    generate_keypair,
)

VECTORS_PATH = Path(__file__).parent / "fixtures" / "agent_attestation_vectors.json"
NOW = datetime(2026, 6, 1, tzinfo=UTC)
ISSUED, EXPIRES = "2026-01-01T00:00:00Z", "2099-01-01T00:00:00Z"
MANDATE = {
    "permitted_actions": ["tool:search"],
    "prohibited_actions": [],
    "limits": {"max": 3},
}
OTHER_HASH = "sha256:" + "ab" * 32


def _priv_pem(seed: bytes) -> bytes:
    return Ed25519PrivateKey.from_private_bytes(seed).private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )


PRIV = _priv_pem(bytes(range(32)))
PUB = public_pem_for_private_pem(PRIV)
OTHER_PRIV = _priv_pem(bytes([7]) * 32)
OTHER_PUB = public_pem_for_private_pem(OTHER_PRIV)


def _sign(**over) -> dict:
    kw = {
        "agent_id": "agent-1",
        "system_id": "sys-1",
        "mandate_sha256": mandate_sha256(MANDATE),
        "issuer": "Example Issuer",
        "issued_at": ISSUED,
        "expires_at": EXPIRES,
        "private_pem": PRIV,
    }
    kw.update(over)
    return sign_attestation(**kw)


def _status(data, pub=PUB, now=NOW, expect=None):
    r = verify_attestation(data, pub, now=now, expect_mandate_sha256=expect)
    return r.status, r.code


def test_sign_verify_round_trip():
    assert _status(_sign()) == ("verified", None)


def test_expired_fails():
    assert _status(_sign(), now=datetime(2100, 1, 1, tzinfo=UTC)) == (
        "invalid",
        "expired",
    )


def test_exactly_at_expiry_fails():
    assert _status(_sign(), now=datetime(2099, 1, 1, tzinfo=UTC)) == (
        "invalid",
        "expired",
    )


def test_not_yet_valid_fails():
    assert _status(_sign(), now=datetime(2025, 1, 1, tzinfo=UTC)) == (
        "invalid",
        "not_yet_valid",
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("agent_id", "agent-2"),
        ("system_id", "sys-2"),
        ("issuer", "Someone Else"),
        ("mandate_sha256", OTHER_HASH),
        ("issued_at", "2025-12-31T00:00:00Z"),
        ("expires_at", "2100-01-01T00:00:00Z"),
    ],
)
def test_tampered_field_fails_signature(field, value):
    data = _sign()
    data[field] = value
    assert _status(data) == ("invalid", "signature")


def test_unsigned_is_distinct_from_tampered():
    data = _sign()
    data["signature"] = None
    assert _status(data) == ("unsigned", None)


def test_wrong_domain_signature_fails():
    data = _sign()
    att = AgentAttestation.model_validate(data)
    body = canonical_json_bytes(att.model_dump(exclude={"signature"}))
    key = serialization.load_pem_private_key(PRIV, password=None)
    sig = key.sign(domain_separated(SigningDomain.AGENT_LOG, body))
    data["signature"] = base64.b64encode(sig).decode()
    assert _status(data) == ("invalid", "signature")


def test_wrong_key_fails():
    assert _status(_sign(), pub=OTHER_PUB) == ("invalid", "key_id")


def test_key_id_mismatch_fails():
    data = _sign()
    data["key_id"] = "sha256:" + "0" * 16
    assert _status(data) == ("invalid", "key_id")


def test_mandate_mismatch_fails():
    assert _status(_sign(), expect=OTHER_HASH) == ("invalid", "mandate_mismatch")
    assert _status(_sign(), expect=mandate_sha256(MANDATE)) == ("verified", None)


def test_mandate_not_checked_when_not_requested():
    data = _sign(mandate_sha256=OTHER_HASH)
    assert _status(data) == ("verified", None)


def test_mandate_sha256_stable_and_sensitive():
    base = mandate_sha256(MANDATE)
    assert base == mandate_sha256(copy.deepcopy(MANDATE))
    more = {
        **MANDATE,
        "permitted_actions": [*MANDATE["permitted_actions"], "tool:write"],
    }
    assert mandate_sha256(more) != base
    m = AgentMandate(permitted_actions=["tool:search"], limits={"max": 3})
    # prohibited_actions is [] (not None) in both; None-valued optional fields are dropped.
    assert mandate_sha256(m) == base


def test_extra_field_rejected():
    data = _sign()
    data["extra"] = 1
    assert _status(data) == ("invalid", "schema")


def test_non_ascii_issuer_rejected():
    with pytest.raises(ValueError, match=r"String should|after issued_at|timezone"):
        _sign(issuer="Zoë")


def test_expiry_not_after_issue_rejected():
    with pytest.raises(ValueError, match=r"String should|after issued_at|timezone"):
        _sign(expires_at=ISSUED)
    data = _sign()
    data["expires_at"] = "2025-01-01T00:00:00Z"
    assert _status(data) == ("invalid", "schema")


def test_impossible_date_is_schema_failure():
    data = _sign()
    data["expires_at"] = "2099-13-45T00:00:00Z"
    assert _status(data) == ("invalid", "schema")


def test_naive_now_raises():
    with pytest.raises(ValueError, match=r"String should|after issued_at|timezone"):
        verify_attestation(_sign(), PUB, now=datetime(2026, 6, 1))


def test_verify_makes_no_network_calls(monkeypatch):
    def boom(*_a, **_k):
        raise AssertionError("verification must be offline")

    data = _sign()
    monkeypatch.setattr(socket, "socket", boom)
    assert _status(data) == ("verified", None)


def _schema() -> dict:
    return json.loads(ATTESTATION_SCHEMA_PATH.read_text(encoding="utf-8"))


def test_schema_file_matches_model():
    expected = (
        json.dumps(AgentAttestation.model_json_schema(), indent=2, sort_keys=True)
        + "\n"
    )
    assert ATTESTATION_SCHEMA_PATH.read_text(encoding="utf-8") == expected


def test_schema_validates_signed_sample():
    jsonschema.validate(_sign(), _schema())


def test_schema_rejects_unknown_field():
    data = _sign()
    data["extra"] = 1
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(data, _schema())


def test_module_never_reads_the_clock():
    src = Path(aa.__file__).read_text(encoding="utf-8")
    assert "datetime.now" not in src
    assert "time.time" not in src


def test_key_id_matches_cli_enrolled_pem(tmp_path):
    generate_keypair(tmp_path)
    enrolled = (tmp_path / "signing.pub").read_text().strip()
    data = sign_attestation(
        agent_id="a",
        system_id="s",
        mandate_sha256=OTHER_HASH,
        issuer="i",
        issued_at=ISSUED,
        expires_at=EXPIRES,
        private_pem=(tmp_path / "signing.key").read_bytes(),
    )
    assert data["key_id"] == key_id_for_public_pem(enrolled)
    assert _status(data, pub=(tmp_path / "signing.pub").read_bytes()) == (
        "verified",
        None,
    )


# ---- golden vectors ---------------------------------------------------------


def _payload_bytes(att: dict) -> bytes:
    return canonical_json_bytes({k: v for k, v in att.items() if k != "signature"})


def build_vectors() -> dict:
    good = _sign()
    mandate_hash = good["mandate_sha256"]
    wrong_domain = copy.deepcopy(good)
    key = serialization.load_pem_private_key(PRIV, password=None)
    wrong_domain["signature"] = base64.b64encode(
        key.sign(domain_separated(SigningDomain.AGENT_LOG, _payload_bytes(good)))
    ).decode()
    cases = [
        ("valid", good, None, "verified", None),
        ("valid_with_matching_mandate", good, mandate_hash, "verified", None),
        (
            "tampered_agent_id",
            {**good, "agent_id": "agent-2"},
            None,
            "invalid",
            "signature",
        ),
        (
            "tampered_expiry_extended",
            {**good, "expires_at": "2100-01-01T00:00:00Z"},
            None,
            "invalid",
            "signature",
        ),
        ("wrong_domain_signature", wrong_domain, None, "invalid", "signature"),
        (
            "expired",
            _sign(expires_at="2026-03-01T00:00:00Z"),
            None,
            "invalid",
            "expired",
        ),
        (
            "not_yet_valid",
            _sign(issued_at="2027-01-01T00:00:00Z", expires_at="2028-01-01T00:00:00Z"),
            None,
            "invalid",
            "not_yet_valid",
        ),
        ("mandate_mismatch", good, OTHER_HASH, "invalid", "mandate_mismatch"),
        (
            "wrong_key_id",
            {**good, "key_id": "sha256:" + "0" * 16},
            None,
            "invalid",
            "key_id",
        ),
        ("unsigned", {**good, "signature": None}, None, "unsigned", None),
    ]
    pem = PUB.decode()
    raw = (
        Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
        .public_key()
        .public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    )
    return {
        "format": "agent_attestation_vectors/v1",
        "public_key_pem": pem,
        "public_key_raw_hex": raw.hex(),
        "key_id": key_id_for_public_pem(PUB),
        "domain_prefix_utf8": "opencomplai.sig.v1",
        "domain": SigningDomain.ATTESTATION.value,
        "vectors": [
            {
                "name": name,
                "attestation": att,
                "now": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "expect_mandate_sha256": expect,
                "canonical_payload": _payload_bytes(att).decode("ascii"),
                "message_hex": domain_separated(
                    SigningDomain.ATTESTATION, _payload_bytes(att)
                ).hex(),
                "expected_status": status,
                "expected_code": code,
            }
            for name, att, expect, status, code in cases
        ],
        "key_id_vectors": [
            {"pem_text": text, "key_id": key_id_for_public_pem(text)}
            for text in (
                pem.strip(),
                pem.strip() + "\n",
                pem.strip() + "\r\n",
                "  " + pem.strip() + "  ",
                OTHER_PUB.decode(),
            )
        ],
    }


def _committed() -> dict:
    return json.loads(VECTORS_PATH.read_text(encoding="utf-8"))


def test_vectors_regenerate_identically():
    fresh = (json.dumps(build_vectors(), indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )
    if os.environ.get("OPENCOMPLAI_UPDATE_GOLDEN") == "1":
        VECTORS_PATH.write_bytes(fresh)
    assert VECTORS_PATH.read_bytes() == fresh, (
        "vectors out of date: run OPENCOMPLAI_UPDATE_GOLDEN=1 pytest "
        "packages/core/tests/test_agent_attestation.py -k vectors"
    )


def test_committed_vectors_match_python_verifier():
    v = _committed()
    pub = v["public_key_pem"].encode()
    assert len(v["vectors"]) == 10
    for vec in v["vectors"]:
        now = datetime.strptime(vec["now"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
        got = verify_attestation(
            vec["attestation"],
            pub,
            now=now,
            expect_mandate_sha256=vec["expect_mandate_sha256"],
        )
        assert (got.status, got.code) == (
            vec["expected_status"],
            vec["expected_code"],
        ), vec["name"]
        att = AgentAttestation.model_validate(vec["attestation"])
        assert signing_payload(att).hex() == vec["message_hex"], vec["name"]


def test_key_id_golden_vectors():
    ids = _committed()["key_id_vectors"]
    assert len({i["key_id"] for i in ids}) == 2
    for item in ids:
        assert key_id_for_public_pem(item["pem_text"]) == item["key_id"]
