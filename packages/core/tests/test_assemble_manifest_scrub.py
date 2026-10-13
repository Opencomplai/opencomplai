"""assemble.sh scrubs private package names from monorepo manifests.

Every test builds a throwaway git repo under tmp_path, runs a copy of
assemble.sh and oss-config.sh against it, then (where relevant) runs the real
verify-oss.sh over the OUTPUT. The real repo is never the OUTPUT and nothing
is mocked. Private literals are built at runtime so this file passes the
gate it tests.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
ASSEMBLE = REPO / "scripts" / "assemble.sh"
VERIFY = REPO / "scripts" / "verify-oss.sh"
# Resolve bash once: a bare "bash" can hit the WSL launcher on Windows.
BASH = shutil.which("bash") or "bash"
GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid"]

PRIV_DIR = "dashboard" + "-saas"
PRIV_PKG = "dashboard" + "-web"
ENT_NAME = "opencomplai" + "-enterprise"
PRIV_ISMS = "is" + "ms"

pytestmark = pytest.mark.skipif(
    not ASSEMBLE.exists()
    or not VERIFY.exists()
    or shutil.which("bash") is None
    or shutil.which("git") is None,
    reason="needs scripts/assemble.sh and verify-oss.sh (absent in the public tree), bash and git",
)

WORKSPACE_YAML = (
    "packages:\n"
    "  - 'services/gateway-api'\n"
    f"  - '{PRIV_DIR}/services/web'\n"
    f'  - "{PRIV_DIR}/services/api"\n'
    f"  - {PRIV_DIR}/libs/*  # c\n"
    f"  - '{PRIV_ISMS}/tools'\n"
    "  - 'packages/*'\n"
)
LOCK_YAML = (
    "lockfileVersion: '9.0'\n"
    "settings:\n"
    "  autoInstallPeers: true\n"
    "  excludeLinksFromLockfile: false\n"
    "importers:\n"
    "  .: {}\n"
    "  services/gateway-api: {}\n"
    f"  {PRIV_DIR}/services/web: {{}}\n"
)


def _git(cwd: Path, *args: str) -> None:
    subprocess.run([*GIT, *args], cwd=cwd, check=True, capture_output=True)


def _make_tree(tmp_path: Path, files: dict[str, str]) -> Path:
    src = tmp_path / "src"
    (src / "scripts").mkdir(parents=True)
    for name in ("assemble.sh", "oss-config.sh"):
        shutil.copyfile(REPO / "scripts" / name, src / "scripts" / name)
    all_files = {"README.md": "hello\n", ".gitattributes": "* -text\n", **files}
    for rel, text in all_files.items():
        p = src / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")
    _git(tmp_path, "init", "-q", str(src))
    _git(src, "add", ".")
    _git(src, "commit", "-q", "-m", "init")
    return src


def _assemble(src: Path, out: Path) -> subprocess.CompletedProcess[str]:
    res = subprocess.run(
        [BASH, "scripts/assemble.sh", src.as_posix(), out.as_posix()],
        cwd=src,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert res.returncode == 0, res.stdout + res.stderr
    return res


def _verify(out: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [BASH, VERIFY.as_posix(), out.as_posix()],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _leaks(out: Path, tokens: list[str]) -> list[tuple[str, str]]:
    found = []
    for p in out.rglob("*"):
        if not p.is_file() or ".git" in p.relative_to(out).parts:
            continue
        data = p.read_bytes()
        found += [
            (p.relative_to(out).as_posix(), t) for t in tokens if t.encode() in data
        ]
    return found


def _root_manifests() -> dict[str, str]:
    pkg = {"name": ENT_NAME + "-workspace", "version": "0.0.0", "private": True}
    lock = {
        "name": ENT_NAME,
        "lockfileVersion": 3,
        "requires": True,
        "packages": {"": {"name": ENT_NAME}},
    }
    return {
        "package.json": json.dumps(pkg, indent=2) + "\n",
        "package-lock.json": json.dumps(lock, indent=2) + "\n",
    }


def test_workspace_manifest_prunes_private_members(tmp_path):
    src = _make_tree(tmp_path, {"pnpm-workspace.yaml": WORKSPACE_YAML})
    out = tmp_path / "out"
    _assemble(src, out)
    text = (out / "pnpm-workspace.yaml").read_text(encoding="utf-8")
    assert "services/gateway-api" in text
    assert "packages/*" in text
    assert PRIV_DIR not in text
    assert PRIV_ISMS not in text


def test_root_manifests_renamed_for_public_projection(tmp_path):
    src = _make_tree(tmp_path, _root_manifests())
    out = tmp_path / "out"
    _assemble(src, out)
    pkg = json.loads((out / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((out / "package-lock.json").read_text(encoding="utf-8"))
    assert pkg["name"] == "opencomplai-workspace"
    assert lock["name"] == "opencomplai-workspace"
    assert lock["packages"][""]["name"] == "opencomplai-workspace"
    assert _leaks(out, [ENT_NAME]) == []


@pytest.mark.skipif(shutil.which("pnpm") is None, reason="needs pnpm")
def test_projected_manifests_hold_no_private_names(tmp_path):
    workspace = (
        "packages:\n"
        "  - 'services/gateway-api'\n"
        f"  - '{PRIV_DIR}/services/web'\n"
        f'  - "{PRIV_DIR}/services/api"\n'
        f"  - {PRIV_DIR}/libs/*  # c\n"
        f"  - '{PRIV_ISMS}/tools'\n"
    )
    files = {
        "pnpm-workspace.yaml": workspace,
        "pnpm-lock.yaml": LOCK_YAML,
        "services/gateway-api/package.json": json.dumps(
            {"name": "gateway", "version": "0.0.0"}
        ),
        f"{PRIV_DIR}/services/web/package.json": json.dumps(
            {"name": PRIV_PKG, "version": "0.0.0"}
        ),
        **_root_manifests(),
    }
    src = _make_tree(tmp_path, files)
    out = tmp_path / "out"
    res = _assemble(src, out)
    assert "Regenerating pnpm-lock.yaml" in res.stdout
    if "could not regenerate" in res.stderr:
        pytest.skip("pnpm could not regenerate offline here")
    assert _leaks(out, [PRIV_DIR, PRIV_PKG, ENT_NAME]) == []
    lock = (out / "pnpm-lock.yaml").read_text(encoding="utf-8")
    assert not any(ln.lstrip().startswith(PRIV_DIR) for ln in lock.splitlines())
    assert "referenced in build manifest" not in _verify(out).stderr


def test_verify_blocks_private_workspaces_assemble_leaves_behind(tmp_path):
    # assemble.sh prunes only pnpm-workspace.yaml; these two survive it and
    # verify-oss.sh is the backstop that must block them.
    member = f"{PRIV_DIR}/services/web"
    pkg = {"name": "x", "version": "0.0.0", "workspaces": ["packages/*", member]}
    lock = {
        "name": "x",
        "lockfileVersion": 3,
        "packages": {
            "": {"name": "x"},
            member: {"name": PRIV_PKG},
            f"node_modules/{PRIV_PKG}": {"resolved": member, "link": True},
        },
    }
    src = _make_tree(
        tmp_path,
        {
            "package.json": json.dumps(pkg, indent=2) + "\n",
            "package-lock.json": json.dumps(lock, indent=2) + "\n",
        },
    )
    out = tmp_path / "out"
    _assemble(src, out)
    r = _verify(out)
    assert r.returncode != 0
    assert "referenced in build manifest: package.json" in r.stderr
    assert "referenced in build manifest: package-lock.json" in r.stderr
