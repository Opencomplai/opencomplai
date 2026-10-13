"""Signing the neutral evidence package: sign, verify, domain separation, CSV."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import jsonschema
import opencomplai_core
import pytest
from opencomplai_core.evidence_package import (
    SIGNED_NOTE,
    EvidencePackage,
    build_evidence_package,
    package_signing_bytes,
    package_to_csv,
    package_to_json,
    sign_package,
    verify_package,
)
from opencomplai_core.models import (
    ArticleGapSource,
    ArticleGapStatus,
    GapReport,
    GapStatus,
    ScanResult,
    ScanStatusArtifact,
)
from opencomplai_core.signing import (
    SigningDomain,
    generate_keypair,
    sign_bundle_bytes,
)

_SCHEMA = (
    Path(opencomplai_core.__file__).parent / "data" / "evidence_package.schema.json"
)


@pytest.fixture(autouse=True)
def _no_env_key(monkeypatch):
    monkeypatch.delenv("SIGNING_KEY_PRIVATE", raising=False)


def _raw(**over: object) -> dict:
    art = ScanStatusArtifact(
        install_id="i",
        system_id="sys-1",
        commit_ref="abc1234",
        result=ScanResult.CONTROL_FAIL,
        failed_controls=["C-1"],
        evidence_hashes=["a" * 64],
        rationale_hash="0" * 64,
        duration_ms=5,
        rule_set_version="2026.10",
        cli_version="0.9.1",
        gap_report=GapReport(
            system_id="sys-1",
            commit_ref="abc1234",
            generated_at="2026-10-06T00:00:00+00:00",
            articles=[
                ArticleGapStatus(
                    article="Art. 9",
                    status=GapStatus.MISSING,
                    source=ArticleGapSource.RULE,
                    evidence_ref="R-9",
                    confidence=0.4,
                )
            ],
        ),
    )
    return {**json.loads(art.model_dump_json()), **over}


def _keys(tmp_path: Path, name: str) -> tuple[Path, Path]:
    d = tmp_path / name
    generate_keypair(d)
    return d / "signing.key", d / "signing.pub"


def _signed(tmp_path: Path) -> tuple[EvidencePackage, dict, Path]:
    key, pub = _keys(tmp_path, "keys")
    pkg = sign_package(build_evidence_package(_raw()), key)
    # What a receiver sees: the values read back from the written file.
    return pkg, json.loads(package_to_json(pkg)), pub


def test_sign_then_verify_package(tmp_path):
    pkg, raw, pub = _signed(tmp_path)
    assert pkg.package_signature is not None
    assert pkg.package_signature.domain == "evidence-package"
    assert pkg.verification.note == SIGNED_NOTE
    assert verify_package(raw, pub) == ("verified", "signature matches")


def test_other_domain_and_other_key_do_not_verify(tmp_path):
    key, pub = _keys(tmp_path, "keys")
    other_key, _ = _keys(tmp_path, "other")
    pkg = sign_package(build_evidence_package(_raw()), key)
    raw = json.loads(package_to_json(pkg))
    bytes_ = package_signing_bytes(raw)

    wrong_domain = dict(raw)
    wrong_domain["package_signature"] = {
        **raw["package_signature"],
        "signature": sign_bundle_bytes(bytes_, key, SigningDomain.ARTIFACT),
    }
    assert verify_package(wrong_domain, pub) == (
        "invalid",
        "signature does not match",
    )

    # Same claimed signer id, signature made by a different key.
    wrong_key = dict(raw)
    wrong_key["package_signature"] = {
        **raw["package_signature"],
        "signature": sign_bundle_bytes(
            bytes_, other_key, SigningDomain.EVIDENCE_PACKAGE
        ),
    }
    assert verify_package(wrong_key, pub)[0] == "invalid"


def test_unsigned_package_is_unsigned_not_invalid(tmp_path):
    _, pub = _keys(tmp_path, "keys")
    raw = json.loads(package_to_json(build_evidence_package(_raw())))
    assert "package_signature" not in raw
    assert verify_package(raw, pub)[0] == "unsigned"
    raw["package_signature"] = None
    assert verify_package(raw, pub)[0] == "unsigned"


def test_signer_key_id_mismatch_is_invalid(tmp_path):
    _, raw, _ = _signed(tmp_path)
    _, other_pub = _keys(tmp_path, "other")
    assert verify_package(raw, other_pub) == (
        "invalid",
        "signer_key_id does not match public key",
    )


def test_malformed_signature_is_invalid(tmp_path):
    _, raw, pub = _signed(tmp_path)
    raw["package_signature"]["signature"] = "not base64 !!"
    assert verify_package(raw, pub) == (
        "invalid",
        "malformed signature or public key",
    )


def test_signed_package_validates_against_schema(tmp_path):
    _, raw, _ = _signed(tmp_path)
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    jsonschema.validate(raw, schema)
    assert raw["package_signature"]["algorithm"] == "ed25519"
    # Still closed: an unknown key inside the signature is rejected.
    raw["package_signature"]["extra"] = 1
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(raw, schema)
    # Unsigned packages validate too, with no package_signature key.
    plain = json.loads(package_to_json(build_evidence_package(_raw())))
    jsonschema.validate(plain, schema)
    assert "package_signature" not in plain


def test_csv_header_is_pinned_exactly():
    rows = list(csv.reader(io.StringIO(package_to_csv(build_evidence_package(_raw())))))
    assert rows[0] == [
        "system_id",
        "commit_ref",
        "rule_set_version",
        "article",
        "status",
        "source",
        "evidence_ref",
        "confidence",
        "confidence_label",
        "tree_sha256",
        "tree_dirty",
        "signed",
        "verdict",
    ]


def test_csv_bool_and_null_cells():
    absent = build_evidence_package(_raw())
    row = list(csv.reader(io.StringIO(package_to_csv(absent))))[1]
    assert row[9:] == ["", "", "false", "control_fail"]

    present = build_evidence_package(
        _raw(tree_sha256="c" * 64, tree_dirty=False, signature="c2ln")
    )
    row = list(csv.reader(io.StringIO(package_to_csv(present))))[1]
    assert row[9:] == ["c" * 64, "false", "true", "control_fail"]
    dirty = build_evidence_package(_raw(tree_sha256="c" * 64, tree_dirty=True))
    assert list(csv.reader(io.StringIO(package_to_csv(dirty))))[1][10] == "true"
