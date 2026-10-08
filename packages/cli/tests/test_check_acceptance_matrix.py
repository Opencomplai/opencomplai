"""Exit-code matrix of `check` for an accepted high-risk system (SU-110b).

Records are created through `opencomplai accept`; the one exception is the
prohibited case, where `accept` refuses, so that record is built and signed
with the core helpers.
"""

from __future__ import annotations

import base64
import json
import shutil
from pathlib import Path

import pytest
from opencomplai_cli import acceptance_gate, main
from opencomplai_cli.main import app
from opencomplai_core.acceptance import (
    CLASSIFICATION_ACCEPTANCE,
    TRAP_APPROVAL,
    build_record,
    public_key_pem_from_private,
    record_path,
    sign_record,
)
from opencomplai_core.control_identity import fingerprint_manifest
from opencomplai_core.frameworks import EU_AI_ACT
from opencomplai_core.models import (
    ArticleGapSource,
    ArticleGapStatus,
    CheckerSessionRef,
    FrameworkReport,
    GapReport,
    GapStatus,
    SystemManifest,
    SystemState,
)
from opencomplai_core.signing import generate_keypair
from opencomplai_core.system_state_store import load_state
from typer.testing import CliRunner

runner = CliRunner()
# Trips EU_AIA_ART6_HIGH_RISK only (no profiling vocabulary).
HIGH_RISK = "managing the operation of critical road traffic infrastructure"
OTHER_HIGH_RISK = "assisting judges in researching case law"
PROHIBITED = "social scoring of citizens by public authority"
ART6 = "EU_AIA_ART6_HIGH_RISK"
TRAP = "EU_AIA_ART25_MODIFICATION_TRAP"
DOCS = Path(__file__).resolve().parents[3] / "docs" / "src" / "cli"


@pytest.fixture
def repo(tmp_path: Path, monkeypatch) -> Path:
    """Fresh repo dir with a signing key and an isolated HOME/state."""
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
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("OPENCOMPLAI_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setattr(main, "_OPENCOMPLAI_DIR", home / "missing")
    monkeypatch.setattr(main, "_CONFIG_FILE", home / "missing" / "config.yaml")
    monkeypatch.setattr(main, "_SIGNING_KEY", home / "missing" / "signing.key")
    monkeypatch.setattr(main, "_SIGNING_PUB", home / "missing" / "signing.pub")
    generate_keypair(tmp_path / "keys")
    return tmp_path


def _manifest(
    repo: Path, purpose: str = HIGH_RISK, verdict: str | None = None
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
        system_id="mx-sys", intended_purpose=purpose, checker_session=session
    )
    (repo / "system-manifest.json").write_text(
        manifest.model_dump_json(), encoding="utf-8"
    )
    return manifest


def _key(repo: Path) -> Path:
    return repo / "keys" / "signing.key"


def _accept(repo: Path, *extra: str) -> None:
    env = {"SIGNING_KEY_PRIVATE": base64.b64encode(_key(repo).read_bytes()).decode()}
    result = runner.invoke(
        app,
        [
            "accept",
            "--accepted-by",
            "dpo@example.test",
            "--statement",
            "Reviewed.",
            *extra,
        ],
        env=env,
    )
    assert result.exit_code == 0, result.output


def _trap_approval(repo: Path, context: str) -> None:
    _accept(repo, "--trap-approval", "--change-context", context)


def _check(*args: str):
    return runner.invoke(app, ["check", "-m", "system-manifest.json", *args])


def _artifact(repo: Path) -> dict:
    return json.loads((repo / "compliance-artifact.json").read_text("utf-8"))


def _failed(repo: Path) -> list[str]:
    return _artifact(repo)["failed_controls"]


def _eu_report(statuses: dict[str, GapStatus]) -> dict[str, FrameworkReport]:
    rows = [
        ArticleGapStatus(
            article=art, status=status, source=ArticleGapSource.RULE, evidence_ref="x"
        )
        for art, status in statuses.items()
    ]
    report = GapReport(
        system_id="mx-sys",
        commit_ref="c",
        generated_at="2026-01-01T00:00:00Z",
        articles=rows,
    )
    return {
        EU_AI_ACT: FrameworkReport(
            framework=EU_AI_ACT,
            label="EU AI Act",
            data_version="test",
            disclaimer_ref="DISCLAIMER_V1",
            report=report,
        )
    }


def _patch_rows(monkeypatch, statuses: dict[str, GapStatus]) -> None:
    reports = _eu_report(statuses)
    monkeypatch.setattr(acceptance_gate, "evaluate_targets", lambda *a, **k: reports)


def _hand_record(manifest: SystemManifest, key: Path) -> dict:
    return sign_record(
        build_record(
            record_type=CLASSIFICATION_ACCEPTANCE,
            system_id=manifest.system_id,
            manifest_fingerprint=fingerprint_manifest(manifest),
            accepted_by="dpo@example.test",
            statement="Reviewed.",
            accepted_at="2026-10-07T10:00:00Z",
            public_key_pem=public_key_pem_from_private(key.read_bytes()),
        ),
        key,
    )


def _acceptance_path(repo: Path, record_type: str = CLASSIFICATION_ACCEPTANCE) -> Path:
    return record_path(repo.resolve(), "mx-sys", record_type)


def _write_record(repo: Path, record: dict) -> None:
    path = _acceptance_path(repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", "utf-8")


def test_matrix_not_accepted_exits_1(repo: Path) -> None:
    _manifest(repo)
    result = _check()
    assert result.exit_code == 1, result.output
    assert _failed(repo) == [ART6]


def test_matrix_accepted_no_missing_exits_0(repo: Path, monkeypatch) -> None:
    _manifest(repo)
    _accept(repo)
    _patch_rows(monkeypatch, {"Art. 6": GapStatus.MISSING, "Art. 9": GapStatus.MET})
    result = _check()
    assert result.exit_code == 0, result.output
    assert ART6 not in _failed(repo)
    assert _artifact(repo)["result"] == "pass"


def test_matrix_accepted_with_missing_rows_exits_1(repo: Path, monkeypatch) -> None:
    _manifest(repo)
    _accept(repo)
    _patch_rows(monkeypatch, {"Art. 6": GapStatus.MISSING, "Art. 9": GapStatus.MISSING})
    result = _check()
    assert result.exit_code == 1, result.output
    assert _failed(repo) == ["Art. 9"]


def test_matrix_real_rows_decide_the_exit(repo: Path) -> None:
    """Unpatched: failed_controls are exactly the real Missing rows, Art. 6 apart."""
    _manifest(repo)
    _accept(repo)
    result = _check("--with-gaps")
    artifact = _artifact(repo)
    missing = [
        row["article"]
        for row in artifact["gap_report"]["articles"]
        if row["status"] == "missing" and row["article"] != "Art. 6"
    ]
    assert artifact["failed_controls"] == missing
    assert result.exit_code == (1 if missing else 0), result.output


def test_matrix_stale_acceptance_exits_1(repo: Path) -> None:
    _manifest(repo)
    _accept(repo)
    _manifest(repo, OTHER_HIGH_RISK)
    result = _check()
    assert result.exit_code == 1, result.output
    assert "stale" in result.stderr
    assert ART6 in _failed(repo)


def test_matrix_prohibited_exits_3_even_when_accepted(repo: Path) -> None:
    manifest = _manifest(repo, PROHIBITED)
    _write_record(repo, _hand_record(manifest, _key(repo)))
    result = _check()
    assert result.exit_code == 3, result.output
    assert "EU_AIA_ART5_UNACCEPTABLE" in _failed(repo)

    manifest = _manifest(repo, "Summarises internal documents", "prohibited_practice")
    _write_record(repo, _hand_record(manifest, _key(repo)))
    result = _check()
    assert result.exit_code == 3, result.output
    assert _artifact(repo)["result"] == "policy_block"


def test_matrix_tampered_record_exits_1(repo: Path) -> None:
    _manifest(repo)
    _accept(repo)
    path = _acceptance_path(repo)
    path.write_text(path.read_text("utf-8").replace("Reviewed.", "Reviewed!"), "utf-8")
    result = _check()
    assert result.exit_code == 1, result.output
    assert "tampered" in result.stderr
    assert ART6 in _failed(repo)


def test_trap_approval_honoured_no_halt(repo: Path, monkeypatch) -> None:
    _manifest(repo)
    _accept(repo)
    _trap_approval(repo, "model_retrain")
    state = repo / "state"
    with monkeypatch.context() as m:
        _patch_rows(m, {"Art. 9": GapStatus.MET})
        result = _check("--change-context", "model_retrain")
    assert result.exit_code == 0, result.output
    assert _artifact(repo)["result"] == "pass"
    assert _failed(repo) == []
    assert load_state(state, "mx-sys") == SystemState.RUNNING

    # Real rows: the approved trap never fails through its own Art. 25 row.
    _check("--change-context", "model_retrain")
    assert "Art. 25" not in _failed(repo)
    assert TRAP not in _failed(repo)
    assert load_state(state, "mx-sys") == SystemState.RUNNING


def test_trap_without_approval_still_exit_4_and_halts(repo: Path) -> None:
    _manifest(repo)
    state = repo / "state"
    _accept(repo)

    result = _check("--change-context", "model_retrain")
    assert result.exit_code == 4, result.output
    assert TRAP in _failed(repo)
    assert load_state(state, "mx-sys") == SystemState.HALTED_PENDING_REVIEW

    # An approval minted for another change context does not apply.
    shutil.rmtree(state)
    _trap_approval(repo, "purpose_change")
    result = _check("--change-context", "model_retrain")
    assert result.exit_code == 4, result.output
    assert load_state(state, "mx-sys") == SystemState.HALTED_PENDING_REVIEW

    # An approval without a valid classification acceptance is not honoured.
    shutil.rmtree(state)
    _trap_approval(repo, "model_retrain")
    _acceptance_path(repo).unlink()
    result = _check("--change-context", "model_retrain")
    assert result.exit_code == 4, result.output
    assert load_state(state, "mx-sys") == SystemState.HALTED_PENDING_REVIEW
    assert _acceptance_path(repo, TRAP_APPROVAL).is_file()


def test_no_record_output_unchanged(repo: Path, monkeypatch) -> None:
    _manifest(repo)
    volatile = {"install_id", "timestamp", "duration_ms", "signature"}

    def stable() -> dict:
        return {k: v for k, v in _artifact(repo).items() if k not in volatile}

    assert _check().exit_code == 1
    with_call = stable()
    monkeypatch.setattr(
        main, "apply_acceptance_gate", lambda artifact, *a, **k: (artifact, False)
    )
    assert _check().exit_code == 1
    assert with_call == stable()


def test_docs_matrix_lists_all_four_rows() -> None:
    rows = (
        "Not accepted",
        "Accepted, no Missing EU rows",
        "Accepted, Missing EU rows",
        "Stale or invalid record",
    )
    for name in ("exit-codes.md", "check.md"):
        text = (DOCS / name).read_text(encoding="utf-8")
        assert "High-risk acceptance" in text, name
        for row in rows:
            assert row in text, (name, row)
