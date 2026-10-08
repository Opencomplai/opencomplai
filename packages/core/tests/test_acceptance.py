"""Signed committed acceptance records (SU-110a)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from opencomplai_core import acceptance as acc
from opencomplai_core.acceptance import (
    ART6_CONTROL,
    CLASSIFICATION_ACCEPTANCE,
    TRAP_APPROVAL,
    AcceptanceStatus,
    apply_acceptance,
    build_record,
    evaluate_record,
    key_id_for,
    public_key_pem_from_private,
    record_path,
    sign_record,
    trusted_key_ids_from_env,
)
from opencomplai_core.control_identity import fingerprint_manifest
from opencomplai_core.models import ScanResult, ScanStatusArtifact, SystemManifest
from opencomplai_core.signing import generate_keypair

AT = "2026-10-07T10:00:00Z"


def _manifest(purpose: str = "Automated resume screening") -> SystemManifest:
    return SystemManifest(system_id="sys-1", intended_purpose=purpose)


def _key(tmp_path: Path, name: str = "k") -> Path:
    generate_keypair(tmp_path / name)
    return tmp_path / name / "signing.key"


def _record(
    key: Path,
    manifest: SystemManifest | None = None,
    record_type: str = CLASSIFICATION_ACCEPTANCE,
    **over,
) -> dict:
    m = manifest or _manifest()
    fields = {
        "record_type": record_type,
        "system_id": m.system_id,
        "manifest_fingerprint": fingerprint_manifest(m),
        "accepted_by": "dpo@example.test",
        "statement": "Reviewed; we accept the classification.",
        "accepted_at": AT,
        "public_key_pem": public_key_pem_from_private(key.read_bytes()),
        "change_context": "model_retrain" if record_type == TRAP_APPROVAL else None,
    }
    fields.update(over)
    return sign_record(build_record(**fields), key)


def _write(tmp_path: Path, record: dict) -> Path:
    path = tmp_path / "rec.json"
    path.write_text(json.dumps(record), encoding="utf-8")
    return path


def _artifact(result: ScanResult, failed: list[str]) -> ScanStatusArtifact:
    return ScanStatusArtifact(
        install_id="i",
        system_id="sys-1",
        commit_ref="abc",
        result=result,
        failed_controls=failed,
        rationale_hash="sha256:00",
        duration_ms=1,
    )


def test_valid_record_round_trip(tmp_path: Path) -> None:
    status = evaluate_record(
        _write(tmp_path, _record(_key(tmp_path))),
        _manifest(),
        CLASSIFICATION_ACCEPTANCE,
    )
    assert status.state == "valid"
    assert status.record["accepted_by"] == "dpo@example.test"


def test_unsigned_record_rejected(tmp_path: Path) -> None:
    rec = _record(_key(tmp_path))
    del rec["signature"]
    assert (
        evaluate_record(
            _write(tmp_path, rec), _manifest(), CLASSIFICATION_ACCEPTANCE
        ).state
        == "unsigned"
    )
    rec["signature"] = ""
    assert (
        evaluate_record(
            _write(tmp_path, rec), _manifest(), CLASSIFICATION_ACCEPTANCE
        ).state
        == "unsigned"
    )


@pytest.mark.parametrize(
    "field",
    [
        "statement",
        "accepted_by",
        "accepted_at",
        "system_id",
        "manifest_fingerprint",
        "change_context",
    ],
)
def test_tampered_field_rejected(tmp_path: Path, field: str) -> None:
    rec = _record(_key(tmp_path), record_type=TRAP_APPROVAL)
    rec[field] = rec[field] + "x"
    manifest = _manifest()
    if field == "system_id":
        manifest = SystemManifest(
            system_id=rec[field], intended_purpose=manifest.intended_purpose
        )
    status = evaluate_record(_write(tmp_path, rec), manifest, TRAP_APPROVAL)
    assert status.state == "tampered"


def test_swapped_public_key_rejected(tmp_path: Path) -> None:
    rec = _record(_key(tmp_path, "a"))
    rec["public_key"] = public_key_pem_from_private(_key(tmp_path, "b").read_bytes())
    status = evaluate_record(
        _write(tmp_path, rec), _manifest(), CLASSIFICATION_ACCEPTANCE
    )
    assert status.state == "tampered"


def test_resigned_with_other_key_rejected_when_trusted_ids_set(tmp_path: Path) -> None:
    trusted = _key(tmp_path, "trusted")
    trusted_id = key_id_for(public_key_pem_from_private(trusted.read_bytes()))
    path = _write(tmp_path, _record(_key(tmp_path, "attacker")))
    pinned = frozenset({trusted_id})
    status = evaluate_record(
        path, _manifest(), CLASSIFICATION_ACCEPTANCE, trusted_key_ids=pinned
    )
    assert status.state == "untrusted"
    path = _write(tmp_path, _record(trusted))
    status = evaluate_record(
        path, _manifest(), CLASSIFICATION_ACCEPTANCE, trusted_key_ids=pinned
    )
    assert status.state == "valid"


def test_stale_after_fingerprint_change(tmp_path: Path) -> None:
    path = _write(tmp_path, _record(_key(tmp_path)))
    edited = _manifest("Automated resume screening, now also ranking")
    assert evaluate_record(path, edited, CLASSIFICATION_ACCEPTANCE).state == "stale"


def test_wrong_system_id_is_mismatch(tmp_path: Path) -> None:
    path = _write(tmp_path, _record(_key(tmp_path)))
    other = SystemManifest(system_id="sys-2", intended_purpose="x")
    assert evaluate_record(path, other, CLASSIFICATION_ACCEPTANCE).state == "mismatch"


def test_malformed_json_is_malformed_not_exception(tmp_path: Path) -> None:
    path = tmp_path / "rec.json"
    for text in ("{not json", "[]", '{"schema_version": 1}'):
        path.write_text(text, encoding="utf-8")
        status = evaluate_record(path, _manifest(), CLASSIFICATION_ACCEPTANCE)
        assert status.state == "malformed"
    assert (
        evaluate_record(
            tmp_path / "none.json", _manifest(), CLASSIFICATION_ACCEPTANCE
        ).state
        == "absent"
    )


def test_path_is_slugged_no_traversal(tmp_path: Path) -> None:
    p = record_path(tmp_path, "../../etc/passwd", CLASSIFICATION_ACCEPTANCE)
    assert p.parent == tmp_path / ".opencomplai" / "acceptances"
    assert "/" not in p.name
    assert "\\" not in p.name
    assert not p.name.startswith(".")
    assert p.name.endswith(".classification_acceptance.json")


def test_trap_approval_record_round_trips_and_is_not_an_acceptance(
    tmp_path: Path,
) -> None:
    path = _write(tmp_path, _record(_key(tmp_path), record_type=TRAP_APPROVAL))
    assert evaluate_record(path, _manifest(), TRAP_APPROVAL).state == "valid"
    assert (
        evaluate_record(path, _manifest(), CLASSIFICATION_ACCEPTANCE).state
        == "mismatch"
    )
    with pytest.raises(ValueError, match="change_context"):
        build_record(
            record_type=TRAP_APPROVAL,
            system_id="s",
            manifest_fingerprint="f",
            accepted_by="a",
            statement="s",
            accepted_at=AT,
            public_key_pem="p",
        )


def _valid(
    tmp_path: Path, record_type: str = CLASSIFICATION_ACCEPTANCE
) -> AcceptanceStatus:
    path = _write(tmp_path, _record(_key(tmp_path), record_type=record_type))
    return evaluate_record(path, _manifest(), record_type)


def test_apply_acceptance_clears_art6_only_failure(tmp_path: Path) -> None:
    out = apply_acceptance(
        _artifact(ScanResult.CONTROL_FAIL, [ART6_CONTROL]), _valid(tmp_path)
    )
    assert out.result == ScanResult.PASS
    assert out.failed_controls == []


@pytest.mark.parametrize(
    ("result", "failed"),
    [
        (ScanResult.POLICY_BLOCK, ["EU_AIA_ART5_UNACCEPTABLE", ART6_CONTROL]),
        (ScanResult.TRAP_DETECTED, ["EU_AIA_ART25_MODIFICATION_TRAP", ART6_CONTROL]),
        (ScanResult.VALIDATION_FAIL, [ART6_CONTROL]),
        (ScanResult.CONTROL_FAIL, ["EU_AIA_ART6_PROFILING"]),
        (ScanResult.CONTROL_FAIL, ["EVAL_SAFETY", "CODE_CORROBORATION_GAP"]),
    ],
)
def test_apply_acceptance_only_removes_art6(tmp_path: Path, result, failed) -> None:
    out = apply_acceptance(_artifact(result, failed), _valid(tmp_path))
    assert out.result == result
    assert out.failed_controls == failed


def test_apply_acceptance_keeps_other_failures_as_control_fail(tmp_path: Path) -> None:
    art = _artifact(ScanResult.CONTROL_FAIL, [ART6_CONTROL, "EU_AIA_ART6_PROFILING"])
    out = apply_acceptance(art, _valid(tmp_path))
    assert out.result == ScanResult.CONTROL_FAIL
    assert out.failed_controls == ["EU_AIA_ART6_PROFILING"]


def test_apply_acceptance_noop_when_not_valid(tmp_path: Path) -> None:
    art = _artifact(ScanResult.CONTROL_FAIL, [ART6_CONTROL])
    for state in (
        "absent",
        "stale",
        "tampered",
        "unsigned",
        "mismatch",
        "untrusted",
        "malformed",
    ):
        assert apply_acceptance(art, AcceptanceStatus(state, "r")) is art
    # a valid trap approval is not an acceptance
    assert apply_acceptance(art, _valid(tmp_path, TRAP_APPROVAL)) is art


def test_trusted_key_ids_from_env() -> None:
    assert trusted_key_ids_from_env({}) == frozenset()
    env = {"OPENCOMPLAI_TRUSTED_KEY_IDS": " sha256:a, ,sha256:b "}
    assert trusted_key_ids_from_env(env) == frozenset({"sha256:a", "sha256:b"})


def test_acceptance_module_never_reads_the_clock() -> None:
    source = Path(acc.__file__).read_text(encoding="utf-8")
    assert "datetime.now" not in source
    assert "time.time" not in source
