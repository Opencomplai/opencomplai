"""Art. 6(3) exemption record: the Art. 49 `record` source, the gate, the fingerprint."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from opencomplai_core.acceptance import (
    ART_6_3_EXEMPTION,
    build_record,
    public_key_pem_from_private,
    record_path,
    sign_record,
)
from opencomplai_core.control_identity import (
    WATCHED_MANIFEST_FIELDS,
    fingerprint_manifest,
)
from opencomplai_core.exemption_gap import (
    CONTROL_ID,
    PROVENANCE,
    apply_exemption_gate,
    exemption_record_status,
    relies_on_derogation,
)
from opencomplai_core.gap_report import build_gap_report
from opencomplai_core.models import (
    ArticleGapSource,
    CheckerSessionRef,
    ConfidenceLabel,
    GapStatus,
    ScanResult,
    ScanStatusArtifact,
    SystemManifest,
)
from opencomplai_core.signing import generate_keypair

DEROGATION = "provider_art_6_4_registration"
RECORD_REF = "art_6_3_exemption_record"


@pytest.fixture(autouse=True)
def _no_trusted_pin(monkeypatch) -> None:
    monkeypatch.delenv("OPENCOMPLAI_TRUSTED_KEY_IDS", raising=False)


def _manifest(
    grounds: tuple[str, ...] = ("hr3_art_6_3",),
    obligations: tuple[str, ...] = (DEROGATION,),
    purpose: str = "credit scoring",
) -> SystemManifest:
    session = CheckerSessionRef(
        checker_version="checker-test",
        session_id="sess-1",
        completed_at="2026-09-18T00:00:00+00:00",
        obligation_ids=list(obligations),
        derogation_grounds=list(grounds),
    )
    return SystemManifest(
        system_id="sys-1",
        intended_purpose=purpose,
        operator_role="provider",
        checker_session=session,
    )


def _write_record(root: Path, manifest: SystemManifest) -> None:
    generate_keypair(root / "keys")
    key = root / "keys" / "signing.key"
    record = sign_record(
        build_record(
            record_type=ART_6_3_EXEMPTION,
            system_id=manifest.system_id,
            manifest_fingerprint=fingerprint_manifest(manifest),
            accepted_by="dpo@example.test",
            statement="Grounds reviewed.",
            accepted_at="2026-10-07T10:00:00Z",
            public_key_pem=public_key_pem_from_private(key.read_bytes()),
            grounds=manifest.checker_session.derogation_grounds,
        ),
        key,
    )
    path = record_path(root.resolve(), manifest.system_id, ART_6_3_EXEMPTION)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record), encoding="utf-8")


def _art49(manifest: SystemManifest, root: Path):
    report = build_gap_report(
        "sys-1",
        "abc123",
        repo_root=root,
        manifest=manifest,
        checker_session=manifest.checker_session,
    )
    return report, next((r for r in report.articles if r.article == "Art. 49"), None)


def _artifact(result: ScanResult, failed: tuple[str, ...] = ()) -> ScanStatusArtifact:
    return ScanStatusArtifact(
        install_id="i",
        system_id="sys-1",
        commit_ref="abc",
        result=result,
        failed_controls=list(failed),
        rationale_hash="sha256:00",
        duration_ms=1,
    )


def test_derogation_without_record_row_is_missing(tmp_path: Path) -> None:
    _, row = _art49(_manifest(), tmp_path)
    assert row is not None
    assert row.status == GapStatus.MISSING
    assert row.evidence_ref == RECORD_REF
    assert "absent" in row.rationale
    assert "does not assess whether the exemption is valid" in row.rationale


def test_valid_record_row_is_met(tmp_path: Path) -> None:
    manifest = _manifest()
    _write_record(tmp_path, manifest)
    status = exemption_record_status(manifest, tmp_path)
    assert status.status == GapStatus.MET
    assert status.evidence_ref == RECORD_REF
    assert status.confidence_label == ConfidenceLabel.ATTESTED
    _, row = _art49(manifest, tmp_path)
    assert row is not None
    # Worst status wins: the registration probe still decides the row.
    assert row.evidence_ref != RECORD_REF
    assert row.status != GapStatus.MET
    assert row.source == ArticleGapSource.ARTIFACT
    assert "exemption record" not in row.rationale


def test_changed_ground_makes_record_stale(tmp_path: Path) -> None:
    _write_record(tmp_path, _manifest(grounds=("hr3_art_6_3",)))
    changed = _manifest(grounds=("hr3_art_6_3", "hr6_accessory"))
    _, row = _art49(changed, tmp_path)
    assert row is not None
    assert row.status == GapStatus.MISSING
    assert row.evidence_ref == RECORD_REF
    assert "stale" in row.rationale


def test_art_49_applies_to_derogating_provider_and_high_risk(tmp_path: Path) -> None:
    for obligation in (DEROGATION, "provider_high_risk", "deployer_high_risk"):
        report, row = _art49(_manifest(obligations=(obligation,)), tmp_path)
        assert row is not None, obligation
        assert "Art. 49" not in report.not_applicable
    report, row = _art49(_manifest(obligations=("ai_literacy",)), tmp_path)
    assert row is None
    assert "Art. 49" in report.not_applicable


def test_high_risk_session_without_derogation_has_no_record_row(
    tmp_path: Path,
) -> None:
    _, row = _art49(_manifest(obligations=("provider_high_risk",)), tmp_path)
    assert row is not None
    assert row.evidence_ref != RECORD_REF


def test_sessionless_output_unchanged(tmp_path: Path) -> None:
    plain = build_gap_report("sys-1", "abc123", repo_root=tmp_path)
    bare = SystemManifest(system_id="sys-1", intended_purpose="credit scoring")
    with_manifest = build_gap_report(
        "sys-1", "abc123", repo_root=tmp_path, manifest=bare, checker_session=None
    )
    drop = {"generated_at"}
    assert plain.model_dump(exclude=drop) == with_manifest.model_dump(exclude=drop)
    row = next(r for r in plain.articles if r.article == "Art. 49")
    assert row.evidence_ref != RECORD_REF


def test_relies_on_derogation() -> None:
    assert relies_on_derogation(_manifest())
    assert not relies_on_derogation(_manifest(obligations=("provider_high_risk",)))
    assert not relies_on_derogation(
        SystemManifest(system_id="sys-1", intended_purpose="x")
    )


def test_fingerprint_unchanged_without_grounds() -> None:
    plain = SystemManifest(
        system_id="sys-1", intended_purpose="credit scoring", operator_role="provider"
    )
    values = plain.model_dump()
    subset = {
        f: values[f]
        for f in WATCHED_MANIFEST_FIELDS
        if values.get(f) is not None and not (f == "operator_roles" and not values[f])
    }
    oracle = hashlib.sha256(
        json.dumps(subset, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()
    assert fingerprint_manifest(plain) == oracle
    # A session without grounds (any obligations) adds nothing to the hash.
    assert fingerprint_manifest(_manifest(grounds=())) == oracle


def test_fingerprint_changes_with_grounds() -> None:
    none = fingerprint_manifest(_manifest(grounds=()))
    one = fingerprint_manifest(_manifest(grounds=("hr3_art_6_3",)))
    two = fingerprint_manifest(_manifest(grounds=("hr3_art_6_3", "hr6_accessory")))
    assert len({none, one, two}) == 3
    assert one == fingerprint_manifest(_manifest(grounds=("hr3_art_6_3",)).model_dump())


@pytest.mark.parametrize(
    "result",
    [ScanResult.POLICY_BLOCK, ScanResult.TRAP_DETECTED, ScanResult.VALIDATION_FAIL],
)
def test_gate_keeps_blocking_results(tmp_path: Path, result: ScanResult) -> None:
    artifact = _artifact(result, ("X",))
    out = apply_exemption_gate(artifact, _manifest(), repo_root=tmp_path, require=True)
    assert out is artifact


def test_gate_pass_becomes_control_fail_and_dedupes(tmp_path: Path) -> None:
    out = apply_exemption_gate(
        _artifact(ScanResult.PASS), _manifest(), repo_root=tmp_path, require=True
    )
    assert out.result == ScanResult.CONTROL_FAIL
    assert out.failed_controls == [CONTROL_ID]
    again = apply_exemption_gate(out, _manifest(), repo_root=tmp_path, require=True)
    assert again.failed_controls == [CONTROL_ID]


def test_gate_off_or_valid_record_is_untouched(tmp_path: Path) -> None:
    artifact = _artifact(ScanResult.PASS)
    manifest = _manifest()
    assert (
        apply_exemption_gate(artifact, manifest, repo_root=tmp_path, require=False)
        is artifact
    )
    _write_record(tmp_path, manifest)
    assert (
        apply_exemption_gate(artifact, manifest, repo_root=tmp_path, require=True)
        is artifact
    )


def test_provenance_is_flagged() -> None:
    assert PROVENANCE["needs_founder_review"] is True
    assert PROVENANCE["confidence"] == "low"
    assert PROVENANCE["source"]
