"""oss-public/.github is the source of the public CI and assemble.sh projects it.

Every test builds a throwaway git repo under tmp_path and runs a copy of
assemble.sh against it; the real repo is never the OUTPUT.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
ASSEMBLE = REPO / "scripts" / "assemble.sh"
SRC_CI = REPO / "oss-public" / ".github"
# Resolve bash once: a bare "bash" can hit the WSL launcher on Windows.
BASH = shutil.which("bash") or "bash"
GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
CONFIG_YML = ".github/ISSUE_TEMPLATE/config.yml"
# Public CI decision for 0.9.0: the projected ci.yml is held back by
# PRIVATE_WORKFLOWS. Empty this when ci.yml ships.
HELD_BACK = {"workflows/ci.yml"}

pytestmark = pytest.mark.skipif(
    not ASSEMBLE.exists()
    or shutil.which("bash") is None
    or shutil.which("git") is None,
    reason="needs scripts/assemble.sh (absent in the public tree), bash and git",
)


def _git(cwd: Path, *args: str) -> None:
    subprocess.run([*GIT, *args], cwd=cwd, check=True, capture_output=True)


def _make_source(tmp_path: Path, *, with_oss_public: bool = True) -> Path:
    src = tmp_path / "src"
    (src / "scripts").mkdir(parents=True)
    for name in ("assemble.sh", "oss-config.sh"):
        shutil.copyfile(REPO / "scripts" / name, src / "scripts" / name)
    (src / "README.md").write_text("hello\n", encoding="utf-8")
    (src / CONFIG_YML).parent.mkdir(parents=True)
    (src / CONFIG_YML).write_text("blank_issues_enabled: false\n", encoding="utf-8")
    if with_oss_public:
        for name in ("ci.yml", "actionlint.yml"):
            dst = src / "oss-public" / ".github" / "workflows" / name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(SRC_CI / "workflows" / name, dst)
    # Byte-exact archives even where a global core.autocrlf would rewrite them.
    (src / ".gitattributes").write_text("* -text\n", encoding="utf-8")
    _git(tmp_path, "init", "-q", str(src))
    _git(src, "add", ".")
    _git(src, "commit", "-q", "-m", "init")
    return src


def _assemble(
    src: Path, out: Path, *flags: str, ok: bool = True
) -> subprocess.CompletedProcess[str]:
    res = subprocess.run(
        [BASH, "scripts/assemble.sh", *flags, src.as_posix(), out.as_posix()],
        cwd=src,
        capture_output=True,
        text=True,
    )
    if ok:
        assert res.returncode == 0, res.stdout + res.stderr
    return res


def _public_clone(out: Path) -> None:
    """An existing public clone with a stale actionlint.yml and a public-only workflow."""
    wf = out / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "actionlint.yml").write_text("name: stale\n", encoding="utf-8")
    (wf / "public-only.yml").write_text("name: public-only\n", encoding="utf-8")
    _git(out.parent, "init", "-q", str(out))
    _git(out, "add", ".")
    _git(out, "commit", "-q", "-m", "public")


def test_oss_public_workflows_have_required_jobs() -> None:
    ci = (SRC_CI / "workflows" / "ci.yml").read_text(encoding="utf-8")
    for needle in (
        '"3.11"',
        '"3.12"',
        '"3.13"',
        "windows-latest",
        "macos-latest",
        "smoke_wheel_install.sh",
        "docker compose",
        "build",
        "mkdocs build --strict",
    ):
        assert needle in ci, needle
    lint = (SRC_CI / "workflows" / "actionlint.yml").read_text(encoding="utf-8")
    assert "actionlint" in lint
    # Without `branches`, a push filter never fires for branch pushes.
    assert "branches:" in lint


def test_oss_public_sources_reference_no_private_paths() -> None:
    files = [p for p in (REPO / "oss-public").rglob("*") if p.is_file()]
    assert files
    for p in files:
        text = p.read_text(encoding="utf-8")
        for bad in (
            "dashboard-saas",
            "PLAN/",
            "isms/",
            "compliance-reports",
            "secrets.",
        ):
            assert bad not in text, f"{p.relative_to(REPO)} contains {bad!r}"


def test_assemble_projects_public_ci_into_fresh_dir(tmp_path: Path) -> None:
    src, out = _make_source(tmp_path), tmp_path / "out"
    _assemble(src, out)
    sources = [
        p
        for p in SRC_CI.rglob("*")
        if p.is_file() and p.relative_to(SRC_CI).as_posix() not in HELD_BACK
    ]
    assert sources
    for p in sources:
        dst = out / ".github" / p.relative_to(SRC_CI)
        assert dst.read_bytes() == p.read_bytes(), dst


def test_assemble_projects_public_ci_over_existing_public_clone(tmp_path: Path) -> None:
    src, out = _make_source(tmp_path), tmp_path / "out"
    _public_clone(out)
    _assemble(src, out)
    assert (out / ".github/workflows/actionlint.yml").read_bytes() == (
        SRC_CI / "workflows/actionlint.yml"
    ).read_bytes()
    assert (out / ".github/workflows/public-only.yml").exists()
    assert (out / CONFIG_YML).read_bytes() == (src / CONFIG_YML).read_bytes()


def test_oss_public_dir_not_in_output(tmp_path: Path) -> None:
    src, out = _make_source(tmp_path), tmp_path / "out"
    _assemble(src, out)
    assert not (out / "oss-public").exists()
    assert (out / ".github").is_dir()


def test_assemble_without_oss_public_still_restores_public_github(
    tmp_path: Path,
) -> None:
    src, out = _make_source(tmp_path, with_oss_public=False), tmp_path / "out"
    _public_clone(out)
    _assemble(src, out)
    assert (out / ".github/workflows/actionlint.yml").read_text(
        encoding="utf-8"
    ) == "name: stale\n"
    assert (out / ".github/workflows/public-only.yml").exists()


def test_assemble_holds_back_projected_ci_yml(tmp_path: Path) -> None:
    src = _make_source(tmp_path)
    fresh = tmp_path / "fresh"
    _assemble(src, fresh)
    assert (fresh / ".github/workflows/actionlint.yml").is_file()
    assert not (fresh / ".github/workflows/ci.yml").exists()

    out = tmp_path / "out"
    _public_clone(out)
    (out / ".github/workflows/ci.yml").write_text("name: public ci\n", encoding="utf-8")
    _git(out, "add", ".")
    _git(out, "commit", "-q", "-m", "ci")
    _assemble(src, out)
    assert not (out / ".github/workflows/ci.yml").exists()
    assert (out / ".github/workflows/public-only.yml").exists()


def _clone_with_local_files(out: Path) -> None:
    """A public clone holding an excluded brag-output/ and an untracked notes.txt."""
    _public_clone(out)
    (out / "brag-output").mkdir()
    (out / "brag-output" / "brag.mp4").write_bytes(b"video")
    with (out / ".git" / "info" / "exclude").open("a", encoding="utf-8") as f:
        f.write("brag-output/\n")
    (out / "notes.txt").write_text("mine\n", encoding="utf-8")


def test_assemble_refuses_to_wipe_local_files(tmp_path: Path) -> None:
    src, out = _make_source(tmp_path), tmp_path / "out"
    _clone_with_local_files(out)
    res = _assemble(src, out, ok=False)
    assert res.returncode == 1, res.stdout + res.stderr
    for needle in ("brag-output", "notes.txt", "--force-clean"):
        assert needle in res.stderr, needle
    assert (out / "brag-output" / "brag.mp4").exists()
    assert (out / "notes.txt").exists()
    assert not (out / "README.md").exists()


def test_assemble_keeps_going_over_regenerated_and_projected_files(
    tmp_path: Path,
) -> None:
    src, out = _make_source(tmp_path), tmp_path / "out"
    _public_clone(out)
    with (out / ".git" / "info" / "exclude").open("a", encoding="utf-8") as f:
        f.write("compliance-artifact.json\nsystem-manifest.json\n")
    (out / "compliance-artifact.json").write_text("{}\n", encoding="utf-8")
    (out / "system-manifest.json").write_text("{}\n", encoding="utf-8")
    (out / "README.md").write_text("old\n", encoding="utf-8")
    _assemble(src, out)
    assert (out / "README.md").read_bytes() == (src / "README.md").read_bytes()


def test_assemble_force_clean_deletes_local_files(tmp_path: Path) -> None:
    src, out = _make_source(tmp_path), tmp_path / "out"
    _clone_with_local_files(out)
    _assemble(src, out, "--force-clean")
    assert not (out / "brag-output").exists()
    assert not (out / "notes.txt").exists()
    assert (out / "README.md").exists()


def test_assemble_refuses_when_output_status_fails(tmp_path: Path) -> None:
    src, out = _make_source(tmp_path), tmp_path / "out"
    _public_clone(out)
    (out / "keep.txt").write_text("mine\n", encoding="utf-8")
    (out / ".git" / "index").write_bytes(b"garbage, not an index")
    res = _assemble(src, out, ok=False)
    assert res.returncode == 1, res.stdout + res.stderr
    assert "git status failed" in res.stderr
    assert (out / "keep.txt").exists()
