"""The CLI side of the Marketplace Action (Opencomplai/opencomplai-action), tested offline.

The Action lives in its own repository and its shell scripts are tested there. What
stays here is the contract with this repo: `check` honours the exact flag set the
Action's run.sh passes, the self-test workflow runs the pinned Action, and the docs
snippets keep pinning it to a commit SHA. No network, no real home.
"""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path

import pytest
import yaml
from opencomplai_cli import main
from opencomplai_core.signing import generate_keypair
from typer.testing import CliRunner

from .test_gate_demo import demo as gate_demo  # noqa: F401  (fixture)

runner = CliRunner()
ROOT = Path(__file__).resolve().parents[3]
ACTION_PAGE = ROOT / "docs" / "src" / "guides" / "github-action.md"
SELFTEST = ROOT / ".github" / "workflows" / "action-selftest.yml"
ACTION_USES = re.compile(r"Opencomplai/opencomplai-action@[0-9a-f]{40}")

# Mirrors Opencomplai/opencomplai-action run.sh: `sign: "true"` adds --sign-if-available,
# `with-gaps: "true"` adds --with-gaps, `strict: "true"` adds the five-flag strict preset.
SIGN_FLAGS = ["--sign-if-available"]
GAPS_FLAGS = ["--with-gaps"]
STRICT_FLAGS = [
    "--with-gaps",
    "--scan",
    "--fail-on",
    "major",
    "--require-exemption-record",
    "--sign-if-available",
]


def _action_check(demo_dir: Path, out: Path, *flags: str):
    """Run `check` the way run.sh does; `--repo-root` is the caller's `args` input."""
    out.mkdir()
    return runner.invoke(
        main.app,
        [
            "check",
            "--manifest",
            str(demo_dir / "system-manifest.json"),
            "--output-dir",
            str(out),
            "--summary-md",
            str(out / "summary.md"),
            "--sarif-output",
            str(out / "results.sarif"),
            *flags,
            "--repo-root",
            str(demo_dir),
        ],
    )


@pytest.fixture
def copy_demo(request: pytest.FixtureRequest):
    """copy(name) -> demo dir under tmp_path, with the environment isolated."""
    return request.getfixturevalue("gate_demo")


@pytest.mark.parametrize("flags", [[], STRICT_FLAGS], ids=["plain", "strict"])
@pytest.mark.parametrize(("name", "expected"), [("high-risk", 1), ("limited", 0)])
def test_action_flag_set_exit_codes_and_files(
    copy_demo, tmp_path: Path, name: str, expected: int, flags: list[str]
) -> None:
    out = tmp_path / "out"
    result = _action_check(copy_demo(name), out, *flags)
    assert result.exit_code == expected, result.output
    for written in ("summary.md", "results.sarif", "compliance-artifact.json"):
        assert (out / written).stat().st_size > 0, written


def test_action_flag_set_signed_with_gaps(
    copy_demo, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    generate_keypair(tmp_path / "keys")
    key = base64.b64encode((tmp_path / "keys" / "signing.key").read_bytes()).decode()
    monkeypatch.setenv("SIGNING_KEY_PRIVATE", key)
    out = tmp_path / "out"
    result = _action_check(copy_demo("limited"), out, *SIGN_FLAGS, *GAPS_FLAGS)
    assert result.exit_code == 0, result.output
    assert "Signed | `yes (key sha256:" in (out / "summary.md").read_text("utf-8")
    artifact = json.loads((out / "compliance-artifact.json").read_text("utf-8"))
    assert artifact["signature"]


_PINNED = re.compile(r"@(?:<40-hex commit SHA> # v1|[0-9a-f]{40} # v\S+)\s*$")


def test_action_uses_lines_are_pinned_to_a_commit_sha() -> None:
    files = [ROOT / "README.md", ACTION_PAGE]
    files += [p for p in (ROOT / "examples").rglob("*") if p.is_file()]
    uses = [
        (p.relative_to(ROOT).as_posix(), ln.strip())
        for p in files
        for ln in p.read_text("utf-8", errors="ignore").splitlines()
        if "uses: Opencomplai/opencomplai-action@" in ln
    ]
    assert any(f == "docs/src/guides/github-action.md" for f, _ in uses)
    bad = [(f, ln) for f, ln in uses if not _PINNED.search(ln)]
    assert not bad, bad


def test_docs_action_page_documents_strict_input() -> None:
    assert re.search(r"^\| `strict` ", ACTION_PAGE.read_text("utf-8"), re.M)


@pytest.mark.skipif(not SELFTEST.is_file(), reason="no self-test workflow in this tree")
def test_selftest_matrix_covers_all_five_demos() -> None:
    text = SELFTEST.read_text("utf-8")
    assert re.search(r"^permissions:", text, re.M)
    wf = yaml.safe_load(text)
    assert wf["permissions"] == {"contents": "read"}
    job = wf["jobs"]["gate-demo"]
    cells = {c["name"]: c for c in job["strategy"]["matrix"]["include"]}
    # accepted exits 1: the acceptance clears Art. 6 and the other EU obligations stay Missing
    assert {n: c["expect"] for n, c in cells.items()} == {
        "prohibited": "3",
        "trap": "4",
        "high-risk": "1",
        "accepted": "1",
        "limited": "0",
    }
    assert "--change-context model_retrain" in cells["trap"]["args"]
    uses = [s.get("uses", "") for s in job["steps"]]
    assert any(ACTION_USES.fullmatch(u) for u in uses), uses


def test_bogus_compliance_gate_example_is_gone() -> None:
    assert not (ROOT / ".github" / "workflows" / "compliance-gate.yml.example").exists()
    suffixes = {".md", ".yml", ".yaml", ".example", ".txt", ".json", ".sh"}
    files = [ROOT / "README.md"]
    for top in (".github", "docs", "examples"):
        files += [
            p
            for p in (ROOT / top).rglob("*")
            if p.is_file() and p.suffix in suffixes and "node_modules" not in p.parts
        ]
    hits = [
        p.relative_to(ROOT).as_posix()
        for p in files
        if "compliance-action@v1" in p.read_text("utf-8", errors="ignore")
    ]
    assert not hits, hits


@pytest.mark.skipif(not SELFTEST.is_file(), reason="no self-test workflow in this tree")
def test_selftest_asserts_artifact_file() -> None:
    text = SELFTEST.read_text("utf-8")
    assert "ARTIFACT: ${{ steps.gate.outputs.artifact-file }}" in text
    assert 'test -s "$ARTIFACT"' in text
    assert 'upload-artifact: "true"' in text


@pytest.mark.skipif(not SELFTEST.is_file(), reason="no self-test workflow in this tree")
def test_selftest_covers_sign_and_with_gaps() -> None:
    text = SELFTEST.read_text("utf-8")
    job = yaml.safe_load(text)["jobs"]["signed-with-gaps"]
    (step,) = [s for s in job["steps"] if ACTION_USES.fullmatch(str(s.get("uses", "")))]
    assert step["with"]["sign"] == "true"
    assert step["with"]["with-gaps"] == "true"
    # The workflow writes the backticks escaped inside double quotes so that
    # shellcheck stays quiet; normalise before matching.
    shell_text = text.replace("\\`", "`")
    assert "Signed | `no (unsigned artifact)`" in shell_text
    assert "Signed | `yes (key sha256:" in shell_text
