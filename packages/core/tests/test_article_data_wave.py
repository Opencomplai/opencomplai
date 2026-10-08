"""Data commit for Art. 26, 49, 72, 73 and the placeholder evidence sources (SU-GM2).

The stub tests read the live ``STUB_SOURCE_REFS`` so the epics that replace a
stub with a real probe need no edit here.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from opencomplai_core.control_catalog import CONTROL_CATALOG
from opencomplai_core.framework_crosswalk import get_crosswalk
from opencomplai_core.frameworks import FRAMEWORKS, data_version
from opencomplai_core.gap_probes import STUB_SOURCE_REFS
from opencomplai_core.gap_report import build_gap_report, load_gap_article_map
from opencomplai_core.models import (
    ArticleGapSource,
    ArticleGapStatus,
    GapReport,
    GapStatus,
)
from opencomplai_core.recommend_engine import load_template_map, render_recommendations

NEW_ARTICLES = ["Art. 26", "Art. 49", "Art. 72", "Art. 73"]
_CORE = Path(__file__).resolve().parents[1]
_DATA = _CORE / "src" / "opencomplai_core" / "data"
_REPO = _CORE.parents[1]


def _is_stub(source: dict) -> bool:
    return source["ref"] in STUB_SOURCE_REFS.get(source["kind"], frozenset())


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "risk_register.md").write_text("# Risks\n", encoding="utf-8")
    (tmp_path / "INSTRUCTIONS.md").write_text("# Instructions\n", encoding="utf-8")
    return tmp_path


def test_existing_rows_are_unchanged_except_the_listed_ones(tmp_path):
    root = _repo(tmp_path)
    real_map = load_gap_article_map()
    old_map = {
        article: {
            **config,
            # manifest sources are real now but need a manifest to read; the
            # "old" shape is the map before any of them existed
            "sources": [
                s
                for s in config["sources"]
                if not _is_stub(s) and s["kind"] != "manifest"
            ],
        }
        for article, config in real_map.items()
        if article not in NEW_ARTICLES
    }
    new = build_gap_report("s", "HEAD", repo_root=root).articles
    old = build_gap_report("s", "HEAD", repo_root=root, requirements=old_map).articles

    assert len(old) == 19
    new_by_article = {row.article: row for row in new}
    for old_row in old:
        expected = old_row.model_dump()
        actual = new_by_article[old_row.article].model_dump()
        assert actual == expected, old_row.article


def test_stub_sources_never_produce_a_row(tmp_path):
    root = _repo(tmp_path)
    rows = {
        r.article: r for r in build_gap_report("s", "HEAD", repo_root=root).articles
    }
    stub_only = [
        article
        for article, config in load_gap_article_map().items()
        if config["sources"] and all(_is_stub(s) for s in config["sources"])
    ]
    # SU-30a replaced the last stub-only articles; the loop below stays for later stubs.
    # Art. 72 and 73 read real evidence since SU-30a: MISSING with a repo root.
    for article in ("Art. 72", "Art. 73"):
        assert article not in stub_only
        assert rows[article].status == GapStatus.MISSING, article
    for article in stub_only:
        row = rows[article]
        assert row.status == GapStatus.UNVERIFIED, article
        assert row.evidence_ref == "none", article
        assert row.status != GapStatus.MISSING


def test_no_article_leads_with_a_manifest_source():
    for article, config in load_gap_article_map().items():
        sources = config["sources"]
        assert not sources or sources[0]["kind"] != "manifest", article


def test_new_articles_are_in_every_data_file():
    principles = json.loads((_DATA / "eu_ai_act_principles.json").read_text("utf-8"))
    listed = {a for p in principles["principles"].values() for a in p["articles"]}
    template_map = load_template_map()
    article_map = load_gap_article_map()
    crosswalk = get_crosswalk()
    for article in NEW_ARTICLES:
        assert article in article_map
        assert article in CONTROL_CATALOG
        assert article in crosswalk
        assert article in template_map
        assert article in listed


def test_new_data_carries_review_flags():
    principles = json.loads((_DATA / "eu_ai_act_principles.json").read_text("utf-8"))
    crosswalk = get_crosswalk()
    template_map = load_template_map()
    for article in NEW_ARTICLES:
        blocks = [
            load_gap_article_map()[article],
            template_map[article],
            principles["review_flags"][article],
        ]
        for block in blocks:
            assert block["source"], article
            assert block["confidence"] in {"low", "medium", "high"}, article
            assert block["needs_founder_review"] is True, article
        row = crosswalk[article]
        assert row.source
        assert row.confidence == "low"
        assert row.needs_founder_review is True


def test_new_templates_render_without_placeholders(tmp_path):
    rows = [
        ArticleGapStatus(
            article=article,
            status=GapStatus.MISSING,
            source=ArticleGapSource.ARTIFACT,
            evidence_ref="x",
            rationale="test rationale",
        )
        for article in NEW_ARTICLES
    ]
    report = GapReport(
        system_id="s",
        commit_ref="HEAD",
        generated_at="2026-01-01T00:00:00Z",
        articles=rows,
    )
    written = {p.name: p for p in render_recommendations(report, tmp_path)}
    for article in ("Art. 26", "Art. 49"):
        name = f"art{article.split()[1]}-eu_obligation_action_plan.md"
        assert name in written
        text = written[name].read_text(encoding="utf-8")
        assert "{{" not in text
        assert article in text


def test_dashboard_fixtures_carry_current_data_versions():
    web = _REPO / "dashboard-saas" / "services" / "web"
    if not (_REPO / "dashboard-saas").is_dir():
        pytest.skip("dashboard-saas/ is absent in this checkout")
    expected = [
        data_version(FRAMEWORKS["EU_AI_ACT"]),
        data_version(FRAMEWORKS["NIST_AI_RMF"]),
    ]
    for path in (web / "demo" / "data.ts", web / "e2e" / "fixtures" / "frameworks.ts"):
        found = re.findall(r'data_version:\s*"([0-9a-f]{12})"', path.read_text("utf-8"))
        assert found == expected, path.name


def test_adr_item_9_is_amended():
    text = (_REPO / "docs" / "adr" / "ADR-framework-packs.md").read_text("utf-8")
    item = re.search(r"^9\. .*?(?=^10\. )", text, re.S | re.M).group(0)
    flat = " ".join(item.split())
    assert "`data_version`" in flat
    assert "frozen per data version" in flat


def test_ruleset_history_records_the_article_wave():
    history = json.loads((_DATA / "ruleset_history.json").read_text("utf-8"))
    entry = next(e for e in history if e["version"] == "1.6.0")
    assert any(
        c.startswith("Added Art. 26, 49, 72 and 73 to the EU article map")
        for c in entry["changes"]
    )
