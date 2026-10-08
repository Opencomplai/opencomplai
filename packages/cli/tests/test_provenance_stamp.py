"""SU-10b: `check` stamps the four provenance fields before signing."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import jsonschema
import pytest
from opencomplai_cli import main
from opencomplai_cli.check_signing import stamp_artifact
from opencomplai_cli.main import app
from opencomplai_cli.publish import envelope_signature, prepare_scan_status_artifact
from opencomplai_core.json_schemas import SCHEMA_VERSION
from opencomplai_core.models import ScanStatusArtifact, SystemManifest
from opencomplai_core.rules import RULE_SET_VERSION
from opencomplai_core.signing import generate_keypair, verify_artifact
from typer.testing import CliRunner

runner = CliRunner()
SCHEMA = (
    Path(__file__).resolve().parents[3]
    / "dashboard-saas"
    / "schemas"
    / "first_scan_status.schema.json"
)
_PROVENANCE = ("rule_set_version", "cli_version", "schema_version", "manifest_sha256")


@pytest.fixture
def signed_check(tmp_path, monkeypatch):
    """Run `check --sign` in tmp_path; return (artifact dict, manifest, pubkey)."""
    monkeypatch.chdir(tmp_path)
    for var in ("OPENCOMPLAI_API_URL", "OPENCOMPLAI_VAULT_URL", "SIGNING_KEY_PRIVATE"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("OPENCOMPLAI_STATE_DIR", str(tmp_path / "state"))
    key_dir = tmp_path / "keys"
    generate_keypair(key_dir)
    monkeypatch.setattr(main, "_SIGNING_KEY", key_dir / "signing.key")
    manifest = tmp_path / "system-manifest.json"
    manifest.write_text(
        SystemManifest(
            system_id="prov-sys",
            intended_purpose="customer support chatbot",
            compliance_target="EU_AI_ACT",
            high_risk_presumption=False,
            commit_ref="HEAD",
        ).model_dump_json(),
        encoding="utf-8",
    )
    result = runner.invoke(app, ["check", "--manifest", str(manifest), "--sign"])
    assert result.exit_code == 0, result.output
    raw = json.loads((tmp_path / "compliance-artifact.json").read_text("utf-8"))
    return raw, manifest, key_dir / "signing.pub"


def test_check_stamps_provenance_before_signing(signed_check):
    raw, _, pub = signed_check
    assert all(raw.get(k) for k in _PROVENANCE)
    assert raw["rule_set_version"] == RULE_SET_VERSION
    assert raw["schema_version"] == SCHEMA_VERSION
    artifact = ScanStatusArtifact.model_validate(raw)
    assert verify_artifact(artifact, pub) is True
    # The signature covers the stamps: change one and it no longer verifies.
    tampered = artifact.model_copy(update={"rule_set_version": "0.0.0"})
    assert verify_artifact(tampered, pub) is False


def test_signature_survives_push_with_provenance(signed_check, tmp_path):
    raw, _, pub = signed_check
    prepared = prepare_scan_status_artifact(raw, repo_dir=tmp_path)
    assert all(prepared[k] == raw[k] for k in _PROVENANCE)
    assert raw["signature"]
    signature = envelope_signature(raw, prepared)
    assert signature == raw["signature"]
    # The surviving signature must still cover the provenance fields.
    pushed = ScanStatusArtifact.model_validate({**prepared, "signature": signature})
    assert verify_artifact(pushed, pub) is True


def test_stamped_artifact_validates_against_widened_schema(signed_check, tmp_path):
    if not SCHEMA.exists():
        pytest.skip("dashboard-saas schema not present")
    raw, _, _ = signed_check
    prepared = prepare_scan_status_artifact(raw, commit_env={"GITHUB_SHA": "c" * 40})
    jsonschema.validate(prepared, json.loads(SCHEMA.read_text("utf-8")))


def test_manifest_sha256_matches_file_bytes(signed_check):
    raw, manifest, _ = signed_check
    lf_bytes = manifest.read_bytes().replace(b"\r\n", b"\n")
    assert raw["manifest_sha256"] == hashlib.sha256(lf_bytes).hexdigest()


def test_manifest_sha256_is_line_ending_independent():
    base = ScanStatusArtifact(
        install_id="i",
        system_id="s",
        commit_ref="a" * 40,
        result="pass",
        rationale_hash="r",
        duration_ms=1,
    )
    now = datetime(2030, 1, 1, tzinfo=UTC)
    lf = stamp_artifact(base, now=now, manifest_bytes=b'{\n  "a": 1\n}')
    crlf = stamp_artifact(base, now=now, manifest_bytes=b'{\r\n  "a": 1\r\n}')
    assert lf.manifest_sha256 == crlf.manifest_sha256
    assert stamp_artifact(base, now=now).manifest_sha256 is None
