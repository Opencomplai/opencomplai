"""`opencomplai export --sign` and `opencomplai verify --kind evidence-package`."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import pytest
from opencomplai_cli import main
from opencomplai_cli.main import app
from opencomplai_core import signing
from opencomplai_core.evidence_package import build_evidence_package
from opencomplai_core.models import (
    ArticleGapSource,
    ArticleGapStatus,
    GapReport,
    GapStatus,
    ScanResult,
    ScanStatusArtifact,
)
from opencomplai_core.signing import generate_keypair
from typer.testing import CliRunner

runner = CliRunner()
_ROOT = Path(__file__).resolve().parents[3]


def _artifact() -> ScanStatusArtifact:
    return ScanStatusArtifact(
        install_id="i",
        system_id="sys-1",
        commit_ref="abc1234",
        result=ScanResult.CONTROL_FAIL,
        failed_controls=["C-1"],
        evidence_hashes=["a" * 64],
        rationale_hash="0" * 64,
        duration_ms=5,
        rule_set_version="2026.10",
        cli_version="0.9.1",
        tree_sha256="d" * 64,
        tree_dirty=True,
        gap_report=GapReport(
            system_id="sys-1",
            commit_ref="abc1234",
            generated_at="2026-10-06T00:00:00+00:00",
            articles=[
                ArticleGapStatus(
                    article="Art. 9",
                    status=GapStatus.MISSING,
                    source=ArticleGapSource.RULE,
                    evidence_ref="R-9",
                    confidence=0.4,
                ),
                ArticleGapStatus(
                    article="Art. 10",
                    status=GapStatus.MET,
                    source=ArticleGapSource.EVALUATOR,
                    evidence_ref="none",
                ),
            ],
        ),
    )


@pytest.fixture
def env(tmp_path, monkeypatch):
    """A signed artifact, a keypair wired into main, and no env key."""
    monkeypatch.delenv("SIGNING_KEY_PRIVATE", raising=False)
    keys = tmp_path / "keys"
    generate_keypair(keys)
    monkeypatch.setattr(main, "_SIGNING_KEY", keys / "signing.key")
    monkeypatch.setattr(main, "_SIGNING_PUB", keys / "signing.pub")
    art = _artifact()
    art.signature = signing.sign_artifact(art, keys / "signing.key")
    src = tmp_path / "compliance-artifact.json"
    src.write_text(art.model_dump_json(indent=2), encoding="utf-8")
    return src, keys


def _export(src: Path, *args: str):
    return runner.invoke(app, ["export", str(src), *args])


def _signed_file(env, tmp_path: Path) -> Path:
    src, _ = env
    out = tmp_path / "package.json"
    res = _export(src, "--sign", "--out", str(out))
    assert res.exit_code == 0, res.output
    return out


def _verify(path: Path, pub: Path | None = None, *extra: str):
    args = ["verify", str(path), "--kind", "evidence-package", *extra]
    if pub is not None:
        args += ["--pub-key", str(pub)]
    return runner.invoke(app, args)


def test_sign_round_trip_verifies(env, tmp_path):
    out = _signed_file(env, tmp_path)
    pkg = json.loads(out.read_text(encoding="utf-8"))
    assert pkg["package_signature"]["domain"] == "evidence-package"
    assert pkg["package_signature"]["algorithm"] == "ed25519"
    res = _verify(out, env[1] / "signing.pub")
    assert res.exit_code == 0, res.output
    assert "verified" in res.output
    # The default public key (main._SIGNING_PUB) works with no --pub-key.
    assert _verify(out).exit_code == 0


def _set(path, value):
    def apply(pkg):
        node = pkg
        for part in path[:-1]:
            node = node[part]
        node[path[-1]] = value

    return apply


@pytest.mark.parametrize(
    "mutate",
    [
        _set(["identity", "system_id"], "someone-else"),
        _set(["articles", 0, "status"], "met"),
        _set(["evidence_hashes", 0], "b" * 64),
        _set(["artifact", "system_id"], "someone-else"),
        _set(["package_signature", "signature"], "AAAA" * 22 + "AA=="),
    ],
    ids=[
        "identity.system_id",
        "article.status",
        "evidence_hashes",
        "artifact.system_id",
        "signature",
    ],
)
def test_tampering_any_field_fails_verify(env, tmp_path, mutate):
    out = _signed_file(env, tmp_path)
    pkg = json.loads(out.read_text(encoding="utf-8"))
    mutate(pkg)
    bad = tmp_path / "tampered.json"
    bad.write_text(json.dumps(pkg, indent=2) + "\n", encoding="utf-8")
    res = _verify(bad, env[1] / "signing.pub", "--output", "json")
    assert res.exit_code == 1, res.output
    assert json.loads(res.stdout)["status"] == "invalid"


def test_embedded_artifact_still_verbatim_and_verifies(env, tmp_path):
    src, keys = env
    out = _signed_file(env, tmp_path)
    pkg = json.loads(out.read_text(encoding="utf-8"))
    assert pkg["artifact"] == json.loads(src.read_text(encoding="utf-8"))
    embedded = tmp_path / "embedded.json"
    res = _export(src, "--sign", "--artifact-out", str(embedded), "--out", str(out))
    assert res.exit_code == 0, res.output
    ok = runner.invoke(
        app,
        [
            "verify",
            str(embedded),
            "--kind",
            "artifact",
            "--pub-key",
            str(keys / "signing.pub"),
        ],
    )
    assert ok.exit_code == 0, ok.output


def test_unsigned_package_bytes_are_unchanged(env, tmp_path):
    src, _ = env
    res = _export(src)
    assert res.exit_code == 0, res.output
    assert "package_signature" not in json.loads(res.stdout)
    pkg = build_evidence_package(json.loads(src.read_text(encoding="utf-8")))
    assert res.stdout == pkg.model_dump_json(indent=2) + "\n"
    assert "not signed; only the embedded artifact is" in res.stdout


def test_sign_without_key_exits_2_and_writes_nothing(env, tmp_path, monkeypatch):
    src, _ = env
    monkeypatch.setattr(main, "_SIGNING_KEY", tmp_path / "missing" / "signing.key")
    out = tmp_path / "package.json"
    embedded = tmp_path / "embedded.json"
    res = _export(src, "--sign", "--out", str(out), "--artifact-out", str(embedded))
    assert res.exit_code == 2, res.output
    assert not out.exists()
    assert not embedded.exists()
    assert "opencomplai init" in res.output
    assert "SIGNING_KEY_PRIVATE" in res.output


def test_sign_with_csv_exits_2(env, tmp_path):
    src, _ = env
    out = tmp_path / "package.csv"
    res = _export(src, "--sign", "--format", "csv", "--out", str(out))
    assert res.exit_code == 2, res.output
    assert not out.exists()
    assert "CSV carries no signature" in res.output


def test_key_option_signs_with_that_key(env, tmp_path, monkeypatch):
    src, _ = env
    other = tmp_path / "other"
    generate_keypair(other)
    out = tmp_path / "package.json"
    res = _export(src, "--sign", "--key", str(other / "signing.key"), "--out", str(out))
    assert res.exit_code == 0, res.output
    assert _verify(out, other / "signing.pub").exit_code == 0
    assert _verify(out).exit_code == 1  # the default key is not the signer


def test_verify_unsigned_package_exits_1_unsigned(env, tmp_path):
    src, _ = env
    out = tmp_path / "package.json"
    assert _export(src, "--out", str(out)).exit_code == 0
    res = _verify(out, None, "--output", "json")
    assert res.exit_code == 1, res.output
    assert json.loads(res.stdout)["status"] == "unsigned"


def test_verify_wrong_key_exits_1(env, tmp_path):
    out = _signed_file(env, tmp_path)
    other = tmp_path / "other"
    generate_keypair(other)
    res = _verify(out, other / "signing.pub", "--output", "json")
    assert res.exit_code == 1, res.output
    assert json.loads(res.stdout)["status"] == "invalid"


def test_verify_bad_json_exits_2(env, tmp_path):
    out = _signed_file(env, tmp_path)
    broken = tmp_path / "broken.json"
    broken.write_bytes(out.read_bytes()[:-20])
    assert _verify(broken, env[1] / "signing.pub").exit_code == 2
    other = tmp_path / "other.json"
    other.write_text('{"hello": "world"}', encoding="utf-8")
    assert _verify(other, env[1] / "signing.pub").exit_code == 2
    assert _verify(tmp_path / "missing.json", env[1] / "signing.pub").exit_code == 2
    nokey = _verify(out, tmp_path / "no.pub")
    assert nokey.exit_code == 2


def test_csv_new_columns_values(env):
    src, _ = env
    res = _export(src, "--format", "csv")
    assert res.exit_code == 0, res.output
    rows = list(csv.reader(io.StringIO(res.stdout, newline="")))
    assert rows[0][9:] == ["tree_sha256", "tree_dirty", "signed", "verdict"]
    for row in rows[1:]:
        assert row[9:] == ["d" * 64, "true", "true", "control_fail"]
    unsigned = env[0].parent / "unsigned.json"
    raw = json.loads(env[0].read_text(encoding="utf-8"))
    raw.pop("signature")
    raw.pop("tree_sha256")
    raw.pop("tree_dirty")
    unsigned.write_text(json.dumps(raw), encoding="utf-8")
    rows = list(
        csv.reader(io.StringIO(_export(unsigned, "--format", "csv").stdout, newline=""))
    )
    assert rows[1][9:] == ["", "", "false", "control_fail"]


def test_docs_say_signed_only_with_sign():
    text = (_ROOT / "docs" / "src" / "cli" / "export.md").read_text(encoding="utf-8")
    assert "signed only with `--sign`" in text
    assert "The package is not signed" not in text
    assert "evidence-package" in (
        _ROOT / "docs" / "src" / "cli" / "verify.md"
    ).read_text(encoding="utf-8")
