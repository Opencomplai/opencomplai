"""Article-specific recommend templates (SU-103)."""

from __future__ import annotations

import re
from pathlib import Path

from opencomplai_core import recommend_engine
from opencomplai_core.models import (
    ArticleGapSource,
    ArticleGapStatus,
    GapReport,
    GapStatus,
)
from opencomplai_core.recommend_engine import load_template_map, render_recommendations

TEMPLATES_DIR = Path(recommend_engine.__file__).parent / "templates" / "recommend"
ARTICLE_KEYS = [
    "Art. 5",
    "Art. 10",
    "Art. 11",
    "Art. 15",
    "Art. 16",
    "Art. 24",
    "Art. 25",
    "Art. 43",
]
SUMMIT_ROW_KEYS = [
    *ARTICLE_KEYS,
    "Art. 13",
    "Art. 26",
    "Art. 49",
    "Art. 53",
    "Art. 55",
    "Art. 72",
    "Art. 73",
]
_ART = re.compile(r"Art\. \d+")


def _heading(entry: dict) -> str:
    text = (TEMPLATES_DIR / entry["file"]).read_text(encoding="utf-8")
    return text.splitlines()[0]


def test_declared_article_equals_map_key():
    tmap = load_template_map()
    for key in ARTICLE_KEYS:
        assert tmap[key]["article"] == key


def test_template_heading_names_only_its_article():
    tmap = load_template_map()
    for key in ARTICLE_KEYS:
        assert _ART.findall(_heading(tmap[key])) == [key], key


def test_article_specific_templates_are_distinct():
    tmap = load_template_map()
    ids = [tmap[k]["template_id"] for k in ARTICLE_KEYS]
    files = [tmap[k]["file"] for k in ARTICLE_KEYS]
    assert len(set(ids)) == len(ids) == 8
    assert len(set(files)) == len(files) == 8
    assert not {"risk_register_entry", "annex_iii_applicability_note"} & set(ids)
    for key in ARTICLE_KEYS:
        assert tmap[key]["template_id"] == Path(tmap[key]["file"]).stem


def test_art13_maps_to_instructions_for_use():
    assert load_template_map()["Art. 13"]["template_id"] == "instructions_for_use"


def test_art11_template_points_at_docs_generate(tmp_path: Path):
    report = GapReport(
        system_id="test-sys",
        commit_ref="HEAD",
        generated_at="2026-10-06T00:00:00Z",
        articles=[
            ArticleGapStatus(
                article="Art. 11",
                status=GapStatus.MISSING,
                source=ArticleGapSource.ARTIFACT,
                evidence_ref="technical_documentation",
                rationale="no technical documentation found",
            )
        ],
    )
    written = render_recommendations(report, tmp_path)
    assert [p.name for p in written] == ["art11-art11_technical_documentation.md"]
    assert "opencomplai docs generate" in written[0].read_text(encoding="utf-8")


def test_new_entries_are_flagged_for_review():
    tmap = load_template_map()
    for key in ARTICLE_KEYS:
        entry = tmap[key]
        assert isinstance(entry["source"], str)
        assert entry["source"]
        assert entry["confidence"] == "low"
        assert entry["needs_founder_review"] is True


def test_summit_added_rows_are_flagged_for_review():
    tmap = load_template_map()
    for key in SUMMIT_ROW_KEYS:
        for entry in [tmap[key], *tmap[key].get("also", [])]:
            assert isinstance(entry.get("source"), str), key
            assert entry["source"], key
            assert entry.get("confidence") == "low", key
            assert entry.get("needs_founder_review") is True, key


def test_every_markdown_template_file_is_mapped():
    mapped = set()
    for e in load_template_map().values():
        mapped.add(e["file"])
        mapped.update(x["file"] for x in e.get("also", []))
    for path in TEMPLATES_DIR.glob("*.md"):
        assert path.name in mapped or path.name == "generic_requirement.md", path.name
