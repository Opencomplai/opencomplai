"""Backlog ordering (`--sort priority`): key order, shape, renderers."""

from datetime import date
from pathlib import Path

from opencomplai_core import backlog
from opencomplai_core.backlog import (
    SortOrder,
    build_backlog,
    deadline_for,
    effort_for,
    sort_rows,
)
from opencomplai_core.models import (
    ArticleGapSource,
    ArticleGapStatus,
    GapReport,
    GapStatus,
    SystemManifest,
)
from opencomplai_core.recommend_engine import render_recommendations
from opencomplai_core.report_engine import render_report

_EFFORT_ARTICLES = [
    *(f"Art. {n}" for n in (4, 5, 6, 9, 10, 11, 12, 13, 14, 15, 16, 17)),
    *(f"Art. {n}" for n in (24, 25, 26, 27, 43, 49, 50, 53, 55, 72, 73)),
]


def _row(article: str, status: GapStatus) -> ArticleGapStatus:
    return ArticleGapStatus(
        article=article,
        status=status,
        source=ArticleGapSource.RULE,
        evidence_ref="test",
    )


def _report(rows: list[ArticleGapStatus]) -> GapReport:
    return GapReport(
        system_id="s",
        commit_ref="HEAD",
        generated_at="2026-07-11T00:00:00Z",
        articles=rows,
    )


def _names(rows: list[ArticleGapStatus]) -> list[str]:
    return [r.article for r in rows]


def test_sort_key_order():
    p = SortOrder.priority
    early, late = date(2026, 1, 1), date(2027, 1, 1)
    # deadline beats severity: Art. 4 is only PARTIAL but due first.
    rows = [_row("Art. 9", GapStatus.MISSING), _row("Art. 4", GapStatus.PARTIAL)]
    dl = {"Art. 9": late, "Art. 4": early}
    assert _names(sort_rows(rows, p, deadlines=dl)) == ["Art. 4", "Art. 9"]
    # severity beats effort: Art. 15 (L, MISSING) before Art. 4 (S, PARTIAL).
    rows = [_row("Art. 4", GapStatus.PARTIAL), _row("Art. 15", GapStatus.MISSING)]
    dl = {"Art. 4": early, "Art. 15": early}
    assert _names(sort_rows(rows, p, deadlines=dl)) == ["Art. 15", "Art. 4"]
    # effort breaks ties: S (Art. 4) before L (Art. 15), same status and date.
    rows = [_row("Art. 15", GapStatus.MISSING), _row("Art. 4", GapStatus.MISSING)]
    assert _names(sort_rows(rows, p, deadlines=dl)) == ["Art. 4", "Art. 15"]
    # full ties keep input order (neither FW row has an effort).
    rows = [_row("FW:b", GapStatus.MISSING), _row("FW:a", GapStatus.MISSING)]
    assert _names(sort_rows(rows, p, deadlines={})) == ["FW:b", "FW:a"]
    # MET rows last, even with the earliest deadline.
    rows = [_row("Art. 4", GapStatus.MET), _row("Art. 9", GapStatus.UNVERIFIED)]
    dl = {"Art. 4": early, "Art. 9": late}
    assert _names(sort_rows(rows, p, deadlines=dl)) == ["Art. 9", "Art. 4"]


def test_article_order_is_identity():
    rows = [_row("Art. 9", GapStatus.MISSING), _row("Art. 4", GapStatus.MET)]
    assert sort_rows(rows) == rows
    assert sort_rows(rows, SortOrder.article) == rows


def test_missing_deadline_and_effort_sort_last():
    p = SortOrder.priority
    rows = [
        _row("FW:x", GapStatus.MISSING),  # no deadline, no effort
        _row("Art. 15", GapStatus.MISSING),  # effort L, no deadline
        _row("Art. 4", GapStatus.MISSING),  # effort S, dated
    ]
    out = sort_rows(rows, p, deadlines={"Art. 4": date(2030, 1, 1)})
    assert _names(out) == ["Art. 4", "Art. 15", "FW:x"]
    assert deadline_for("FW:x") is None
    assert effort_for("FW:x") is None


def test_build_backlog_shape_and_no_met_rows():
    rows = [
        _row("Art. 4", GapStatus.MET),
        _row("Art. 15", GapStatus.PARTIAL),
        _row("Art. 9", GapStatus.MISSING),
    ]
    out = build_backlog(rows, deadlines={"Art. 9": date(2026, 8, 2)})
    assert out == [
        {
            "rank": 1,
            "article": "Art. 9",
            "status": "missing",
            "deadline": "2026-08-02",
            "effort": "M",
        },
        {
            "rank": 2,
            "article": "Art. 15",
            "status": "partial",
            "deadline": None,
            "effort": "L",
        },
    ]


def test_effort_for_reads_template_map():
    for article in _EFFORT_ARTICLES:
        assert effort_for(article) in {"S", "M", "L"}, article
    assert effort_for("Art. 999") is None
    assert (
        backlog.EFFORT_RANK["S"] < backlog.EFFORT_RANK["M"] < backlog.EFFORT_RANK["L"]
    )


def test_render_recommendations_priority_order(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        backlog, "deadline_for", lambda a: date(2026, 1, 1) if a == "Art. 10" else None
    )
    report = _report(
        [_row("Art. 9", GapStatus.MISSING), _row("Art. 10", GapStatus.MISSING)]
    )
    plain = render_recommendations(report, tmp_path / "a")
    ordered = render_recommendations(report, tmp_path / "b", sort=SortOrder.priority)
    assert [p.name.split("-")[0] for p in plain] == ["art9", "art10"]
    assert [p.name.split("-")[0] for p in ordered] == ["art10", "art9"]
    assert {p.name for p in plain} == {p.name for p in ordered}


def test_render_report_priority_order(monkeypatch):
    monkeypatch.setattr(
        backlog, "deadline_for", lambda a: date(2026, 1, 1) if a == "Art. 10" else None
    )
    manifest = SystemManifest(
        system_id="s",
        commit_ref="HEAD",
        intended_purpose="x",
        compliance_target="EU_AI_ACT",
    )
    report = _report(
        [_row("Art. 9", GapStatus.MISSING), _row("Art. 10", GapStatus.MISSING)]
    )

    def table(**kw) -> str:
        html = render_report(manifest, gap_report=report, **kw)
        start = html.index('id="gap-table"')  # envelope timestamp varies per call
        return html[start : html.index("</table>", start)]

    default = table()
    assert default == table(sort=SortOrder.article)
    assert default.index("Art. 9") < default.index("Art. 10")
    ordered = table(sort=SortOrder.priority)
    assert ordered.index("Art. 10") < ordered.index("Art. 9")
