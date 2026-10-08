"""examples/gate-demo: the five demo directories exit 3, 4, 1, 1, 0 under `check`.

Each demo is copied to tmp_path and run with isolated state, so nothing reads the
real home and `compliance-artifact.json` never lands in the repo (T11). The
accepted demo's record is created at run time with a throw-away key.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from opencomplai_cli import main
from opencomplai_core.models import SystemManifest
from opencomplai_core.signing import generate_keypair
from typer.testing import CliRunner

runner = CliRunner()
ROOT = Path(__file__).resolve().parents[3]
DEMOS = ROOT / "examples" / "gate-demo"
ART6 = "EU_AIA_ART6_HIGH_RISK"
TRAP_ARGS = ["--change-context", "model_retrain"]


@pytest.fixture
def demo(tmp_path: Path, monkeypatch):
    """Return copy(name) -> demo dir under tmp_path, with the environment isolated."""
    monkeypatch.chdir(tmp_path)
    for var in (
        "SIGNING_KEY_PRIVATE",
        "OPENCOMPLAI_TRUSTED_KEY_IDS",
        "OPENCOMPLAI_API_URL",
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

    def copy(name: str) -> Path:
        dest = tmp_path / "work" / name
        shutil.copytree(DEMOS / name, dest)
        return dest

    return copy


def _check(path: Path, *extra: str):
    manifest = path / "system-manifest.json"
    return runner.invoke(
        main.app, ["check", "-m", str(manifest), "--repo-root", str(path), *extra]
    )


def _failed() -> list[str]:
    # `check` writes the artifact into the CWD (tmp_path), not the demo dir.
    artifact = json.loads((Path.cwd() / "compliance-artifact.json").read_text("utf-8"))
    return artifact["failed_controls"]


def _accept(path: Path, tmp_path: Path) -> None:
    generate_keypair(tmp_path / "keys")
    result = runner.invoke(
        main.app,
        [
            "accept",
            "-m",
            str(path / "system-manifest.json"),
            "--accepted-by",
            "demo-reviewer",
            "--statement",
            "Illustrative sandbox acceptance",
            "--repo-root",
            str(path),
            "--key",
            str(tmp_path / "keys" / "signing.key"),
        ],
    )
    assert result.exit_code == 0, result.output


@pytest.mark.parametrize(
    ("name", "extra", "expected"),
    [
        ("prohibited", [], 3),
        ("trap", TRAP_ARGS, 4),
        ("high-risk", [], 1),
        ("accepted", [], 1),
        ("limited", [], 0),
    ],
)
def test_gate_demo_exit_codes(demo, tmp_path, name, extra, expected) -> None:
    path = demo(name)
    if name == "accepted":
        _accept(path, tmp_path)
    result = _check(path, *extra)
    assert result.exit_code == expected, result.output


def test_accepted_demo_without_acceptance_fails(demo) -> None:
    path = demo("accepted")
    assert _check(path).exit_code == 1


def test_accepted_demo_acceptance_clears_art6_only(demo, tmp_path) -> None:
    path = demo("accepted")
    assert _check(path).exit_code == 1
    assert ART6 in _failed()

    _accept(path, tmp_path)
    result = _check(path)
    assert result.exit_code == 1, result.output
    failed = _failed()
    assert not [c for c in failed if "ART6" in c or c == "Art. 6"], failed
    assert failed, "other EU obligations stay Missing after acceptance"


def test_every_example_manifest_validates() -> None:
    manifests = sorted((ROOT / "examples").glob("**/system-manifest.json"))
    for manifest in manifests:
        SystemManifest.model_validate_json(manifest.read_text("utf-8"))
    found = {m.parent.name for m in manifests if m.parent.parent == DEMOS}
    assert found == {"prohibited", "trap", "high-risk", "accepted", "limited"}


def test_readmes_point_at_gate_demo() -> None:
    for rel in ("README.md", "docs/src/index.md"):
        text = (ROOT / rel).read_text("utf-8")
        assert "examples/gate-demo" in text, rel
        sandbox = [ln for ln in text.splitlines() if "(Sandbox)" in ln]
        assert sandbox, rel
        assert all("examples/sample-system" not in ln for ln in sandbox), rel


def test_demo_readmes_have_no_literal_backslash_n() -> None:
    # a literal backslash-n in a copy-paste command splits it; line continuations are a lone backslash
    for readme in (ROOT / "examples" / "gate-demo").rglob("README.md"):
        assert "\\n" not in readme.read_text("utf-8"), readme
