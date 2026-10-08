"""Art. 72 and Art. 73 read real evidence (SU-30a)."""

from __future__ import annotations

import json
from pathlib import Path

from opencomplai_core import gap_probes
from opencomplai_core.framework_crosswalk import get_crosswalk
from opencomplai_core.gap_probes import (
    _PROBE_PATTERNS,
    INCIDENT_LOG_PATH,
    STUB_SOURCE_REFS,
    qms_clause_results,
)
from opencomplai_core.gap_report import build_gap_report, load_gap_article_map
from opencomplai_core.models import GapStatus
from opencomplai_core.recommend_engine import load_template_map, render_recommendations
from opencomplai_core.signed_log import SignedLog
from opencomplai_core.signing import SigningDomain

_CORE = Path(__file__).resolve().parents[1]
_DATA = _CORE / "src" / "opencomplai_core" / "data"
_PACKAGES = _CORE.parent
_PLAN = "docs/post-market-monitoring-plan.md"
_FILLED_PLAN = (
    "# Post-market monitoring plan\n\n"
    "We monitor accuracy and complaints for version 2 every month and review the "
    "findings with the product owner before each release.\n"
)
_PAYLOAD = {
    "note": "Model returned wrong refund amounts to several customers during one week"
}


def _row(root: Path | None, article: str):
    report = build_gap_report("s", "HEAD", repo_root=root)
    return next(r for r in report.articles if r.article == article)


def _write_log(root: Path) -> None:
    SignedLog(root / INCIDENT_LOG_PATH, SigningDomain.INCIDENT_LOG).append(
        _PAYLOAD, ts="2026-01-01T00:00:00Z"
    )


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _rendered(tmp_path: Path, name: str) -> str:
    root = tmp_path / "render-src"
    root.mkdir(exist_ok=True)
    report = build_gap_report("s", "HEAD", repo_root=root)
    written = {p.name: p for p in render_recommendations(report, tmp_path / "out")}
    return written[name].read_text(encoding="utf-8")


def test_art72_73_unverified_without_repo_root():
    for article in ("Art. 72", "Art. 73"):
        assert _row(None, article).status == GapStatus.UNVERIFIED


def test_art72_missing_without_plan(tmp_path):
    row = _row(tmp_path, "Art. 72")
    assert row.status == GapStatus.MISSING


def test_art72_scaffold_plan_is_low_confidence_partial(tmp_path):
    _write(tmp_path, _PLAN, _rendered(tmp_path, "art72-post_market_monitoring_plan.md"))
    row = _row(tmp_path, "Art. 72")
    assert row.status == GapStatus.PARTIAL
    assert row.confidence is not None
    assert row.confidence <= 0.4


def test_art72_filled_plan_is_partial_never_met(tmp_path):
    _write(tmp_path, _PLAN, _FILLED_PLAN)
    row = _row(tmp_path, "Art. 72")
    assert row.status == GapStatus.PARTIAL
    assert row.status != GapStatus.MET
    assert row.confidence is not None
    assert row.confidence > 0.4


def test_art73_missing_without_incident_log(tmp_path):
    assert _row(tmp_path, "Art. 73").status == GapStatus.MISSING


def test_art73_incident_log_is_partial_never_met(tmp_path):
    _write_log(tmp_path)
    row = _row(tmp_path, "Art. 73")
    assert row.status == GapStatus.PARTIAL
    assert row.status != GapStatus.MET
    assert row.confidence is not None
    assert row.confidence > 0.4


def test_art73_log_without_chain_line_is_low_confidence(tmp_path):
    for text in ("", json.dumps([{"note": "an incident was logged here"}])):
        _write(tmp_path, INCIDENT_LOG_PATH, text)
        row = _row(tmp_path, "Art. 73")
        assert row.status == GapStatus.PARTIAL
        assert row.confidence is not None
        assert row.confidence <= 0.4


def test_incident_log_feeds_qms_clauses_h_and_i(tmp_path):
    before = {r.letter: r.label for r in qms_clause_results(tmp_path)}
    assert before["h"] == before["i"] == "Missing"
    _write_log(tmp_path)
    after = {r.letter: r.label for r in qms_clause_results(tmp_path)}
    assert after["h"] == after["i"] == "Present"


def test_incident_log_path_is_defined_once():
    assert INCIDENT_LOG_PATH == "incident-log.json"
    for ref in ("serious_incident_log", "provider_qms_17_1_h", "provider_qms_17_1_i"):
        assert _PROBE_PATTERNS[ref][-1] == INCIDENT_LOG_PATH
    offenders = [
        str(p)
        for p in _PACKAGES.rglob("*.py")
        if "tests" not in p.parts
        and ".venv" not in p.parts
        and p != Path(gap_probes.__file__)
        and INCIDENT_LOG_PATH in p.read_text(encoding="utf-8", errors="replace")
    ]
    assert not offenders


def test_art72_73_refs_are_real_probes_not_stubs():
    for ref in ("post_market_monitoring_plan", "serious_incident_log"):
        assert ref in _PROBE_PATTERNS
        assert ref not in STUB_SOURCE_REFS["artifact"]


def test_templates_are_mapped_flagged_and_render(tmp_path):
    tmap = load_template_map()
    assert tmap["Art. 72"]["template_id"] == "post_market_monitoring_plan"
    assert tmap["Art. 73"]["template_id"] == "serious_incident_report"
    for article in ("Art. 72", "Art. 73"):
        entry = tmap[article]
        assert entry["source"]
        assert entry["confidence"] == "low"
        assert entry["needs_founder_review"] is True
    for name in (
        "art72-post_market_monitoring_plan.md",
        "art73-serious_incident_report.md",
    ):
        text = _rendered(tmp_path, name)
        assert "{{" not in text
        assert gap_probes.SCAFFOLD_PLACEHOLDER in text


def test_rendered_plan_round_trips_as_unfilled(tmp_path):
    text = _rendered(tmp_path, "art72-post_market_monitoring_plan.md")
    repo = tmp_path / "repo"
    _write(repo, _PLAN, text)
    row = _row(repo, "Art. 72")
    assert row.status == GapStatus.PARTIAL
    assert row.confidence is not None
    assert row.confidence <= 0.4


def test_crosswalk_rows_for_art72_73_stay_flagged():
    crosswalk = get_crosswalk()
    for article in ("Art. 72", "Art. 73"):
        assert crosswalk[article].needs_founder_review is True
        assert crosswalk[article].confidence == "low"
    assert {"Art. 72", "Art. 73"} <= set(load_gap_article_map())


def test_ruleset_history_records_the_art72_73_wiring():
    history = json.loads((_DATA / "ruleset_history.json").read_text("utf-8"))
    entry = next(e for e in history if e["version"] == "1.6.0")
    assert any(
        c.startswith("Art. 72 and Art. 73 now read real evidence")
        for c in entry["changes"]
    )
