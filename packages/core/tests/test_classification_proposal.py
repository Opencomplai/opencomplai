"""A classification proposal file and its signed confirmation record."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from opencomplai_core.acceptance import (
    ART6_CONTROL,
    ART_6_3_EXEMPTION,
    CLASSIFICATION_ACCEPTANCE,
    PROPOSAL_CONFIRMATION,
    TRAP_APPROVAL,
    apply_acceptance,
    build_record,
    evaluate_record,
    public_key_pem_from_private,
    sign_record,
)
from opencomplai_core.classification_proposal import (
    PROPOSAL_DOCUMENT_TYPE,
    PROPOSAL_FILENAME,
    TOOL_WRITTEN_NAMES,
    build_proposal_document,
    confirmation_status,
    is_tool_written_path,
    load_proposal,
    proposal_digest,
    proposal_tree_sha256,
)
from opencomplai_core.control_identity import fingerprint_manifest
from opencomplai_core.models import ScanResult, ScanStatusArtifact, SystemManifest
from opencomplai_core.signing import generate_keypair

AT = "2026-10-12T10:00:00Z"
DIGEST = "sha256:" + "ab" * 32


def _manifest(purpose: str = "Automated resume screening") -> SystemManifest:
    return SystemManifest(system_id="sys-1", intended_purpose=purpose)


def _key(tmp_path: Path) -> Path:
    generate_keypair(tmp_path / "k")
    return tmp_path / "k" / "signing.key"


def _doc(manifest: SystemManifest, area: str = "Employment") -> dict:
    return build_proposal_document(
        system_id=manifest.system_id,
        commit_ref="HEAD",
        scanner_version="0.0.0",
        scan_input_digest=DIGEST,
        scan_report_hash="sha256:" + "cd" * 32,
        manifest_fingerprint=fingerprint_manifest(manifest),
        declared_purpose=manifest.intended_purpose,
        area=area,
        confidence="medium",
        evidence=[{"location": "a.py:3", "file": "a.py", "line": 3}],
        minority_evidence=[],
        prohibited_signals=[],
        proposal={"proposed_annex_iii_area": 4, "proposed_area_name": area},
    )


def _write_proposal(tmp_path: Path, doc: dict) -> Path:
    path = tmp_path / PROPOSAL_FILENAME
    path.write_text(json.dumps(doc, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _confirm(tmp_path: Path, manifest: SystemManifest, doc: dict) -> Path:
    key = _key(tmp_path)
    record = sign_record(
        build_record(
            record_type=PROPOSAL_CONFIRMATION,
            system_id=manifest.system_id,
            manifest_fingerprint=fingerprint_manifest(manifest),
            accepted_by="dpo@example.test",
            statement="Confirmed.",
            accepted_at=AT,
            public_key_pem=public_key_pem_from_private(key.read_bytes()),
            proposal_sha256=doc["proposal_sha256"],
            confirmed_area=doc["area"],
        ),
        key,
    )
    path = tmp_path / "record.json"
    path.write_text(json.dumps(record), encoding="utf-8")
    return path


def test_document_carries_scan_digest_and_self_digest() -> None:
    doc = _doc(_manifest())
    assert doc["status"] == "unconfirmed"
    assert doc["document_type"] == PROPOSAL_DOCUMENT_TYPE
    assert doc["scan_input_digest"] == DIGEST
    assert doc["proposal_sha256"] == proposal_digest(doc)
    assert doc["proposal_sha256"].startswith("sha256:")
    assert list(doc)[-1] == "proposal_sha256"
    assert "not a legal determination" in doc["notice"].lower()


def test_load_rejects_edited_proposal(tmp_path: Path) -> None:
    doc = _doc(_manifest())
    path = _write_proposal(tmp_path, doc)
    assert load_proposal(path) == doc
    path.write_text(
        json.dumps({**doc, "area": "Biometrics"}, sort_keys=True), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="edited"):
        load_proposal(path)
    path.write_text(json.dumps([1, 2]), encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        load_proposal(path)
    path.write_text(
        json.dumps({**doc, "document_type": "other"}, sort_keys=True), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="document_type"):
        load_proposal(path)


def test_confirmation_valid_when_proposal_unchanged(tmp_path: Path) -> None:
    manifest = _manifest()
    doc = _doc(manifest)
    proposal = _write_proposal(tmp_path, doc)
    record = _confirm(tmp_path, manifest, doc)
    status = confirmation_status(proposal, record, manifest)
    assert status.state == "valid"
    assert status.record["proposal_sha256"] == doc["proposal_sha256"]
    assert status.record["confirmed_area"] == "Employment"


def test_edited_proposal_after_confirmation_is_proposal_changed(
    tmp_path: Path,
) -> None:
    manifest = _manifest()
    doc = _doc(manifest)
    proposal = _write_proposal(tmp_path, doc)
    record = _confirm(tmp_path, manifest, doc)

    # Edited without re-hashing: the file no longer verifies.
    proposal.write_text(
        json.dumps({**doc, "area": "Biometrics"}, sort_keys=True), encoding="utf-8"
    )
    assert confirmation_status(proposal, record, manifest).state == "proposal_changed"

    # Re-hashed to look consistent: it is a different proposal than the one confirmed.
    other = _doc(manifest, area="Biometrics")
    _write_proposal(tmp_path, other)
    assert confirmation_status(proposal, record, manifest).state == "proposal_changed"

    proposal.unlink()
    assert confirmation_status(proposal, record, manifest).state == "proposal_changed"


def test_confirmation_stale_when_manifest_edited(tmp_path: Path) -> None:
    manifest = _manifest()
    doc = _doc(manifest)
    proposal = _write_proposal(tmp_path, doc)
    record = _confirm(tmp_path, manifest, doc)
    edited = _manifest("Something else entirely")
    assert confirmation_status(proposal, record, edited).state == "stale"


def test_confirmation_record_is_inert_for_apply_acceptance(tmp_path: Path) -> None:
    manifest = _manifest()
    record = _confirm(tmp_path, manifest, _doc(manifest))
    status = evaluate_record(record, manifest, PROPOSAL_CONFIRMATION)
    assert status.state == "valid"
    artifact = ScanStatusArtifact(
        install_id="i",
        system_id="sys-1",
        commit_ref="abc",
        result=ScanResult.CONTROL_FAIL,
        failed_controls=[ART6_CONTROL],
        rationale_hash="sha256:00",
        duration_ms=1,
    )
    assert apply_acceptance(artifact, status) is artifact


def test_existing_records_unchanged_without_new_fields(tmp_path: Path) -> None:
    pem = public_key_pem_from_private(_key(tmp_path).read_bytes())
    for record_type in (CLASSIFICATION_ACCEPTANCE, TRAP_APPROVAL):
        record = build_record(
            record_type=record_type,
            system_id="sys-1",
            manifest_fingerprint="fp",
            accepted_by="a",
            statement="s",
            accepted_at=AT,
            public_key_pem=pem,
            change_context="ctx" if record_type == TRAP_APPROVAL else None,
        )
        assert "proposal_sha256" not in record
        assert "confirmed_area" not in record


def test_proposal_fields_only_on_proposal_confirmation(tmp_path: Path) -> None:
    pem = public_key_pem_from_private(_key(tmp_path).read_bytes())
    base = {
        "system_id": "sys-1",
        "manifest_fingerprint": "fp",
        "accepted_by": "a",
        "statement": "s",
        "accepted_at": AT,
        "public_key_pem": pem,
    }
    extra = {
        CLASSIFICATION_ACCEPTANCE: {},
        ART_6_3_EXEMPTION: {"grounds": ["hr3_art_6_3"]},
    }
    for record_type, more in extra.items():
        for field in ("proposal_sha256", "confirmed_area"):
            with pytest.raises(ValueError, match="only apply"):
                build_record(record_type=record_type, **base, **more, **{field: "x"})
    for missing in (
        {},
        {"proposal_sha256": "sha256:x"},
        {"confirmed_area": "Employment"},
        {"proposal_sha256": "", "confirmed_area": "Employment"},
    ):
        with pytest.raises(ValueError, match="requires proposal_sha256"):
            build_record(record_type=PROPOSAL_CONFIRMATION, **base, **missing)


def test_confirmation_record_is_not_a_classification_acceptance(
    tmp_path: Path,
) -> None:
    manifest = _manifest()
    record = _confirm(tmp_path, manifest, _doc(manifest))
    status = evaluate_record(record, manifest, CLASSIFICATION_ACCEPTANCE)
    assert status.state == "mismatch"


def test_proposal_without_backend_fields_still_loads_and_confirms(
    tmp_path: Path,
) -> None:
    manifest = _manifest()
    doc = _doc(manifest)
    assert "ai_backend" not in doc
    assert "ai_model_id" not in doc
    proposal = _write_proposal(tmp_path, doc)
    assert load_proposal(proposal) == doc
    record = _confirm(tmp_path, manifest, doc)
    assert confirmation_status(proposal, record, manifest).state == "valid"


def test_backend_fields_are_covered_by_the_digest(tmp_path: Path) -> None:
    doc = _doc(_manifest())
    doc = build_proposal_document(
        **{
            k: doc[k]
            for k in (
                "system_id",
                "commit_ref",
                "scanner_version",
                "scan_input_digest",
                "scan_report_hash",
                "manifest_fingerprint",
                "declared_purpose",
                "area",
                "confidence",
            )
        },
        evidence=doc["evidence"],
        minority_evidence=[],
        prohibited_signals=[],
        proposal=doc["proposal"],
        ai_backend="deterministic",
        ai_model_id="codebert-onnx",
    )
    path = _write_proposal(tmp_path, doc)
    assert load_proposal(path)["ai_model_id"] == "codebert-onnx"
    path.write_text(
        json.dumps({**doc, "ai_model_id": "other"}, sort_keys=True), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="edited after it was written"):
        load_proposal(path)


def test_scan_tree_sha256_optional_and_covered_by_digest(tmp_path: Path) -> None:
    manifest = _manifest()
    plain = _doc(manifest)
    assert "scan_tree_sha256" not in plain  # older shape, byte-identical
    assert proposal_tree_sha256(plain) is None

    kwargs = {
        k: plain[k]
        for k in (
            "system_id",
            "commit_ref",
            "scanner_version",
            "scan_input_digest",
            "scan_report_hash",
            "manifest_fingerprint",
            "declared_purpose",
            "area",
            "confidence",
        )
    }
    tree = "ef" * 32
    doc = build_proposal_document(
        **kwargs,
        evidence=plain["evidence"],
        minority_evidence=[],
        prohibited_signals=[],
        proposal=plain["proposal"],
        scan_tree_sha256=tree,
    )
    assert proposal_tree_sha256(doc) == tree
    assert doc["proposal_sha256"] != plain["proposal_sha256"]
    path = _write_proposal(tmp_path, doc)
    assert load_proposal(path)["scan_tree_sha256"] == tree
    path.write_text(
        json.dumps({**doc, "scan_tree_sha256": "00" * 32}, sort_keys=True),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="edited after it was written"):
        load_proposal(path)
    assert proposal_tree_sha256({"scan_tree_sha256": ""}) is None
    assert proposal_tree_sha256({"scan_tree_sha256": 5}) is None


LITERAL_SIDECARS = ("scan-report.json", "eval-report.json", "compliance-artifact.json")


def test_tool_written_names_pin_the_sidecars() -> None:
    assert set(LITERAL_SIDECARS) <= set(TOOL_WRITTEN_NAMES)


@pytest.mark.parametrize(
    "rel",
    [
        PROPOSAL_FILENAME,
        ".ocignore",
        ".opencomplai/acceptances/s.record.json",
        *LITERAL_SIDECARS,
        *("out/" + n for n in LITERAL_SIDECARS),
    ],
)
def test_tool_written_names_are_tool_written(rel: str) -> None:
    assert is_tool_written_path(rel)


@pytest.mark.parametrize("rel", ["src/scan_report.py", "notes/scan-report.json.bak"])
def test_lookalike_names_are_not_tool_written(rel: str) -> None:
    assert not is_tool_written_path(rel)


def test_is_tool_written_path() -> None:
    assert is_tool_written_path(PROPOSAL_FILENAME)
    assert is_tool_written_path(".ocignore")
    assert is_tool_written_path(".opencomplai/acceptances/s.record.json")
    assert not is_tool_written_path("src/" + PROPOSAL_FILENAME)
    assert not is_tool_written_path("src/.ocignore")
    assert not is_tool_written_path(".opencomplai/acceptances")
    assert not is_tool_written_path(".opencomplai/config.yaml")
    assert not is_tool_written_path("app.py")
