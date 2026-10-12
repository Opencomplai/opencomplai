"""CL-A3: a provider's deployer pack as upstream `imported_evidence`."""

from __future__ import annotations

import pytest
from opencomplai_core.deployer_pack import build_pack, upstream_evidence
from opencomplai_core.models import (
    ImportedFieldEvidence,
    ImportedPackEvidence,
    SystemManifest,
)
from opencomplai_core.signing import generate_keypair
from pydantic import ValidationError

CONTENT = {"points": [{"point": "purpose", "populated": True}]}


def _pack(tmp_path, *, signed: bool):
    key = None
    if signed:
        generate_keypair(tmp_path / "keys")
        key = tmp_path / "keys" / "signing.key"
    return build_pack(
        CONTENT,
        system_id="provider-sys",
        issued_on="2026-10-07",
        generator_version="1",
        private_key_path=key,
    )


def _manifest(**extra) -> dict:
    return {"system_id": "dep-1", "intended_purpose": "x", "commit_ref": "abc", **extra}


def test_manifest_without_evidence_serialises_unchanged():
    manifest = SystemManifest.model_validate(_manifest())
    assert manifest.imported_evidence == {}
    assert "imported_evidence" not in manifest.model_dump_json(indent=2)


def test_model_card_evidence_still_loads():
    entry = {
        "source": "model_card",
        "status": "attested",
        "source_file": "card.md",
        "card_sha256": "a" * 64,
        "imported_on": "2026-10-07",
    }
    manifest = SystemManifest.model_validate(
        _manifest(imported_evidence={"model_architecture": entry})
    )
    assert isinstance(
        manifest.imported_evidence["model_architecture"], ImportedFieldEvidence
    )


def test_pack_evidence_round_trips(tmp_path):
    key, entry = upstream_evidence(
        _pack(tmp_path, signed=True),
        "verified",
        source_file="p.json",
        imported_on="2026-10-07",
    )
    dumped = entry.model_dump(mode="json")
    manifest = SystemManifest.model_validate(_manifest(imported_evidence={key: dumped}))
    got = manifest.imported_evidence[key]
    assert isinstance(got, ImportedPackEvidence)
    assert got == entry
    assert got.model_dump(mode="json") == dumped


def test_pack_evidence_rejects_unknown_key_and_bad_hash(tmp_path):
    _, entry = upstream_evidence(
        _pack(tmp_path, signed=False),
        "unsigned",
        source_file="p.json",
        imported_on="2026-10-07",
    )
    good = entry.model_dump(mode="json")
    with pytest.raises(ValidationError):
        ImportedPackEvidence.model_validate({**good, "extra": 1})
    with pytest.raises(ValidationError):
        ImportedPackEvidence.model_validate({**good, "pack_sha256": "a" * 63})


def test_upstream_evidence_verified_carries_signer(tmp_path):
    pack = _pack(tmp_path, signed=True)
    _, entry = upstream_evidence(
        pack, "verified", source_file="p.json", imported_on="2026-10-07"
    )
    assert entry.verification == "verified"
    assert entry.signer_key_id == pack.integrity.signer_key_id
    assert entry.signer_key_id is not None
    assert entry.provider_system_id == "provider-sys"
    assert entry.pack_sha256 == pack.integrity.pack_sha256


def test_upstream_evidence_unsigned_has_no_signer(tmp_path):
    pack = _pack(tmp_path, signed=False)
    _, entry = upstream_evidence(
        pack, "unsigned", source_file="p.json", imported_on="2026-10-07"
    )
    assert entry.verification == "unsigned"
    assert entry.signer_key_id is None


def test_upstream_evidence_rejects_invalid_status(tmp_path):
    pack = _pack(tmp_path, signed=False)
    with pytest.raises(ValueError, match="verified' or 'unsigned"):
        upstream_evidence(
            pack, "invalid", source_file="p.json", imported_on="2026-10-07"
        )


def test_upstream_evidence_key_is_twelve_hex_pack_id(tmp_path):
    pack = _pack(tmp_path, signed=False)
    key, entry = upstream_evidence(
        pack, "unsigned", source_file="a/b\\p.json", imported_on="2026-10-07"
    )
    assert key == f"deployer_pack:{pack.integrity.pack_sha256[:12]}"
    assert len(key.split(":")[1]) == 12
    assert entry.source_file == "p.json"
