"""Real (unpatched) gap rows decide `check` for an accepted high-risk system.

The matrix tests patch `evaluate_targets`; here nothing is patched. The result
asserted is the tool's computed artifact result for a synthetic fixture, not a
statement that any real system is compliant.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest
from opencomplai_cli import main
from opencomplai_cli.main import app
from opencomplai_core.gap_probes import _PROBE_PATTERNS, run_artifact_probe
from opencomplai_core.models import SystemManifest
from opencomplai_core.signing import generate_keypair
from typer.testing import CliRunner

runner = CliRunner()
# Trips EU_AIA_ART6_HIGH_RISK only (no profiling vocabulary).
HIGH_RISK = "managing the operation of critical road traffic infrastructure"
DOSSIER_REF = "technical_documentation_dossier"


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


def _accepted_repo(repo: Path) -> None:
    manifest = SystemManifest(system_id="mx-sys", intended_purpose=HIGH_RISK)
    (repo / "system-manifest.json").write_text(
        manifest.model_dump_json(), encoding="utf-8"
    )
    key = base64.b64encode((repo / "keys" / "signing.key").read_bytes()).decode()
    result = runner.invoke(
        app,
        ["accept", "--accepted-by", "dpo@example.test", "--statement", "Reviewed."],
        env={"SIGNING_KEY_PRIVATE": key},
    )
    assert result.exit_code == 0, result.output


def _materialise_probe_files(repo: Path) -> None:
    """One small file per probe ref, from the first pattern of its tuple."""
    for patterns in _PROBE_PATTERNS.values():
        rel = patterns[0].replace("**/", "").replace("*", "x")
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")


def _check_with_gaps():
    return runner.invoke(app, ["check", "-m", "system-manifest.json", "--with-gaps"])


def _artifact(repo: Path) -> dict:
    return json.loads((repo / "compliance-artifact.json").read_text("utf-8"))


def test_accepted_system_with_every_probe_file_exits_0(repo: Path) -> None:
    _accepted_repo(repo)
    _materialise_probe_files(repo)
    result = _check_with_gaps()
    artifact = _artifact(repo)
    assert result.exit_code == 0, result.output + str(artifact["failed_controls"])
    assert artifact["result"] == "pass"
    assert artifact["failed_controls"] == []


def test_removing_one_probe_file_fails_that_article(repo: Path) -> None:
    _accepted_repo(repo)
    _materialise_probe_files(repo)
    # safeguard: no other probe file matches the dossier probe
    found = run_artifact_probe(DOSSIER_REF, repo).found_paths
    assert found == ["dossier_x.json"]
    (repo / found[0]).unlink()

    result = _check_with_gaps()
    artifact = _artifact(repo)
    assert result.exit_code == 1, result.output
    assert "Art. 11" in artifact["failed_controls"]
    row = next(
        r for r in artifact["gap_report"]["articles"] if r["article"] == "Art. 11"
    )
    assert row["status"] == "missing"
