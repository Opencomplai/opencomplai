"""Tests for thin artifact probes and MCP detector registration."""

from __future__ import annotations

from pathlib import Path

from opencomplai_core.gap_probes import artifact_gap_status
from opencomplai_core.gap_report import build_gap_report, load_gap_article_map
from opencomplai_core.models import GapStatus, SignalCategory
from opencomplai_core.scanner.registry import DETECTOR_REGISTRY


def test_gap_map_covers_seventeen_articles():
    load_gap_article_map.cache_clear()
    articles = set(load_gap_article_map())
    for art in ("Art. 9", "Art. 13", "Art. 14", "Art. 16", "Art. 24", "Art. 43"):
        assert art in articles
    assert len(articles) >= 17


def test_artifact_probe_finds_risk_register(tmp_path: Path):
    (tmp_path / "risk_register.json").write_text('{"risks":[]}', encoding="utf-8")
    row = artifact_gap_status("risk_register", tmp_path)
    assert row.status == GapStatus.PARTIAL


def test_agents_detector_registered():
    ids = {d.detector_id for d in DETECTOR_REGISTRY}
    assert "DET_AGENTS_MCP_V1" in ids
    assert SignalCategory.MCP_SERVER.value == "mcp_server"


def test_gap_report_with_repo_root_runs_probes(tmp_path: Path):
    load_gap_article_map.cache_clear()
    report = build_gap_report("sys", "HEAD", repo_root=tmp_path)
    art9 = next(r for r in report.articles if r.article == "Art. 9")
    assert art9.status in {GapStatus.MISSING, GapStatus.PARTIAL, GapStatus.UNVERIFIED}
