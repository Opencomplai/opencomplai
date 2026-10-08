"""Art. 53 recommend rows also write the copyright and training-summary drafts (SU-135c)."""

from __future__ import annotations

import json
from pathlib import Path

from opencomplai_core import recommend_engine
from opencomplai_core.gpai_training_pack import (
    get_gpai_training_pack,
    render_training_summary_markdown,
)
from opencomplai_core.models import (
    ArticleGapSource,
    ArticleGapStatus,
    GapReport,
    GapStatus,
)
from opencomplai_core.recommend_engine import load_template_map, render_recommendations

TEMPLATES_DIR = Path(recommend_engine.__file__).parent / "templates" / "recommend"
DATA_DIR = Path(recommend_engine.__file__).parent / "data"
ART53_FILES = {
    "art53-gpai_annex_documentation.md",
    "art53-gpai_copyright_policy.md",
    "art53-gpai_training_summary.md",
}


def _written(tmp_path: Path, article: str, status: GapStatus) -> list[Path]:
    row = ArticleGapStatus(
        article=article,
        status=status,
        source=ArticleGapSource.RULE,
        evidence_ref="RULE",
        rationale="r",
    )
    report = GapReport(
        system_id="s",
        commit_ref="HEAD",
        generated_at="2026-07-11T00:00:00Z",
        articles=[row],
    )
    return render_recommendations(report, tmp_path / "out")


def _names(paths: list[Path]) -> set[str]:
    return {p.name for p in paths}


def test_missing_art53_writes_annex_copyright_and_summary_files(tmp_path):
    paths = _written(tmp_path, "Art. 53", GapStatus.MISSING)
    assert ART53_FILES <= _names(paths)
    assert all(p.is_file() for p in paths)


def test_partial_art53_row_also_writes_extras(tmp_path):
    assert ART53_FILES <= _names(_written(tmp_path, "Art. 53", GapStatus.PARTIAL))


def test_met_and_unverified_art53_rows_write_nothing(tmp_path):
    for status in (GapStatus.MET, GapStatus.UNVERIFIED):
        assert _written(tmp_path, "Art. 53", status) == []


def test_training_summary_has_every_section_banner_and_no_placeholder(tmp_path):
    paths = _written(tmp_path, "Art. 53", GapStatus.MISSING)
    path = next(p for p in paths if p.name == "art53-gpai_training_summary.md")
    content = path.read_text(encoding="utf-8")
    raw = json.loads((DATA_DIR / "gpai_training_pack.json").read_text(encoding="utf-8"))
    for section in raw["training_summary_sections"]:
        assert section["title"] in content
    assert render_training_summary_markdown(get_gpai_training_pack()) in content
    assert "Draft: every section below needs founder review" in content
    assert "{{" not in content


def test_copyright_policy_has_review_banner(tmp_path):
    paths = _written(tmp_path, "Art. 53", GapStatus.MISSING)
    path = next(p for p in paths if p.name == "art53-gpai_copyright_policy.md")
    content = path.read_text(encoding="utf-8")
    assert "Draft for founder and lawyer review" in content
    assert "not legal advice" in content
    assert ArticleGapSource.RULE.value in content
    assert "{{" not in content


def test_missing_art55_writes_no_extra_files(tmp_path):
    names = _names(_written(tmp_path, "Art. 55", GapStatus.MISSING))
    assert names == {"art55-gpai_annex_documentation.md"}


def test_also_items_are_flagged_and_files_exist():
    items = [i for e in load_template_map().values() for i in e.get("also", [])]
    assert {i["template_id"] for i in items} == {
        "gpai_copyright_policy",
        "gpai_training_summary",
    }
    for item in items:
        assert isinstance(item["source"], str)
        assert item["source"]
        assert item["confidence"] == "low"
        assert item["needs_founder_review"] is True
        assert item["kind"] == "markdown"
        assert (TEMPLATES_DIR / item["file"]).is_file()


def test_annex_template_names_both_extra_outputs():
    text = (TEMPLATES_DIR / "gpai_annex_documentation.md").read_text(encoding="utf-8")
    assert "art53-gpai_copyright_policy.md" in text
    assert "art53-gpai_training_summary.md" in text
    assert "planned" not in text


def test_docs_pages_name_both_extra_outputs():
    root = Path(__file__).resolve().parents[3]
    for rel in (
        "docs/src/cli/recommend.md",
        "docs/src/frameworks/gpai-training-summary-and-cop.md",
    ):
        text = (root / rel).read_text(encoding="utf-8")
        assert "art53-gpai_copyright_policy.md" in text, rel
        assert "art53-gpai_training_summary.md" in text, rel
