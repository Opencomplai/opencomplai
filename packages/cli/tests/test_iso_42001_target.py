"""`--target ISO_IEC_42001` end to end: gaps JSON, check --with-gaps, manifest, gate."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from opencomplai_cli import main
from opencomplai_core.models import DISCLAIMER_V2
from rich.console import Console
from typer.testing import CliRunner

ISO = "ISO_IEC_42001"


@pytest.fixture
def cli(tmp_path, monkeypatch):
    """Run the CLI in a temp repo; returns (exit code, stdout, stderr)."""
    monkeypatch.chdir(tmp_path)
    for var in (
        "OPENCOMPLAI_API_URL",
        "OPENCOMPLAI_VAULT_URL",
        "OPENCOMPLAI_RISK_ENGINE_URL",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("OPENCOMPLAI_STATE_DIR", str(tmp_path / "state"))
    home = tmp_path / "home"
    monkeypatch.setattr(main, "_OPENCOMPLAI_DIR", home)
    monkeypatch.setattr(main, "_CONFIG_FILE", home / "config.yaml")
    monkeypatch.setattr(main, "_SIGNING_KEY", home / "signing.key")
    monkeypatch.setattr(main, "_SIGNING_PUB", home / "signing.pub")

    out, err = io.StringIO(), io.StringIO()
    for name, buffer in (("console", out), ("err_console", err)):
        monkeypatch.setattr(
            main, name, Console(file=buffer, width=300, color_system=None)
        )

    def run(*args: str) -> tuple[int, str, str]:
        for buffer in (out, err):
            buffer.seek(0)
            buffer.truncate()
        result = CliRunner().invoke(main.app, list(args))
        return result.exit_code, out.getvalue(), err.getvalue()

    code, _, _ = run(
        "init",
        "--system-id",
        "iso-sys",
        "--intended-purpose",
        "credit scoring for loan applications",
    )
    assert code == 0
    return run


def _gaps_json(cli, *args: str) -> dict:
    code, stdout, stderr = cli("gaps", *args, "--output", "json")
    assert code == 0, stderr
    return json.loads(stdout)


def test_gaps_json_has_iso_framework_block(cli):
    envelope = _gaps_json(cli, "--target", ISO)
    assert envelope["disclaimer"] == DISCLAIMER_V2
    frameworks = envelope["payload"]["frameworks"]
    assert list(frameworks) == [ISO]  # targets only; EU is the legacy top level
    iso = frameworks[ISO]
    assert iso["derived_from"] is None
    assert iso["disclaimer_ref"] == "DISCLAIMER_V2"
    assert len(iso["report"]["articles"]) == 65


def test_check_with_gaps_embeds_framework_report(cli):
    code, _, stderr = cli("check", "--with-gaps", "--target", ISO)
    assert code != 2, stderr
    artifact = json.loads(Path("compliance-artifact.json").read_text())
    assert ISO in artifact["framework_reports"]
    assert artifact["gap_report"]


def test_manifest_compliance_targets_accepts_iso_key(cli):
    path = Path("system-manifest.json")
    manifest = json.loads(path.read_text())
    path.write_text(json.dumps({**manifest, "compliance_targets": ["EU_AI_ACT", ISO]}))
    code, _, stderr = cli("validate-manifest", str(path))
    assert code == 0, stderr
    path.write_text(
        json.dumps({**manifest, "compliance_targets": ["EU_AI_ACT", "ISO_42001"]})
    )
    code, _, _ = cli("validate-manifest", str(path))
    assert code == 2


def test_gate_on_iso_unverified_does_not_fail(cli):
    path = Path("system-manifest.json")
    manifest = json.loads(path.read_text())
    path.write_text(json.dumps({**manifest, "compliance_targets": ["EU_AI_ACT", ISO]}))
    code, _, stderr = cli("check", "--gate", ISO)
    assert code != 2, stderr
    artifact = json.loads(Path("compliance-artifact.json").read_text())
    failed = [c for c in artifact["failed_controls"] if c.startswith(f"{ISO}:")]
    # Attestation-only rows are Unverified and never fail. The four rows that also
    # look for a document read Missing in a repo without one, which is correct.
    assert set(failed) <= {
        f"{ISO}:Clause 6.1.2",
        f"{ISO}:Clause 6.1.3",
        f"{ISO}:A.6.2.7",
        f"{ISO}:A.8.2",
    }


def test_eu_only_output_unchanged_by_registration(cli):
    assert "frameworks" not in _gaps_json(cli)["payload"]
