"""
DG-11: the published CI guide (docs/src/guides/ci-integration.md) must be
generated from the same canonical YAML DG-7 already treats as the single
source of truth (dashboard-saas/docs/ci/*.yml) -- the same files
dashboard-saas/services/web/src/lib/ciSnippets.test.ts already byte-compares
its generator output against. This extends that same guarantee to the
published guide: its fenced ```yaml blocks must be byte-identical to those
files (at the documented placeholder host), so a future edit to one without
the other fails here instead of silently drifting, which is exactly the kind
of drift that made the old guide teach the legacy bearer-token env var +
OIDC client creds long after the CLI/dashboard had moved on to API-key auth.

Root-workspace test (not the web toolchain) per DG-11's own instructions --
this only needs to read two file paths, no web build tooling required.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_GUIDE = _REPO_ROOT / "docs" / "src" / "guides" / "ci-integration.md"
_DOCS_CI_DIR = _REPO_ROOT / "dashboard-saas" / "docs" / "ci"

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
    blocks = _fenced_yaml_blocks(_GUIDE.read_text(encoding="utf-8"))
    canonical = (_DOCS_CI_DIR / "github-actions.yml").read_text(encoding="utf-8")
    assert blocks[0] == canonical


def test_guide_gitlab_ci_block_matches_docs_ci_verbatim():
    blocks = _fenced_yaml_blocks(_GUIDE.read_text(encoding="utf-8"))
    canonical = (_DOCS_CI_DIR / "gitlab-ci.yml").read_text(encoding="utf-8")
    assert blocks[1] == canonical


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
