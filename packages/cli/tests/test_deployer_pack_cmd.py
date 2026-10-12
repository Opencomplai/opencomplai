"""SU-21b: `deployer-pack build`, `verify --kind deployer-pack` and the pushed envelope."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import jsonschema
import pytest
from opencomplai_cli import main
from opencomplai_cli.commands import deployer_pack as cmd
from opencomplai_cli.main import app
from opencomplai_cli.publish import prepare_scan_status_artifact
from opencomplai_core.deployer_pack import build_pack, with_pack_summary
from opencomplai_core.instructions_for_use import generate_instructions_for_use
from opencomplai_core.models import ScanResult, ScanStatusArtifact, SystemManifest
from opencomplai_core.signing import canonical_json_bytes, generate_keypair
from typer.testing import CliRunner

runner = CliRunner()
SENTINEL = "SENTINEL-purpose-91c2"
SENTINEL_SYSTEM = "SENTINEL-system-44ab"
INGEST_SCHEMA = (
    Path(__file__).resolve().parents[3]
    / "dashboard-saas"
    / "schemas"
    / "first_scan_status.schema.json"
)


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Chdir to tmp_path, no env key, `main._SIGNING_KEY` at a missing file."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SIGNING_KEY_PRIVATE", raising=False)
    monkeypatch.setattr(main, "_SIGNING_KEY", tmp_path / "nokey" / "signing.key")
    monkeypatch.setattr(main, "_SIGNING_PUB", tmp_path / "nokey" / "signing.pub")
    monkeypatch.setattr(cmd, "_today", lambda: "2026-10-07")
    return tmp_path


def _instructions(tmp_path: Path, system_id: str = "sys-1") -> Path:
    doc = generate_instructions_for_use(
        SystemManifest(
            system_id=system_id, intended_purpose=SENTINEL, commit_ref="abc1234"
        ),
        generated_at="2026-10-07T00:00:00Z",
    )
    path = tmp_path / "instructions_for_use.json"
    path.write_text(doc.model_dump_json(indent=2), encoding="utf-8")
    return path


def _keys(tmp_path: Path, monkeypatch, name: str = "keys") -> Path:
    key_dir = tmp_path / name
    generate_keypair(key_dir)
    monkeypatch.setattr(main, "_SIGNING_KEY", key_dir / "signing.key")
    return key_dir / "signing.pub"


def _build(tmp_path: Path, *args: str, out: str = "out"):
    return runner.invoke(
        app,
        [
            "deployer-pack",
            "build",
            "--instructions",
            str(_instructions(tmp_path)),
            "--output-dir",
            str(tmp_path / out),
            *args,
        ],
    )


def _only_pack(directory: Path) -> Path:
    files = list(directory.iterdir())
    assert len(files) == 1
    return files[0]


def _expected_hash(pack: dict) -> str:
    body = {k: v for k, v in pack.items() if k != "integrity"}
    return hashlib.sha256(canonical_json_bytes(body)).hexdigest()


def _verify(path: Path, pub: Path | None = None):
    args = ["verify", str(path), "--kind", "deployer-pack"]
    if pub is not None:
        args += ["--pub-key", str(pub)]
    return runner.invoke(app, args)


def test_build_writes_pack_and_reports_hash(env):
    human = _build(env)
    assert human.exit_code == 0, human.output
    pack_file = _only_pack(env / "out")
    pack = json.loads(pack_file.read_text(encoding="utf-8"))
    digest = _expected_hash(pack)
    assert pack_file.name == f"deployer_pack_{digest[:12]}.json"
    assert pack["integrity"]["pack_sha256"] == digest
    assert digest in human.output.replace("\n", "")

    as_json = _build(env, "-o", "json", out="out2")
    assert as_json.exit_code == 0, as_json.output
    reported = json.loads(as_json.stdout)
    assert reported["pack_sha256"] == digest
    assert _only_pack(env / "out2").name == pack_file.name


def test_build_sign_without_key_exits_2_and_writes_nothing(env):
    result = _build(env, "--sign")
    assert result.exit_code == 2, result.output
    out = env / "out"
    assert not out.exists() or not any(out.iterdir())


def test_build_rejects_non_ifu_json_exit_2_and_writes_nothing(env):
    bad = env / "bad.json"
    bad.write_text('{"x": 1}', encoding="utf-8")
    result = runner.invoke(
        app,
        ["deployer-pack", "build", "--instructions", str(bad),
         "--system-id", "s", "--output-dir", str(env / "out")],
    )  # fmt: skip
    assert result.exit_code == 2, result.output
    assert not (env / "out").exists()


def test_build_twice_same_day_is_byte_identical(env, monkeypatch):
    _keys(env, monkeypatch)
    assert _build(env, "--sign", out="a").exit_code == 0
    assert _build(env, "--sign", out="b").exit_code == 0
    a, b = _only_pack(env / "a"), _only_pack(env / "b")
    assert a.name == b.name
    assert a.read_bytes() == b.read_bytes()


def test_verify_kind_accepts_signed_pack(env, monkeypatch):
    pub = _keys(env, monkeypatch)
    assert _build(env, "--sign").exit_code == 0
    result = _verify(_only_pack(env / "out"), pub)
    assert result.exit_code == 0, result.output
    assert "verified" in result.output


def test_verify_kind_detects_tampered_content(env, monkeypatch):
    pub = _keys(env, monkeypatch)
    assert _build(env, "--sign").exit_code == 0
    path = _only_pack(env / "out")
    pack = json.loads(path.read_text(encoding="utf-8"))
    pack["content"]["points"][0]["content"] = "tampered"
    path.write_text(json.dumps(pack), encoding="utf-8")
    result = _verify(path, pub)
    assert result.exit_code == 1
    assert "INVALID" in result.output


def test_verify_kind_reports_unsigned_distinctly(env):
    assert _build(env).exit_code == 0
    result = _verify(_only_pack(env / "out"))
    assert result.exit_code == 1
    assert "unsigned" in result.output
    assert "INVALID" not in result.output


def test_verify_kind_wrong_key_exits_1(env, monkeypatch, tmp_path):
    _keys(env, monkeypatch)
    assert _build(env, "--sign").exit_code == 0
    other_pub = _keys(env, monkeypatch, "other")
    result = _verify(_only_pack(env / "out"), other_pub)
    assert result.exit_code == 1
    assert "INVALID" in result.output


def test_verify_kind_rejects_non_pack_json_exit_2(env):
    path = env / "x.json"
    path.write_text('{"a": 1}', encoding="utf-8")
    assert _verify(path).exit_code == 2
    path.write_text("not json", encoding="utf-8")
    assert _verify(path).exit_code == 2
    assert _verify(env / "missing.json").exit_code == 2


def _pack_dir_with_sentinels(tmp_path: Path) -> Path:
    doc = json.loads(_instructions(tmp_path, SENTINEL_SYSTEM).read_text("utf-8"))
    pack = build_pack(
        doc,
        system_id=SENTINEL_SYSTEM,
        issued_on="2026-10-07",
        generator_version="1",
    )
    pack_dir = tmp_path / "deployer-pack"
    pack_dir.mkdir()
    digest = pack.integrity.pack_sha256
    (pack_dir / f"deployer_pack_{digest[:12]}.json").write_text(
        pack.model_dump_json(), encoding="utf-8"
    )
    return pack_dir


def test_pushed_envelope_contains_no_pack_text(tmp_path):
    artifact = ScanStatusArtifact(
        install_id="i",
        system_id="s",
        commit_ref="a" * 40,
        result=ScanResult.PASS,
        rationale_hash="sha256:a",
        duration_ms=1,
    )
    with_summary = with_pack_summary(artifact, _pack_dir_with_sentinels(tmp_path))
    envelope = prepare_scan_status_artifact(
        json.loads(with_summary.model_dump_json()), commit_env={}
    )
    text = json.dumps(envelope)
    assert SENTINEL not in text
    assert SENTINEL_SYSTEM not in text
    assert '"content"' not in text
    assert "system_id" not in json.dumps(envelope["summaries"])
    assert envelope["summaries"]["packs"]["issued"] == 1
    if INGEST_SCHEMA.exists():
        jsonschema.validate(envelope, json.loads(INGEST_SCHEMA.read_text("utf-8")))


def _check(tmp_path: Path, monkeypatch) -> dict:
    monkeypatch.setenv("OPENCOMPLAI_STATE_DIR", str(tmp_path / "state"))
    for var in ("OPENCOMPLAI_API_URL", "OPENCOMPLAI_VAULT_URL", "GITHUB_SHA"):
        monkeypatch.delenv(var, raising=False)
    manifest = tmp_path / "system-manifest.json"
    manifest.write_text(
        SystemManifest(
            system_id="gate-sys",
            intended_purpose="customer support chatbot",
            compliance_target="EU_AI_ACT",
            high_risk_presumption=False,
            commit_ref="HEAD",
        ).model_dump_json(),
        encoding="utf-8",
    )
    result = runner.invoke(
        app,
        ["check", "--manifest", str(manifest), "--repo-root", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    return json.loads((tmp_path / "compliance-artifact.json").read_text("utf-8"))


def test_check_without_pack_dir_is_unchanged(env, monkeypatch):
    assert "summaries" not in _check(env, monkeypatch)


def test_check_with_pack_dir_adds_packs_summary(env, monkeypatch):
    _pack_dir_with_sentinels(env)
    raw = _check(env, monkeypatch)
    assert raw["summaries"]["packs"]["issued"] == 1
    assert SENTINEL_SYSTEM not in json.dumps(raw)


def _manifest(tmp_path: Path, **extra) -> Path:
    """The deployer's own manifest: a system id different from the provider's `sys-1`."""
    path = tmp_path / "system-manifest.json"
    payload = SystemManifest(
        system_id="deployer-sys", intended_purpose="support", commit_ref="HEAD"
    ).model_dump(mode="json")
    path.write_text(json.dumps({**payload, **extra}, indent=2), encoding="utf-8")
    return path


def _import(path: Path, manifest: Path, *args: str):
    return runner.invoke(
        app,
        ["deployer-pack", "import", str(path), "--manifest", str(manifest), *args],
    )


def _tamper(path: Path) -> None:
    pack = json.loads(path.read_text(encoding="utf-8"))
    pack["content"]["points"][0]["content"] = "tampered"
    path.write_text(json.dumps(pack), encoding="utf-8")


def test_import_signed_pack_records_reference(env, monkeypatch):
    pub = _keys(env, monkeypatch)
    assert _build(env, "--sign").exit_code == 0
    path = _only_pack(env / "out")
    pack = json.loads(path.read_text(encoding="utf-8"))
    manifest = _manifest(env)

    result = _import(path, manifest, "--pub-key", str(pub))
    assert result.exit_code == 0, result.output
    evidence = json.loads(manifest.read_text(encoding="utf-8"))["imported_evidence"]
    key = f"deployer_pack:{pack['integrity']['pack_sha256'][:12]}"
    assert list(evidence) == [key]
    assert evidence[key] == {
        "source": "deployer_pack",
        "status": "imported_pack",
        "source_file": path.name,
        "pack_sha256": pack["integrity"]["pack_sha256"],
        "provider_system_id": "sys-1",
        "verification": "verified",
        "signer_key_id": hashlib.sha256(pub.read_bytes()).hexdigest()[:16],
        "imported_on": "2026-10-07",
    }


def test_import_unsigned_pack_recorded_as_unsigned(env):
    assert _build(env).exit_code == 0
    manifest = _manifest(env)
    result = _import(_only_pack(env / "out"), manifest)
    assert result.exit_code == 0, result.output
    assert "unsigned" in result.output
    (entry,) = json.loads(manifest.read_text(encoding="utf-8"))[
        "imported_evidence"
    ].values()
    assert entry["verification"] == "unsigned"
    assert entry["signer_key_id"] is None


def test_import_tampered_pack_refused_and_nothing_written(env, monkeypatch):
    pub = _keys(env, monkeypatch)
    assert _build(env, "--sign").exit_code == 0
    path = _only_pack(env / "out")
    _tamper(path)
    manifest = _manifest(env)
    before = manifest.read_bytes()
    result = _import(path, manifest, "--pub-key", str(pub))
    assert result.exit_code == 2, result.output
    assert manifest.read_bytes() == before


def test_import_signed_pack_without_key_exits_2(env, monkeypatch):
    _keys(env, monkeypatch)
    assert _build(env, "--sign").exit_code == 0
    manifest = _manifest(env)
    before = manifest.read_bytes()
    result = _import(_only_pack(env / "out"), manifest)
    assert result.exit_code == 2, result.output
    assert manifest.read_bytes() == before


def test_import_twice_is_idempotent(env, monkeypatch):
    pub = _keys(env, monkeypatch)
    assert _build(env, "--sign").exit_code == 0
    path = _only_pack(env / "out")
    manifest = _manifest(env)
    assert _import(path, manifest, "--pub-key", str(pub)).exit_code == 0
    first = manifest.read_bytes()
    monkeypatch.setattr(cmd, "_today", lambda: "2026-10-08")
    again = _import(path, manifest, "--pub-key", str(pub), "-o", "json")
    assert again.exit_code == 0, again.output
    assert json.loads(again.stdout)["recorded"] is False
    assert manifest.read_bytes() == first


def test_import_missing_manifest_exits_2_and_creates_nothing(env):
    assert _build(env).exit_code == 0
    manifest = env / "absent.json"
    result = _import(_only_pack(env / "out"), manifest)
    assert result.exit_code == 2, result.output
    assert not manifest.exists()


def test_import_preserves_other_manifest_keys(env):
    assert _build(env).exit_code == 0
    manifest = _manifest(env, x_local_note="keep me", operator_role="deployer")
    before = json.loads(manifest.read_text(encoding="utf-8"))
    assert _import(_only_pack(env / "out"), manifest).exit_code == 0
    after = json.loads(manifest.read_text(encoding="utf-8"))
    assert after.pop("imported_evidence")
    assert after == before


def test_import_json_output_shape(env):
    assert _build(env).exit_code == 0
    manifest = _manifest(env)
    result = _import(_only_pack(env / "out"), manifest, "-o", "json")
    assert result.exit_code == 0, result.output
    out = json.loads(result.stdout)
    assert set(out) == {
        "pack_id",
        "pack_sha256",
        "provider_system_id",
        "verification",
        "signer_key_id",
        "manifest",
        "recorded",
    }
    assert out["pack_id"] == out["pack_sha256"][:12]
    assert out["verification"] == "unsigned"
    assert out["recorded"] is True
