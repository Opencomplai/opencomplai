"""integrations/github-action: run.sh, comment.sh and action.yml, tested offline.

Every test calls the real shell scripts with shims on PATH: a fake ``uvx`` (the
real-fixture test's shim runs this checkout's CLI, never real uvx) and a fake
``gh`` (comment.sh never talks to GitHub). No network, no real home (T1, T7, T11).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from opencomplai_core.signing import generate_keypair

ROOT = Path(__file__).resolve().parents[3]
ACTION = ROOT / "integrations" / "github-action"
DEMOS = ROOT / "examples" / "gate-demo"
SELFTEST = ROOT / ".github" / "workflows" / "action-selftest.yml"
MARKER = "<!-- opencomplai-gate -->"
BASH = shutil.which("bash")
needs_bash = pytest.mark.skipif(BASH is None, reason="bash not found on PATH")

# Drops uvx's own arguments up to the bare `opencomplai`, then runs this checkout's CLI.
REAL_UVX = """#!/usr/bin/env bash
while [ "$1" != opencomplai ]; do shift; done
shift
exec "$OC_TEST_PY" -c 'import sys; from opencomplai_cli.main import app; sys.argv[0]="opencomplai"; app()' "$@"
"""

# Writes the summary/SARIF files named on its command line and exits with FAKE_EXIT.
FAKE_UVX = """#!/usr/bin/env bash
prev=""
for a in "$@"; do
  if [ "$prev" = --summary-md ] && [ "${FAKE_WRITE_SUMMARY:-1}" = 1 ]; then printf '## fake summary\\n' >"$a"; fi
  if [ "$prev" = --sarif-output ]; then printf '{}\\n' >"$a"; fi
  prev="$a"
done
echo "$@" >"$FAKE_ARGV"
exit "${FAKE_EXIT:-0}"
"""

# Records argv; keeps the last posted body so a later list call can find the marker.
FAKE_GH = """#!/usr/bin/env bash
echo "$*" >>"$GH_LOG"
body=""
for a in "$@"; do case "$a" in body=@*) body="${a#body=@}";; esac; done
case "$*" in
  *--paginate*) if [ -f "$GH_STATE" ] && grep -q opencomplai-gate "$GH_STATE"; then echo 777; fi;;
  *--method*) cp "$body" "$GH_STATE";;
esac
exit 0
"""


def _shim(directory: Path, name: str, text: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(text, encoding="utf-8", newline="\n")
    path.chmod(0o755)


def _env(tmp_path: Path, shims: Path, **extra: str) -> dict[str, str]:
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    env = dict(os.environ)
    for var in (
        "SIGNING_KEY_PRIVATE",
        "OPENCOMPLAI_TRUSTED_KEY_IDS",
        "OPENCOMPLAI_API_URL",
        "GITHUB_SHA",
        "CI_COMMIT_SHA",
    ):
        env.pop(var, None)
    env.update(
        HOME=str(home),
        USERPROFILE=str(home),
        OPENCOMPLAI_STATE_DIR=str(tmp_path / "state"),
        PATH=f"{shims}{os.pathsep}{env.get('PATH', '')}",
        OC_VERSION="0.9.0",
        OC_OUT_DIR=str(tmp_path / "out"),
        GITHUB_OUTPUT=str(tmp_path / "gh_output"),
        **extra,
    )
    return env


def _run_sh(tmp_path: Path, env: dict[str, str]) -> tuple[dict[str, str], Path]:
    done = subprocess.run(
        [BASH, (ACTION / "run.sh").as_posix()],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )
    assert done.returncode == 0, done.stdout + done.stderr  # run.sh never fails itself
    lines = (tmp_path / "gh_output").read_text("utf-8").splitlines()
    out = dict(line.split("=", 1) for line in lines)
    return out, Path(out["summary-file"])


@needs_bash
def test_run_sh_passes_exit_code_through(tmp_path: Path) -> None:
    for code in (0, 1, 3, 4):
        run = tmp_path / str(code)
        _shim(run / "shims", "uvx", FAKE_UVX)
        env = _env(
            run,
            run / "shims",
            FAKE_EXIT=str(code),
            FAKE_ARGV=str(run / "argv"),
            OC_MANIFEST="m.json",
            OC_WITH="./a\n./b",
            OC_ARGS="--change-context model_retrain",
        )
        out, summary = _run_sh(run, env)
        assert out["exit-code"] == str(code)
        assert summary.read_text("utf-8").startswith(MARKER + "\n## fake summary")
        assert out["sarif-file"].endswith("results.sarif")
        argv = (run / "argv").read_text("utf-8")
        assert argv.startswith(
            "--from opencomplai==0.9.0 --with ./a --with ./b opencomplai check"
        )
        assert "--manifest m.json" in argv
        assert "--change-context model_retrain" in argv


@needs_bash
def test_run_sh_fallback_body_when_no_summary(tmp_path: Path) -> None:
    _shim(tmp_path / "shims", "uvx", FAKE_UVX)
    env = _env(
        tmp_path,
        tmp_path / "shims",
        FAKE_EXIT="2",
        FAKE_WRITE_SUMMARY="0",
        FAKE_ARGV=str(tmp_path / "argv"),
    )
    out, summary = _run_sh(tmp_path, env)
    assert out["exit-code"] == "2"
    body = summary.read_text("utf-8")
    assert body.startswith(MARKER + "\n")
    assert "exit code 2" in body


@needs_bash
@pytest.mark.parametrize(
    ("name", "extra", "expected"),
    [
        ("prohibited", [], 3),
        ("trap", ["--change-context", "model_retrain"], 4),
        ("high-risk", [], 1),
        # Acceptance clears Art. 6 only; the other EU obligations stay Missing (exit 1).
        ("accepted", [], 1),
        ("limited", [], 0),
    ],
)
def test_run_sh_real_gate_demo_exit_codes(
    tmp_path: Path, name: str, extra: list[str], expected: int
) -> None:
    demo = tmp_path / "work" / name
    shutil.copytree(DEMOS / name, demo)
    shims = tmp_path / "shims"
    _shim(shims, "uvx", REAL_UVX)
    env = _env(
        tmp_path,
        shims,
        OC_TEST_PY=Path(sys.executable).as_posix(),
        OC_MANIFEST=(demo / "system-manifest.json").as_posix(),
        OC_ARGS=" ".join(["--repo-root", demo.as_posix(), *extra]),
    )
    if name == "accepted":
        generate_keypair(tmp_path / "keys")
        done = subprocess.run(
            [
                BASH,
                (shims / "uvx").as_posix(),
                "opencomplai",
                "accept",
                "-m",
                (demo / "system-manifest.json").as_posix(),
                "--accepted-by",
                "demo-reviewer",
                "--statement",
                "Illustrative sandbox acceptance",
                "--repo-root",
                demo.as_posix(),
                "--key",
                (tmp_path / "keys" / "signing.key").as_posix(),
            ],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
        )
        assert done.returncode == 0, done.stdout + done.stderr
    out, summary = _run_sh(tmp_path, env)
    assert out["exit-code"] == str(expected)
    body = summary.read_text("utf-8")
    assert body.startswith(MARKER + "\n")
    assert len(body) > len(MARKER) + 1
    if name == "accepted":
        assert "EU_AIA_ART6_HIGH_RISK" not in body


@needs_bash
def test_comment_sh_creates_then_updates_sticky_comment(tmp_path: Path) -> None:
    _shim(tmp_path / "shims", "uvx", FAKE_UVX)
    _shim(tmp_path / "shims", "gh", FAKE_GH)
    env = _env(
        tmp_path,
        tmp_path / "shims",
        FAKE_ARGV=str(tmp_path / "argv"),
        GH_LOG=str(tmp_path / "gh.log"),
        GH_STATE=str(tmp_path / "gh.state"),
        GH_TOKEN="fake-token",
        GITHUB_REPOSITORY="o/r",
        PR_NUMBER="5",
    )
    _, summary = _run_sh(tmp_path, env)
    env["BODY_FILE"] = summary.as_posix()
    for _ in range(2):
        done = subprocess.run(
            [BASH, (ACTION / "comment.sh").as_posix()],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
        )
        assert done.returncode == 0, done.stdout + done.stderr
    calls = (tmp_path / "gh.log").read_text("utf-8").splitlines()
    assert len(calls) == 4, calls
    assert "--paginate repos/o/r/issues/5/comments" in calls[0]
    assert "--method POST repos/o/r/issues/5/comments" in calls[1]
    assert "--method PATCH repos/o/r/issues/comments/777" in calls[3]
    assert not any("POST" in c for c in calls[2:])


@needs_bash
def test_comment_sh_noop_outside_pr(tmp_path: Path) -> None:
    _shim(tmp_path / "shims", "gh", FAKE_GH)
    env = _env(
        tmp_path,
        tmp_path / "shims",
        GH_LOG=str(tmp_path / "gh.log"),
        GH_STATE=str(tmp_path / "gh.state"),
        GH_TOKEN="fake-token",
        GITHUB_REPOSITORY="o/r",
        PR_NUMBER="",
        BODY_FILE=str(tmp_path / "missing.md"),
    )
    done = subprocess.run(
        [BASH, (ACTION / "comment.sh").as_posix()],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert "Not a pull request" in done.stdout
    assert not (tmp_path / "gh.log").exists()


NOTE = "\n\n_Summary truncated._\n"


def _post_via_comment_sh(tmp_path: Path, body: bytes) -> bytes:
    _shim(tmp_path / "shims", "gh", FAKE_GH)
    body_file = tmp_path / "body.md"
    body_file.write_bytes(body)
    env = _env(
        tmp_path,
        tmp_path / "shims",
        GH_LOG=str(tmp_path / "gh.log"),
        GH_STATE=str(tmp_path / "gh.state"),
        GH_TOKEN="fake-token",
        GITHUB_REPOSITORY="o/r",
        PR_NUMBER="5",
        BODY_FILE=str(body_file),
    )
    done = subprocess.run(
        [BASH, (ACTION / "comment.sh").as_posix()],
        cwd=tmp_path,
        env=env,
        capture_output=True,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    return (tmp_path / "gh.state").read_bytes()


@needs_bash
@pytest.mark.parametrize(
    "char", ["\u00e9", "\u20ac", "\U0001f600"], ids=["2-byte", "3-byte", "4-byte"]
)
def test_comment_sh_truncates_on_a_character_boundary(
    tmp_path: Path, char: str
) -> None:
    k = len(char.encode())
    prefix = MARKER + "\n"
    pad = (60000 - len(prefix) - (k - 1)) % k
    raw = (prefix + "a" * pad + char * (60000 // k + 100)).encode()
    assert raw[60000] & 0xC0 == 0x80  # a byte cut would split the character
    posted = _post_via_comment_sh(tmp_path, raw)
    decoded = posted.decode("utf-8")
    assert len(decoded) <= 65536
    assert decoded.startswith(prefix)
    assert decoded.endswith(NOTE)
    assert posted[: -len(NOTE.encode())] == raw[: 60000 - (k - 1)]


@needs_bash
@pytest.mark.parametrize("size", [60000, 60001])
def test_comment_sh_threshold_is_60000_bytes(tmp_path: Path, size: int) -> None:
    prefix = MARKER + "\n"
    raw = (prefix + "x" * (size - len(prefix))).encode()
    assert len(raw) == size
    posted = _post_via_comment_sh(tmp_path, raw)
    assert posted == (raw if size == 60000 else raw[:60000] + NOTE.encode())


def _action() -> dict:
    return yaml.safe_load((ACTION / "action.yml").read_text("utf-8"))


def test_action_yml_is_pinned_composite() -> None:
    action = _action()
    assert action["runs"]["using"] == "composite"
    assert re.fullmatch(r"\d+\.\d+\.\d+", action["inputs"]["version"]["default"])
    uses = [
        ln.strip()
        for ln in (ACTION / "action.yml").read_text("utf-8").splitlines()
        if re.match(r"\s*(-\s+)?uses:", ln)
    ]
    assert len(uses) >= 2, uses
    for ln in uses:
        assert re.search(r"@[0-9a-f]{40} # v\d", ln), ln
    run_sh = (ACTION / "run.sh").read_text("utf-8")
    assert 'from="opencomplai==${OC_VERSION}"' in run_sh
    assert "latest" not in run_sh
    assert "uvx --from" in run_sh


def test_action_yml_never_interpolates_inputs_in_run() -> None:
    steps = _action()["runs"]["steps"]
    runs = [s["run"] for s in steps if "run" in s]
    assert runs
    assert not [r for r in runs if "${{" in r], runs


@pytest.mark.skipif(not SELFTEST.is_file(), reason="no self-test workflow in this tree")
def test_selftest_matrix_covers_all_five_demos() -> None:
    text = SELFTEST.read_text("utf-8")
    assert re.search(r"^permissions:", text, re.M)
    wf = yaml.safe_load(text)
    assert wf["permissions"] == {"contents": "read"}
    (job,) = wf["jobs"].values()
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
    assert "./integrations/github-action" in uses


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
