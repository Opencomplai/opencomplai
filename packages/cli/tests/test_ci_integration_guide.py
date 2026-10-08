"""
DG-11: the published CI guide (docs/src/guides/ci-integration.md) must be
generated from the same canonical YAML DG-7 already treats as the single
source of truth -- the same files
dashboard-saas/services/web/src/lib/ciSnippets.test.ts already byte-compares
its generator output against. This extends that same guarantee to the
published guide: its fenced ```yaml blocks must be byte-identical to those
files (at the documented placeholder host), so a future edit to one without
the other fails here instead of silently drifting, which is exactly the kind
of drift that made the old guide teach the legacy bearer-token env var +
OIDC client creds long after the CLI/dashboard had moved on to API-key auth.

Root-workspace test (not the web toolchain) per DG-11's own instructions --
this only needs to read two file paths, no web build tooling required.

CP-11 (D-10): the canonical copies now live in this OSS tree at docs/ci/ --
vendored from dashboard-saas/docs/ci/ so these two tests are reachable (and
therefore run rather than skip) in the public checkout too. A separate
enterprise-only test below still asserts docs/ci/ stays in sync with the
dashboard-saas/ originals.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_GUIDE = _REPO_ROOT / "docs" / "src" / "guides" / "ci-integration.md"
_DOCS_CI_DIR = _REPO_ROOT / "docs" / "ci"
_DASHBOARD_DOCS_CI_DIR = _REPO_ROOT / "dashboard-saas" / "docs" / "ci"

_PLACEHOLDER_HOST = "https://YOUR-DASHBOARD-HOST"


def _fenced_yaml_blocks(markdown: str) -> list[str]:
    return re.findall(r"```yaml\n(.*?)```", markdown, re.S)


def test_guide_exists_and_has_two_yaml_blocks():
    assert _GUIDE.exists(), f"missing {_GUIDE}"
    blocks = _fenced_yaml_blocks(_GUIDE.read_text(encoding="utf-8"))
    assert len(blocks) == 2, (
        f"expected exactly 2 fenced yaml blocks (github actions, gitlab ci), "
        f"found {len(blocks)}"
    )


def test_guide_github_actions_block_matches_docs_ci_verbatim():
    # docs/ci/ is vendored into the OSS tree (CP-11/D-10) -- always reachable,
    # public checkout included, so this runs rather than skips there too.
    canonical_path = _DOCS_CI_DIR / "github-actions.yml"
    blocks = _fenced_yaml_blocks(_GUIDE.read_text(encoding="utf-8"))
    assert blocks[0] == canonical_path.read_text(encoding="utf-8")


def test_guide_gitlab_ci_block_matches_docs_ci_verbatim():
    canonical_path = _DOCS_CI_DIR / "gitlab-ci.yml"
    blocks = _fenced_yaml_blocks(_GUIDE.read_text(encoding="utf-8"))
    assert blocks[1] == canonical_path.read_text(encoding="utf-8")


def test_docs_ci_matches_dashboard_saas_source_verbatim():
    """Enterprise-only: docs/ci/*.yml (OSS-vendored) must stay byte-identical
    to the dashboard-saas/docs/ci/*.yml originals they were vendored from.
    Skips in the public checkout, where dashboard-saas/ does not exist at
    all -- intentional, matching the pre-CP-11 skip pattern this file used
    for the two tests above before they were repointed at the OSS-reachable
    docs/ci/ copy. Fails (never skips) when dashboard-saas/ IS reachable and
    the two copies differ."""
    if not _DASHBOARD_DOCS_CI_DIR.exists():
        pytest.skip(
            "dashboard-saas/docs/ci not reachable (expected in public checkout)"
        )
    for name in ("github-actions.yml", "gitlab-ci.yml"):
        assert (_DOCS_CI_DIR / name).read_text(encoding="utf-8") == (
            _DASHBOARD_DOCS_CI_DIR / name
        ).read_text(encoding="utf-8"), name


def test_guide_yaml_blocks_use_the_documented_placeholder_host():
    blocks = _fenced_yaml_blocks(_GUIDE.read_text(encoding="utf-8"))
    for block in blocks:
        assert _PLACEHOLDER_HOST in block


def test_guide_never_mentions_the_legacy_auth_token_var_or_oidc_client_creds():
    text = _GUIDE.read_text(encoding="utf-8")
    assert "OPENCOMPLAI_AUTH_TOKEN" not in text
    assert "OPENCOMPLAI_CLIENT_ID" not in text
    assert "OPENCOMPLAI_CLIENT_SECRET" not in text
    assert "OPENCOMPLAI_TOKEN_ENDPOINT" not in text


def test_guide_points_at_connect():
    text = _GUIDE.read_text(encoding="utf-8")
    assert "/connect" in text


_MARKER = "pytest.mark." + "x" + "fail"
_SKIP_DIRS = {"node_modules", ".venv", "__pycache__"}


def test_no_xfail_marker_in_python_tests():
    """No lenient expected-failure marker may hide a drift in any test tree.

    A strict one (``strict=True``, on the marker's own line) is allowed: it
    records a known false negative and fails loudly the day it is fixed, so it
    cannot mask a regression. Anything else, e.g. the old non-strict marker on
    the dashboard CI parity test, is reported as ``path:line``.
    """
    found = []
    for top in ("packages", "services", "api", "tools", "tests", "dashboard-saas"):
        root = _REPO_ROOT / top
        if not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            if _SKIP_DIRS & set(path.parts):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for n, line in enumerate(text.splitlines(), start=1):
                if _MARKER in line and "strict=True" not in line:
                    found.append(f"{path.relative_to(_REPO_ROOT).as_posix()}:{n}")
    assert not found, "non-strict expected-failure marker found: " + ", ".join(found)
