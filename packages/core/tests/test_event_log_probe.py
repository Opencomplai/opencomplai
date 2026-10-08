"""Art. 12 reads a real event-log probe (SU-20b1): file presence, Partial at most."""

from __future__ import annotations

from pathlib import Path

import pytest
from opencomplai_core.gap_probes import (
    PROBE_PROVENANCE,
    STUB_SOURCE_REFS,
    artifact_gap_status,
)
from opencomplai_core.gap_report import build_gap_report, load_gap_article_map
from opencomplai_core.models import GapStatus


@pytest.fixture(autouse=True)
def _fresh_map():
    load_gap_article_map.cache_clear()
    yield
    load_gap_article_map.cache_clear()


def _ref() -> str:
    sources = load_gap_article_map()["Art. 12"]["sources"]
    return next(s["ref"] for s in sources if s["kind"] == "artifact")


def _art12(root: Path):
    report = build_gap_report("s", "HEAD", repo_root=root)
    return next(r for r in report.articles if r.article == "Art. 12")


def test_oversight_log_in_repo_is_partial_never_met(tmp_path):
    log = tmp_path / ".opencomplai" / "oversight-log.json"
    log.parent.mkdir()
    log.write_text('{"seq": 1}\n', encoding="utf-8")
    row = artifact_gap_status(_ref(), tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.evidence_ref == ".opencomplai/oversight-log.json"
    assert _art12(tmp_path).status == GapStatus.PARTIAL


def test_no_event_log_is_missing(tmp_path):
    (tmp_path / "other.json").write_text("{}", encoding="utf-8")
    assert artifact_gap_status(_ref(), tmp_path).status == GapStatus.MISSING
    assert _art12(tmp_path).status == GapStatus.MISSING


def test_event_log_evidence_is_not_a_stub():
    assert _ref() == "event_log_evidence"
    assert _ref() not in STUB_SOURCE_REFS["artifact"]


def test_probe_has_provenance():
    p = PROBE_PROVENANCE["event_log_evidence"]
    assert p["confidence"] == "low"
    assert p["needs_founder_review"] is True
    assert "Art. 12" in p["source"]
