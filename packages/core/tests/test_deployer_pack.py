"""SU-21b: build and verify a deployer pack (hash, signature, domain, completeness)."""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path

import opencomplai_core.deployer_pack as dp
import pytest
from opencomplai_core.deployer_pack import build_pack, verify_pack
from opencomplai_core.signing import (
    SigningDomain,
    canonical_json_bytes,
    generate_keypair,
    sign_bundle_bytes,
)

CONTENT = {
    "system_id": "sys-1",
    "points": [
        {"point": "a", "populated": True, "content": "Acme"},
        {"point": "b_iv", "populated": False, "content": "Not captured"},
        {"point": "b_v", "populated": False, "content": "Not captured"},
    ],
}


@pytest.fixture(autouse=True)
def _no_env_key(monkeypatch):
    monkeypatch.delenv("SIGNING_KEY_PRIVATE", raising=False)


@pytest.fixture
def keys(tmp_path: Path) -> tuple[Path, Path]:
    generate_keypair(tmp_path / "k1")
    return tmp_path / "k1" / "signing.key", tmp_path / "k1" / "signing.pub"


def _pack(key: Path | None = None) -> dict:
    return build_pack(
        copy.deepcopy(CONTENT),
        system_id="sys-1",
        issued_on="2026-10-07",
        generator_version="9.9.9",
        private_key_path=key,
    ).model_dump(mode="json")


def _body_bytes(pack: dict) -> bytes:
    return canonical_json_bytes({k: v for k, v in pack.items() if k != "integrity"})


def test_build_is_deterministic_for_same_inputs(keys):
    assert _pack() == _pack()
    assert _pack(keys[0]) == _pack(keys[0])  # Ed25519 signing is deterministic


def test_pack_sha256_excludes_integrity_block():
    pack = _pack()
    expected = hashlib.sha256(_body_bytes(pack)).hexdigest()
    assert pack["integrity"]["pack_sha256"] == expected


def test_signed_pack_verifies_with_public_key(keys):
    result = verify_pack(_pack(keys[0]), keys[1])
    assert (result.status, result.detail) == ("verified", "hash and signature match")


def test_tampered_content_fails_hash(keys):
    pack = _pack(keys[0])
    pack["content"]["points"][0]["content"] = "Evil Corp"
    result = verify_pack(pack, keys[1])
    assert (result.status, result.detail) == ("invalid", "content hash mismatch")


def test_resigned_hash_without_signature_fails(keys):
    pack = _pack(keys[0])
    pack["content"]["points"][0]["content"] = "Evil Corp"
    pack["integrity"]["pack_sha256"] = hashlib.sha256(_body_bytes(pack)).hexdigest()
    result = verify_pack(pack, keys[1])  # old signature kept
    assert (result.status, result.detail) == ("invalid", "signature does not match")


def test_wrong_key_fails_signature(keys, tmp_path):
    other = tmp_path / "k2"
    generate_keypair(other)
    assert verify_pack(_pack(keys[0]), other / "signing.pub").status == "invalid"


def test_signature_is_bound_to_deployer_pack_domain(keys):
    pack = _pack(keys[0])
    pack["integrity"]["signature"] = sign_bundle_bytes(
        _body_bytes(pack), keys[0], SigningDomain.DOSSIER_BUNDLE
    )
    assert verify_pack(pack, keys[1]).status == "invalid"


def test_unsigned_pack_reports_unsigned_not_verified(keys):
    assert verify_pack(_pack(), keys[1]).status == "unsigned"
    assert verify_pack(_pack(), None).status == "unsigned"


def test_signer_key_id_is_fingerprint_of_public_key(keys):
    pack = _pack(keys[0])
    assert (
        pack["integrity"]["signer_key_id"]
        == hashlib.sha256(keys[1].read_bytes()).hexdigest()[:16]
    )
    assert _pack()["integrity"]["signer_key_id"] is None


def test_completeness_lists_every_not_captured_item():
    assert _pack()["completeness"] == {
        "items_total": 3,
        "items_provided": 1,
        "items_not_captured": 2,
        "not_captured_items": ["b_iv", "b_v"],
    }


def test_build_pack_rejects_content_without_points():
    for bad in ({"x": 1}, {"points": "no"}, {"points": [{"point": "a"}]}):
        with pytest.raises(ValueError, match="instructions-for-use"):
            build_pack(
                bad, system_id="s", issued_on="2026-10-07", generator_version="1"
            )


def test_deployer_pack_module_never_reads_the_clock():
    source = Path(dp.__file__).read_text(encoding="utf-8")
    for banned in ("datetime.now", "time.time", "uuid", "date.today"):
        assert banned not in source
