"""
`check --sign` signs the artifact it writes, not an earlier draft of it.

`check` used to sign inside `_finalize_artifact` and then change the
artifact: the `--scan --fail-on` override, the checker verdict and the
`--with-gaps` blocks all landed after the signature, so the signed
compliance-artifact.json never verified. Each test signs with a throwaway
keypair and verifies the file on disk (and, in service mode, the copy
appended to the ledger) against its public key.
"""

from __future__ import annotations

import json
from pathlib import Path

from opencomplai_cli import main
from opencomplai_cli.main import app
from opencomplai_core.models import ScanStatusArtifact, SystemManifest
from opencomplai_core.signing import generate_keypair, verify_artifact
from typer.testing import CliRunner

runner = CliRunner()


def _setup(tmp_path: Path, monkeypatch) -> tuple[Path, Path]:
    """Chdir to tmp_path, force the local path, point `check` at a fresh
    keypair, and write a manifest. Returns `(manifest_file, pub_key)`."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENCOMPLAI_API_URL", raising=False)
    monkeypatch.delenv("OPENCOMPLAI_VAULT_URL", raising=False)
    monkeypatch.delenv("SIGNING_KEY_PRIVATE", raising=False)
    monkeypatch.setenv("OPENCOMPLAI_STATE_DIR", str(tmp_path / "state"))
    key_dir = tmp_path / "keys"
    generate_keypair(key_dir)
    monkeypatch.setattr(main, "_SIGNING_KEY", key_dir / "signing.key")

    manifest_file = tmp_path / "system-manifest.json"
    manifest_file.write_text(
        SystemManifest(
            system_id="sign-sys",
            intended_purpose="customer support chatbot",
            compliance_target="EU_AI_ACT",
            high_risk_presumption=False,
            commit_ref="HEAD",
        ).model_dump_json(),
        encoding="utf-8",
    )
    return manifest_file, key_dir / "signing.pub"


def _written_artifact(tmp_path: Path) -> ScanStatusArtifact:
    return ScanStatusArtifact.model_validate_json(
        (tmp_path / "compliance-artifact.json").read_text(encoding="utf-8")
    )


def test_signed_artifact_with_gaps_verifies(tmp_path, monkeypatch):
    manifest_file, pub_key = _setup(tmp_path, monkeypatch)

    result = runner.invoke(
        app, ["check", "--manifest", str(manifest_file), "--sign", "--with-gaps"]
    )
    assert result.exit_code == 0, result.output

    artifact = _written_artifact(tmp_path)
    assert artifact.gap_report is not None
    assert verify_artifact(artifact, pub_key) is True


def test_signed_artifact_after_failed_scan_override_verifies(tmp_path, monkeypatch):
    manifest_file, pub_key = _setup(tmp_path, monkeypatch)
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "requirements.txt").write_text("face_recognition\n", encoding="utf-8")
    (repo / "face.py").write_text("import face_recognition\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "check",
            "--manifest",
            str(manifest_file),
            "--repo-root",
            str(repo),
            "--scan",
            "--fail-on",
            "major",
            "--sign",
        ],
    )
    assert result.exit_code == 1, result.output

    artifact = _written_artifact(tmp_path)
    assert "CODE_CORROBORATION_GAP" in artifact.failed_controls
    assert verify_artifact(artifact, pub_key) is True


def test_service_mode_ledgers_the_final_signed_artifact(tmp_path, monkeypatch):
    manifest_file, pub_key = _setup(tmp_path, monkeypatch)
    monkeypatch.setenv("OPENCOMPLAI_API_URL", "http://gateway.invalid")

    def fake_call_service(path: str, payload: dict) -> tuple[int, dict]:
        if path == "/v1/risk/classify":
            return 200, {
                "risk_class": "minimal",
                "rationale_hash": "sha256:" + "a" * 64,
            }
        if path == "/v1/verify/claims":
            return 200, {"outcome": "verified"}
        return 200, {}

    events: list[tuple[str, dict]] = []
    monkeypatch.setattr(main, "_call_service", fake_call_service)
    monkeypatch.setattr(
        main,
        "_emit_event",
        lambda event_type, payload, *a, **kw: events.append((event_type, payload)),
    )

    result = runner.invoke(
        app, ["check", "--manifest", str(manifest_file), "--sign", "--with-gaps"]
    )
    assert result.exit_code == 0, result.output

    artifact = _written_artifact(tmp_path)
    assert verify_artifact(artifact, pub_key) is True
    ledgered = [p for t, p in events if t == "scan_status_artifact"]
    assert ledgered == [json.loads(artifact.model_dump_json())]
