"""Per-pack remediation templates: `packs/<KEY>/templates/template_map.json`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from opencomplai_core import pack_registry
from opencomplai_core.frameworks import FRAMEWORKS, FrameworkPack
from opencomplai_core.models import (
    ArticleGapSource,
    ArticleGapStatus,
    GapReport,
    GapStatus,
)
from opencomplai_core.recommend_engine import (
    load_pack_template_map,
    render_recommendations,
)

FIXTURE_PACK = FrameworkPack(
    "FIXTURE",
    "Fixture framework",
    requirements=Path(__file__).parent
    / "fixtures"
    / "framework_pack"
    / "requirements.json",
)


@pytest.fixture
def pack_root(tmp_path, monkeypatch):
    root = tmp_path / "packs"
    templates = root / "FIXTURE" / "templates"
    templates.mkdir(parents=True)
    (templates / "template_map.json").write_text(
        json.dumps(
            {
                "FIXTURE:REQ-3": {
                    "template_id": "fixture_special",
                    "kind": "markdown",
                    "file": "special.md",
                }
            }
        ),
        encoding="utf-8",
    )
    (templates / "special.md").write_text(
        "# Pack template for {{article}} ({{status}})\n\n{{rationale}}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(pack_registry, "PACKS_DIR", root)
    monkeypatch.setitem(FRAMEWORKS, "FIXTURE", FIXTURE_PACK)
    load_pack_template_map.cache_clear()
    yield root
    load_pack_template_map.cache_clear()


def _row(article: str) -> ArticleGapStatus:
    return ArticleGapStatus(
        article=article,
        status=GapStatus.MISSING,
        source=ArticleGapSource.ARTIFACT,
        evidence_ref="ref",
        rationale="nothing found",
    )


def _report(*articles: str) -> GapReport:
    return GapReport(
        system_id="test-sys",
        commit_ref="HEAD",
        generated_at="2026-07-11T00:00:00Z",
        articles=[_row(a) for a in articles],
    )


def test_map_loads_and_is_empty_without_a_map(pack_root):
    assert set(load_pack_template_map("FIXTURE")) == {"FIXTURE:REQ-3"}
    assert load_pack_template_map("NOPE") == {}


def test_mapped_row_gets_the_pack_template(pack_root, tmp_path):
    out = tmp_path / "out"
    written = render_recommendations(_report("FIXTURE:REQ-3"), out)

    assert [p.name for p in written] == ["fixture--req-3-fixture_special.md"]
    content = written[0].read_text(encoding="utf-8")
    assert "# Pack template for FIXTURE:REQ-3 (MISSING)" in content
    assert "nothing found" in content


def test_unmapped_row_gets_the_generic_template(pack_root, tmp_path):
    written = render_recommendations(_report("FIXTURE:REQ-1"), tmp_path / "out")

    assert [p.name for p in written] == ["fixture--req-1-generic_requirement.md"]
    assert "Requirement Action Plan" in written[0].read_text(encoding="utf-8")


def test_eu_row_is_unaffected(pack_root, tmp_path):
    written = render_recommendations(_report("Art. 9"), tmp_path / "out")

    assert written
    assert all("fixture" not in p.name for p in written)
    assert "Pack template" not in written[0].read_text(encoding="utf-8")
