"""The concept pages exist, are in the nav, and the schema index is complete.

Reads repo files from the core suite (the root is three levels above this file). The
dashboard schema glob is skipped when `dashboard-saas/` is absent (public checkout).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
CONCEPTS = ROOT / "docs" / "src" / "concepts"
NAV = ROOT / "docs" / "mkdocs.yml"
CORE_SCHEMAS = ROOT / "packages" / "core" / "src" / "opencomplai_core" / "data"
DASHBOARD_SCHEMAS = ROOT / "dashboard-saas" / "schemas"
CLI_SRC = ROOT / "packages" / "cli" / "src" / "opencomplai_cli"

NEW_PAGES = (
    "rule-set-versioning",
    "roles-and-applicability",
    "backlog",
    "agents",
    "incidents",
    "regimes",
    "high-risk-acceptance",
    "published-schemas",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_every_new_page_exists_and_is_in_nav() -> None:
    nav = _read(NAV)
    for name in NEW_PAGES:
        assert (CONCEPTS / f"{name}.md").is_file(), f"missing concepts/{name}.md"
        assert re.search(
            rf":\s*concepts/{re.escape(name)}\.md\s*$", nav, re.MULTILINE
        ), f"concepts/{name}.md is not a nav entry in docs/mkdocs.yml"


def test_every_schema_file_and_id_has_an_index_entry() -> None:
    index = _read(CONCEPTS / "published-schemas.md")

    def check(directory: Path) -> None:
        files = sorted(directory.glob("*.schema.json"))
        assert files, f"no schemas found in {directory}"
        for path in files:
            assert path.name in index, f"{path.name} has no index entry"
            schema_id = json.loads(_read(path)).get("$id")
            if schema_id:
                assert schema_id in index, f"{schema_id} ({path.name}) is not indexed"

    check(CORE_SCHEMAS)
    if not DASHBOARD_SCHEMAS.is_dir():
        pytest.skip("dashboard-saas/ is absent (public checkout)")
    check(DASHBOARD_SCHEMAS)


def test_versioning_policy_sections_present() -> None:
    index = _read(CONCEPTS / "published-schemas.md")
    for heading in (
        "## Versioning policy",
        "### $id pattern",
        "### Pin and re-pin rules",
        "### Compatibility promise",
    ):
        assert re.search(rf"^{re.escape(heading)}\s*$", index, re.MULTILINE), heading
    assert "https://schemas.opencomplai.dev/" in index
    assert "needs founder review" in index.lower()


def test_concept_pages_reference_only_real_commands() -> None:
    cli_text = "\n".join(_read(p) for p in CLI_SRC.rglob("*.py"))
    for name in NEW_PAGES:
        text = _read(CONCEPTS / f"{name}.md")
        for word in set(re.findall(r"\bopencomplai\s+([a-z][a-z0-9-]*)", text)):
            assert f'"{word}"' in cli_text, (
                f"concepts/{name}.md names `opencomplai {word}`, not found in the CLI"
            )
