"""SU-104: `opencomplai verify --kind dossier` dispatches to the dossier verifier."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from opencomplai_cli.commands import verify as verify_mod
from opencomplai_cli.main import app
from opencomplai_core.dossier_generator import generate_dossier
from opencomplai_core.engine import assess
from opencomplai_core.models import AssessmentInput, ModelMetadata, SystemManifest
from opencomplai_core.signing import generate_keypair
from typer.testing import CliRunner

runner = CliRunner()


@pytest.fixture(autouse=True)
def _clean_signing_env(monkeypatch):
    for name in (
        "DOSSIER_SIGNING_KEY_PATH",
        "LOCAL_SIGNING_KEY_PATH",
        "SIGNING_KEY_PRIVATE",
    ):
        monkeypatch.delenv(name, raising=False)


def _dossier_file(tmp_path: Path, monkeypatch, *, sign: bool) -> tuple[Path, Path]:
    key_dir = tmp_path / "keys"
    generate_keypair(key_dir)
    if sign:
        monkeypatch.setenv("DOSSIER_SIGNING_KEY_PATH", str(key_dir / "signing.key"))
    manifest = SystemManifest(
        system_id="t",
        intended_purpose="chatbot",
        compliance_target="EU_AI_ACT",
        high_risk_presumption=False,
        commit_ref="abc123",
    )
    risk = assess(
        AssessmentInput(
            model=ModelMetadata(
                name="t",
                version="1.0.0",
                modality="text",
                use_case="chatbot",
                deployment_context="production",
            )
        )
    )
    path = tmp_path / "dossier.json"
    path.write_text(
        generate_dossier(manifest, risk).model_dump_json(), encoding="utf-8"
    )
    return path, key_dir / "signing.pub"


def _run(path: Path, pub: Path | None, *extra: str):
    args = ["verify", str(path), "--kind", "dossier", *extra]
    if pub is not None:
        args += ["--pub-key", str(pub)]
    return runner.invoke(app, args)


def test_signed_dossier_verifies_via_cli(tmp_path, monkeypatch):
    path, pub = _dossier_file(tmp_path, monkeypatch, sign=True)
    res = _run(path, pub)
    assert res.exit_code == 0
    assert "verified" in res.output


def test_unsigned_dossier_reported_unsigned(tmp_path, monkeypatch):
    path, _ = _dossier_file(tmp_path, monkeypatch, sign=False)
    # No key needed for the unsigned verdict.
    res = _run(path, tmp_path / "no-such.pub", "--output", "json")
    assert res.exit_code == 1
    assert json.loads(res.output)["status"] == "unsigned"


def test_hmac_or_tampered_dossier_invalid(tmp_path, monkeypatch):
    path, pub = _dossier_file(tmp_path, monkeypatch, sign=True)
    data = json.loads(path.read_text(encoding="utf-8"))

    legacy = dict(data, signature_status="hmac-local")
    path.write_text(json.dumps(legacy), encoding="utf-8")
    res = _run(path, pub)
    assert res.exit_code == 1
    assert "UNSUPPORTED_SIGNATURE" in res.output

    data["section1"]["intended_purpose"] = "tampered"
    path.write_text(json.dumps(data), encoding="utf-8")
    res = _run(path, pub)
    assert res.exit_code == 1
    assert "CHECKSUM_MISMATCH" in res.output


def test_dossier_kind_listed_for_unknown_kind(tmp_path):
    path = tmp_path / "x.json"
    path.write_text("{}", encoding="utf-8")
    res = runner.invoke(app, ["verify", str(path), "--kind", "nope"])
    assert res.exit_code == 2
    assert "dossier" in res.output
    assert "dossier" in verify_mod._KINDS


def test_bad_input_exits_2(tmp_path):
    path = tmp_path / "x.json"
    path.write_text("not json", encoding="utf-8")
    assert _run(path, None).exit_code == 2
    assert _run(tmp_path / "missing.json", None).exit_code == 2
