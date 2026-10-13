"""`check` lists the digests of the files it read or wrote in `evidence_hashes`.

Local mode only: the manifest, and with `--scan` / `--sample-set` the scan and
eval sidecar reports, each as `sha256:<hex>` over the LF-folded bytes. Hashes
only, never content. The digests are in the artifact before it is signed.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from opencomplai_cli import main
from opencomplai_cli.check_signing import with_input_hashes
from opencomplai_cli.main import app
from opencomplai_core.models import (
    CorroborationReport,
    EvalReport,
    ScanResult,
    ScanStatusArtifact,
    SystemManifest,
)
from opencomplai_core.signing import generate_keypair, verify_artifact
from typer.testing import CliRunner

runner = CliRunner()


def _digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


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
            system_id="inputs-sys",
            intended_purpose="customer support chatbot",
            compliance_target="EU_AI_ACT",
            high_risk_presumption=False,
            commit_ref="HEAD",
        ).model_dump_json(),
        encoding="utf-8",
    )
    return manifest_file, key_dir / "signing.pub"


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("print('hello')\n", encoding="utf-8")
    return repo


def _written(tmp_path: Path) -> ScanStatusArtifact:
    return ScanStatusArtifact.model_validate_json(
        (tmp_path / "compliance-artifact.json").read_text(encoding="utf-8")
    )


def _sidecar_digest(tmp_path: Path, name: str) -> str:
    return _digest((tmp_path / name).read_bytes())


def _artifact(hashes: list[str]) -> ScanStatusArtifact:
    return ScanStatusArtifact(
        install_id="i",
        system_id="s",
        commit_ref="abc1234",
        result=ScanResult.PASS,
        evidence_hashes=hashes,
        rationale_hash="0" * 64,
        duration_ms=1,
    )


def test_with_input_hashes_order_dedupe_and_none_skipped():
    class _Report:
        def __init__(self, text: str) -> None:
            self.text = text

        def model_dump_json(self, indent: int | None = None) -> str:
            return self.text

    scan = _Report('{"scan": 1}')
    ev = _Report('{"eval": 1}')
    art = _artifact(["keep-me"])
    got = with_input_hashes(art, manifest_bytes=b"m", scan_report=scan, eval_report=ev)
    assert got.evidence_hashes == [
        "keep-me",
        _digest(b"m"),
        _digest(b'{"scan": 1}'),
        _digest(b'{"eval": 1}'),
    ]
    # Every input None: the same object comes back.
    none = with_input_hashes(
        art, manifest_bytes=None, scan_report=None, eval_report=None
    )
    assert none is art
    # Only the manifest, and a digest already present is not repeated.
    seeded = _artifact([_digest(b"m")])
    again = with_input_hashes(
        seeded, manifest_bytes=b"m", scan_report=None, eval_report=None
    )
    assert again is seeded
    only_eval = with_input_hashes(
        art, manifest_bytes=None, scan_report=None, eval_report=ev
    )
    assert only_eval.evidence_hashes == ["keep-me", _digest(b'{"eval": 1}')]


def test_crlf_and_lf_inputs_hash_the_same():
    lf = with_input_hashes(
        _artifact([]), manifest_bytes=b'{"a":\n1}', scan_report=None, eval_report=None
    )
    crlf = with_input_hashes(
        _artifact([]),
        manifest_bytes=b'{"a":\r\n1}',
        scan_report=None,
        eval_report=None,
    )
    assert lf.evidence_hashes == crlf.evidence_hashes
    assert lf.evidence_hashes[0].startswith("sha256:")
    assert len(lf.evidence_hashes[0]) == len("sha256:") + 64


def test_local_check_lists_manifest_digest(tmp_path, monkeypatch):
    manifest_file, _ = _setup(tmp_path, monkeypatch)

    result = runner.invoke(app, ["check", "--manifest", str(manifest_file)])
    assert result.exit_code == 0, result.output

    artifact = _written(tmp_path)
    assert artifact.manifest_sha256
    digest = f"sha256:{artifact.manifest_sha256}"
    assert digest in artifact.evidence_hashes
    assert digest == _digest(manifest_file.read_bytes())


def test_scan_adds_report_hash_and_sidecar_digest(tmp_path, monkeypatch):
    manifest_file, _ = _setup(tmp_path, monkeypatch)
    repo = _repo(tmp_path)

    result = runner.invoke(
        app,
        ["check", "--manifest", str(manifest_file), "--repo-root", str(repo), "--scan"],
    )
    assert result.exit_code == 0, result.output

    artifact = _written(tmp_path)
    assert artifact.scan_summary is not None
    assert artifact.scan_summary.report_hash in artifact.evidence_hashes
    sidecar = _sidecar_digest(tmp_path, "scan-report.json")
    assert sidecar in artifact.evidence_hashes
    # The sidecar digest is a distinct entry from the canonical report hash.
    assert sidecar != artifact.scan_summary.report_hash
    assert f"sha256:{artifact.manifest_sha256}" in artifact.evidence_hashes
    # The sidecar is the model dump the digest was taken over.
    report = CorroborationReport.model_validate_json(
        (tmp_path / "scan-report.json").read_text(encoding="utf-8")
    )
    assert _digest(report.model_dump_json(indent=2).encode("utf-8")) == sidecar


def test_eval_sidecar_digest_listed(tmp_path, monkeypatch):
    manifest_file, _ = _setup(tmp_path, monkeypatch)
    sample = tmp_path / "set.json"
    sample.write_text(
        json.dumps(
            {"eval_set_id": "s1", "system_id": "inputs-sys", "prompts": ["hello"]}
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app, ["check", "--manifest", str(manifest_file), "--sample-set", str(sample)]
    )
    assert result.exit_code == 0, result.output

    artifact = _written(tmp_path)
    assert _sidecar_digest(tmp_path, "eval-report.json") in artifact.evidence_hashes
    report = EvalReport.model_validate_json(
        (tmp_path / "eval-report.json").read_text(encoding="utf-8")
    )
    assert report.results
    assert all(r.evidence_hash in artifact.evidence_hashes for r in report.results)


def test_signed_check_with_input_hashes_verifies(tmp_path, monkeypatch):
    manifest_file, pub_key = _setup(tmp_path, monkeypatch)
    repo = _repo(tmp_path)

    result = runner.invoke(
        app,
        [
            "check",
            "--manifest",
            str(manifest_file),
            "--repo-root",
            str(repo),
            "--scan",
            "--sign",
        ],
    )
    assert result.exit_code == 0, result.output

    artifact = _written(tmp_path)
    assert artifact.signature
    assert len(artifact.evidence_hashes) > 0
    assert _sidecar_digest(tmp_path, "scan-report.json") in artifact.evidence_hashes
    assert verify_artifact(artifact, pub_key) is True


def test_service_mode_hashes_unchanged(tmp_path, monkeypatch):
    manifest_file, _ = _setup(tmp_path, monkeypatch)
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

    monkeypatch.setattr(main, "_call_service", fake_call_service)
    monkeypatch.setattr(main, "_emit_event", lambda *a, **kw: None)

    result = runner.invoke(app, ["check", "--manifest", str(manifest_file)])
    assert result.exit_code == 0, result.output

    artifact = _written(tmp_path)
    assert artifact.manifest_sha256
    assert f"sha256:{artifact.manifest_sha256}" not in artifact.evidence_hashes
