"""`check` honours a signed acceptance committed in the repository (SU-110a)."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest
from opencomplai_cli import acceptance_gate, main
from opencomplai_cli.main import app
from opencomplai_core.acceptance import (
    CLASSIFICATION_ACCEPTANCE,
    build_record,
    key_id_for,
    public_key_pem_from_private,
    record_path,
    sign_record,
)
from opencomplai_core.control_identity import fingerprint_manifest
from opencomplai_core.frameworks import EU_AI_ACT
from opencomplai_core.models import (
    CheckerSessionRef,
    FrameworkReport,
    GapReport,
    SystemManifest,
)
from opencomplai_core.signing import generate_keypair
from typer.testing import CliRunner

runner = CliRunner()
# Trips EU_AIA_ART6_HIGH_RISK only (no profiling vocabulary).
HIGH_RISK = "managing the operation of critical road traffic infrastructure"
OTHER_HIGH_RISK = "assisting judges in researching case law"
PROHIBITED = "social scoring of citizens by public authority"
PROFILING_TOO = "ranking job applicants"


@pytest.fixture(autouse=True)
def _no_missing_eu_rows(monkeypatch) -> None:
    """These tests cover record handling; the Missing-row gate lives in the matrix tests."""
    reports = {
        EU_AI_ACT: FrameworkReport(
            framework=EU_AI_ACT,
            label="EU AI Act",
            data_version="test",
            disclaimer_ref="DISCLAIMER_V1",
            report=GapReport(
                system_id="s",
                commit_ref="c",
                generated_at="2026-01-01T00:00:00Z",
                articles=[],
            ),
        )
    }
    monkeypatch.setattr(acceptance_gate, "evaluate_targets", lambda *a, **k: reports)


@pytest.fixture
def home(tmp_path: Path, monkeypatch) -> Path:
    """Fresh HOME: empty tmp dirs, and the home signing key/pub do not exist."""
    monkeypatch.chdir(tmp_path)
    for var in (
        "SIGNING_KEY_PRIVATE",
        "OPENCOMPLAI_TRUSTED_KEY_IDS",
        "OPENCOMPLAI_API_URL",
        "OPENCOMPLAI_VAULT_URL",
        "OPENCOMPLAI_RISK_ENGINE_URL",
        "GITHUB_SHA",
        "CI_COMMIT_SHA",
    ):
        monkeypatch.delenv(var, raising=False)
    fresh = tmp_path / "home"
    fresh.mkdir()
    monkeypatch.setenv("HOME", str(fresh))
    monkeypatch.setenv("USERPROFILE", str(fresh))
    monkeypatch.setenv("OPENCOMPLAI_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setattr(main, "_OPENCOMPLAI_DIR", fresh / "missing")
    monkeypatch.setattr(main, "_CONFIG_FILE", fresh / "missing" / "config.yaml")
    monkeypatch.setattr(main, "_SIGNING_KEY", fresh / "missing" / "signing.key")
    monkeypatch.setattr(main, "_SIGNING_PUB", fresh / "missing" / "signing.pub")
    return fresh


def _manifest(
    tmp_path: Path,
    purpose: str = HIGH_RISK,
    verdict: str | None = None,
    system_id: str = "acc-sys",
) -> SystemManifest:
    session = (
        CheckerSessionRef(
            checker_version="checker-test",
            session_id="s",
            completed_at="2026-01-01T00:00:00Z",
            verdict=verdict,
        )
        if verdict
        else None
    )
    manifest = SystemManifest(
        system_id=system_id, intended_purpose=purpose, checker_session=session
    )
    (tmp_path / "system-manifest.json").write_text(
        manifest.model_dump_json(), encoding="utf-8"
    )
    return manifest


def _key(tmp_path: Path, name: str = "keys") -> Path:
    generate_keypair(tmp_path / name)
    return tmp_path / name / "signing.key"


def _record(manifest: SystemManifest, key: Path, **over) -> dict:
    fields = {
        "record_type": CLASSIFICATION_ACCEPTANCE,
        "system_id": manifest.system_id,
        "manifest_fingerprint": fingerprint_manifest(manifest),
        "accepted_by": "dpo@example.test",
        "statement": "Reviewed and accepted.",
        "accepted_at": "2026-10-07T10:00:00Z",
        "public_key_pem": public_key_pem_from_private(key.read_bytes()),
    }
    fields.update(over)
    return sign_record(build_record(**fields), key)


def _commit(tmp_path: Path, manifest: SystemManifest, record: dict) -> Path:
    path = record_path(
        tmp_path.resolve(), manifest.system_id, CLASSIFICATION_ACCEPTANCE
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return path


def _check(*args: str):
    return runner.invoke(app, ["check", "-m", "system-manifest.json", *args])


def _failed(tmp_path: Path) -> list[str]:
    artifact = json.loads((tmp_path / "compliance-artifact.json").read_text("utf-8"))
    return artifact["failed_controls"]


def test_valid_acceptance_on_fresh_home_exits_0(tmp_path: Path, home: Path) -> None:
    manifest = _manifest(tmp_path)
    assert _check().exit_code == 1  # no record: unchanged behaviour
    _commit(tmp_path, manifest, _record(manifest, _key(tmp_path)))
    result = _check()
    assert result.exit_code == 0, result.output
    assert _failed(tmp_path) == []
    assert "Accepted high-risk classification" in result.stderr
    assert "dpo@example.test" in result.stderr
    assert "2026-10-07T10:00:00Z" in result.stderr
    assert "acceptances/acc-sys.classification_acceptance.json" in result.stderr
    assert not any(home.iterdir())  # nothing created under HOME


def test_valid_acceptance_clears_checker_verdict_path(
    tmp_path: Path, home: Path
) -> None:
    manifest = _manifest(
        tmp_path, "Summarises internal documents", "high_risk_ai_system"
    )
    assert _check().exit_code == 1
    assert "EU_AIA_ART6_HIGH_RISK" in _failed(tmp_path)
    _commit(tmp_path, manifest, _record(manifest, _key(tmp_path)))
    result = _check()
    assert result.exit_code == 0, result.output
    assert _failed(tmp_path) == []


def test_edited_purpose_makes_acceptance_stale_exit_1(
    tmp_path: Path, home: Path
) -> None:
    manifest = _manifest(tmp_path)
    _commit(tmp_path, manifest, _record(manifest, _key(tmp_path)))
    assert _check().exit_code == 0
    _manifest(tmp_path, OTHER_HIGH_RISK)
    result = _check()
    assert result.exit_code == 1, result.output
    assert "stale" in result.stderr
    assert "WARN" in result.stderr
    assert "EU_AIA_ART6_HIGH_RISK" in _failed(tmp_path)


def test_unsigned_and_tampered_records_exit_1(tmp_path: Path, home: Path) -> None:
    manifest = _manifest(tmp_path)
    good = _record(manifest, _key(tmp_path))

    unsigned = {k: v for k, v in good.items() if k != "signature"}
    _commit(tmp_path, manifest, unsigned)
    result = _check()
    assert result.exit_code == 1
    assert "unsigned" in result.stderr

    _commit(tmp_path, manifest, {**good, "statement": "Edited after signing."})
    result = _check()
    assert result.exit_code == 1
    assert "tampered" in result.stderr

    _commit(tmp_path, manifest, good)
    assert _check().exit_code == 0


def test_prohibited_still_exits_3_with_valid_acceptance(
    tmp_path: Path, home: Path
) -> None:
    manifest = _manifest(tmp_path, PROHIBITED)
    # `accept` refuses a prohibited system, so the record is hand-built.
    _commit(tmp_path, manifest, _record(manifest, _key(tmp_path)))
    result = _check()
    assert result.exit_code == 3, result.output
    assert "EU_AIA_ART5_UNACCEPTABLE" in _failed(tmp_path)
    assert "not counted as a failure" not in result.stderr


def test_acceptance_for_other_system_ignored(tmp_path: Path, home: Path) -> None:
    _manifest(tmp_path)
    other = SystemManifest(system_id="other-sys", intended_purpose=HIGH_RISK)
    _commit(tmp_path, other, _record(other, _key(tmp_path)))
    result = _check()
    assert result.exit_code == 1, result.output
    assert "ccept" not in result.stderr


def test_no_record_output_unchanged(tmp_path: Path, home: Path) -> None:
    _manifest(tmp_path)
    result = _check()
    assert result.exit_code == 1
    assert "ccept" not in result.stderr
    assert "ccept" not in result.stdout
    assert _failed(tmp_path) == ["EU_AIA_ART6_HIGH_RISK"]


def test_json_output_has_no_acceptance_line(tmp_path: Path, home: Path) -> None:
    manifest = _manifest(tmp_path)
    _commit(tmp_path, manifest, _record(manifest, _key(tmp_path)))
    result = _check("-o", "json")
    assert result.exit_code == 0, result.output
    assert "ccept" not in result.stderr
    assert json.loads(result.stdout)["result"] == "pass"


def test_acceptance_keeps_other_failures(tmp_path: Path, home: Path) -> None:
    manifest = _manifest(tmp_path, PROFILING_TOO)
    _check()
    assert set(_failed(tmp_path)) == {"EU_AIA_ART6_HIGH_RISK", "EU_AIA_ART6_PROFILING"}
    _commit(tmp_path, manifest, _record(manifest, _key(tmp_path)))
    result = _check()
    assert result.exit_code == 1, result.output
    assert _failed(tmp_path) == ["EU_AIA_ART6_PROFILING"]


def test_trusted_key_ids_env_pins_signer(
    tmp_path: Path, home: Path, monkeypatch
) -> None:
    manifest = _manifest(tmp_path)
    key = _key(tmp_path)
    _commit(tmp_path, manifest, _record(manifest, key))

    other = key_id_for(
        public_key_pem_from_private(_key(tmp_path, "other").read_bytes())
    )
    monkeypatch.setenv("OPENCOMPLAI_TRUSTED_KEY_IDS", other)
    result = _check()
    assert result.exit_code == 1
    assert "untrusted" in result.stderr

    mine = key_id_for(public_key_pem_from_private(key.read_bytes()))
    monkeypatch.setenv("OPENCOMPLAI_TRUSTED_KEY_IDS", f"{other}, {mine}")
    assert _check().exit_code == 0


def test_accept_then_check_end_to_end(tmp_path: Path, home: Path, monkeypatch) -> None:
    _manifest(tmp_path)
    monkeypatch.setenv(
        "SIGNING_KEY_PRIVATE", base64.b64encode(_key(tmp_path).read_bytes()).decode()
    )
    assert _check().exit_code == 1
    accepted = runner.invoke(
        app, ["accept", "--accepted-by", "dpo@example.test", "--statement", "Reviewed."]
    )
    assert accepted.exit_code == 0, accepted.output
    monkeypatch.delenv("SIGNING_KEY_PRIVATE")
    result = _check()
    assert result.exit_code == 0, result.output
    assert "Accepted high-risk classification" in result.stderr
