"""The CI recipes page: YAML parses, no raw ingest curl, notify and archive notes exist.

Pure file reads, no network.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parents[3]
_RECIPES = (_ROOT / "docs" / "src" / "guides" / "ci-recipes.md").read_text(
    encoding="utf-8"
)
_GUIDE = (_ROOT / "docs" / "src" / "guides" / "ci-integration.md").read_text(
    encoding="utf-8"
)
_MKDOCS = (_ROOT / "docs" / "mkdocs.yml").read_text(encoding="utf-8")
_LEGACY_VARS = (
    "OPENCOMPLAI_AUTH_TOKEN",
    "OPENCOMPLAI_CLIENT_ID",
    "OPENCOMPLAI_CLIENT_SECRET",
    "OPENCOMPLAI_TOKEN_ENDPOINT",
)


def _blocks(md: str, lang: str) -> list[str]:
    return re.findall(rf"```{lang}\n(.*?)```", md, re.S)


def _section(md: str, heading: str) -> str:
    m = re.search(rf"^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", md, re.S | re.M)
    assert m, f"missing section {heading}"
    return m.group(1)


def test_recipe_yaml_blocks_parse() -> None:
    blocks = _blocks(_RECIPES, "yaml")
    assert len(blocks) >= 2
    for b in blocks:
        assert isinstance(yaml.safe_load(b), dict)


def test_three_platform_recipes_present() -> None:
    for h in ("Jenkins", "Bitbucket Pipelines", "CircleCI"):
        assert f"\n## {h}\n" in _RECIPES
    assert any(
        "returnStatus" in b and "archiveArtifacts" in b
        for b in _blocks(_RECIPES, "groovy")
    )
    parsed = [yaml.safe_load(b) for b in _blocks(_RECIPES, "yaml")]
    assert any("pipelines" in p for p in parsed)
    assert any("jobs" in p and "version" in p for p in parsed)


def test_no_raw_ingest_curl() -> None:
    for text in (_RECIPES, _GUIDE):
        assert "v1/ingest/scan-status" not in text
        assert "-d @compliance-artifact.json" not in text


def test_any_other_ci_uses_push() -> None:
    sec = _section(_GUIDE, "Any other CI platform")
    assert "opencomplai push" in sec
    assert "422" in sec


def test_exit_code_notify_recipes_cover_every_code() -> None:
    sec = _section(_RECIPES, "Notify from the exit code")
    assert 'case "$CHECK_EXIT"' in sec
    for code in range(5):
        assert re.search(rf"^\s*{code}\)", sec, re.M)
    assert "SLACK_WEBHOOK_URL" in sec
    assert "rest/api/3/issue" in sec
    assert "hooks.slack.com/services/" not in _RECIPES
    assert "Bearer ock_" not in _RECIPES


def test_archive_note_names_artifact_files() -> None:
    sec = _section(_RECIPES, "Archive the artifact")
    for word in (
        "compliance-artifact.json",
        "archiveArtifacts",
        "store_artifacts",
        "artifacts",
    ):
        assert word in sec


def test_page_in_nav_and_linked() -> None:
    assert "guides/ci-recipes.md" in _MKDOCS
    assert "ci-recipes.md" in _GUIDE
    assert "ci-integration.md" in _RECIPES


def test_recipes_page_avoids_legacy_auth_vars() -> None:
    for v in _LEGACY_VARS:
        assert v not in _RECIPES


def test_ci_guide_still_has_two_yaml_blocks() -> None:
    assert len(_blocks(_GUIDE, "yaml")) == 2
