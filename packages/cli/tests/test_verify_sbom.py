"""sync/verify-sbom.sh checks the identity and namespace where release images are signed.

cosign and jq are bash function stubs that log their arguments: no network,
no real cosign, no PATH edits.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
BASH = shutil.which("bash")
needs_bash = pytest.mark.skipif(BASH is None, reason="needs bash")

STUB = (
    'cosign() { printf \'%s\\n\' "$*" >> "$STUB_LOG"; }; '
    "jq() { cat >/dev/null; echo sbom; }; "
    "export -f cosign jq; "
)
DEFAULT_ID = (
    "^https://github.com/Opencomplai/opencomplai-enterprise/"
    "\\.github/workflows/supply-chain\\.yml@"
)


def _run(tmp_path: Path, ref: str, **env: str) -> list[str]:
    log = tmp_path / "cosign.log"
    base = {k: v for k, v in os.environ.items() if k != "OPENCOMPLAI_RELEASE_REPO"}
    res = subprocess.run(
        [BASH, "-c", STUB + '"$BASH" sync/verify-sbom.sh "$1"', "_", ref],
        cwd=ROOT,
        env={**base, "STUB_LOG": log.as_posix(), **env},
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, res.stdout + res.stderr
    lines = log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2, lines
    assert lines[0].startswith("verify ")
    assert lines[1].startswith("verify-attestation ")
    return lines


@needs_bash
def test_defaults_to_release_repo_identity_and_namespace(tmp_path: Path) -> None:
    for line in _run(tmp_path, "gateway-api:0.9.0"):
        assert f"--certificate-identity-regexp {DEFAULT_ID}" in line
        assert line.endswith(
            " ghcr.io/opencomplai/opencomplai-enterprise/gateway-api:0.9.0"
        )


@needs_bash
def test_full_reference_and_release_repo_override(tmp_path: Path) -> None:
    fork = tmp_path / "fork"
    fork.mkdir()
    for line in _run(
        fork, "gateway-api:1.2.3", OPENCOMPLAI_RELEASE_REPO="Example/Fork-Repo"
    ):
        assert (
            "--certificate-identity-regexp "
            "^https://github.com/Example/Fork-Repo/\\.github/workflows/supply-chain\\.yml@"
        ) in line
        assert line.endswith(" ghcr.io/example/fork-repo/gateway-api:1.2.3")
    full = tmp_path / "full"
    full.mkdir()
    for line in _run(full, "ghcr.io/acme/x/gateway-api:1"):
        assert f"--certificate-identity-regexp {DEFAULT_ID}" in line
        assert line.endswith(" ghcr.io/acme/x/gateway-api:1")


def test_image_docs_point_at_the_release_repo() -> None:
    docs = (
        "SECURITY.md",
        "docs/src/security/supply-chain.md",
        "docs/src/guides/security.md",
    )
    for rel in docs:
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "GHCR packages are public" in text, rel
        assert "opencomplai-enterprise" in text, rel
    for rel in docs[1:]:
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "ghcr.io/<owner>/<repo>" not in text, rel
        assert "github.com/Opencomplai/opencomplai/actions/workflows/" not in text, rel
