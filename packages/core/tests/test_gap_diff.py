"""diff_gap_reports: row movements, direction, rule-set delta."""

from __future__ import annotations

import json

from opencomplai_core.gap_diff import diff_gap_reports
from opencomplai_core.models import (
    ArticleGapSource,
    ArticleGapStatus,
    FrameworkReport,
    GapReport,
    GapStatus,
)


def _row(article: str, status: GapStatus, rationale: str = "") -> ArticleGapStatus:
    return ArticleGapStatus(
        article=article,
        status=status,
        source=ArticleGapSource.RULE,
        evidence_ref="r",
        rationale=rationale,
    )


def _report(*rows: ArticleGapStatus) -> GapReport:
    return GapReport(
        system_id="s", commit_ref="c", generated_at="t", articles=list(rows)
    )


def _fw(key: str, *rows: ArticleGapStatus) -> FrameworkReport:
    return FrameworkReport(
        framework=key,
        label=key,
        data_version="x",
        disclaimer_ref="D",
        report=_report(*rows),
    )


M, P, X, U = (
    GapStatus.MET,
    GapStatus.PARTIAL,
    GapStatus.MISSING,
    GapStatus.UNVERIFIED,
)


def test_added_removed_changed_rows():
    a = _report(_row("Art. 9", M), _row("Art. 10", P), _row("Art. 11", X))
    b = _report(_row("Art. 9", M), _row("Art. 10", X), _row("Art. 12", U))
    d = diff_gap_reports(a, b)
    assert d["added"] == [{"article": "Art. 12", "status": "unverified"}]
    assert d["removed"] == [{"article": "Art. 11", "status": "missing"}]
    assert d["changed"] == [
        {"article": "Art. 10", "from": "partial", "to": "missing", "direction": "worse"}
    ]
    assert d["unchanged_count"] == 1
    # added/removed rows are never regressions
    assert d["regressions"] == ["Art. 10"]
    assert d["regression"] is True


def test_worse_and_better_direction():
    a = _report(_row("A", M), _row("B", X), _row("C", U), _row("D", P))
    b = _report(_row("A", U), _row("B", P), _row("C", M), _row("D", X))
    dirs = {c["article"]: c["direction"] for c in diff_gap_reports(a, b)["changed"]}
    assert dirs == {"A": "worse", "B": "better", "C": "better", "D": "worse"}
    improved = diff_gap_reports(b, a)
    assert improved["regressions"] == ["B", "C"]


def test_status_only_change_counts_rationale_change_does_not():
    a = _report(_row("A", M, "old"))
    b = _report(_row("A", M, "new words"))
    d = diff_gap_reports(a, b)
    assert d["changed"] == []
    assert d["unchanged_count"] == 1
    assert d["regression"] is False


def test_rule_set_delta_known_unknown_and_equal():
    r = _report()
    known = diff_gap_reports(r, r, a_rule_set="1.5.0", b_rule_set="1.6.0")["rule_set"]
    assert known["changed"] is True
    assert known["from"] == "1.5.0"
    assert [e["version"] for e in known["changes"]] == ["1.6.0"]
    assert diff_gap_reports(r, r, a_rule_set="1.5.0")["rule_set"]["changed"] is None
    assert diff_gap_reports(r, r)["rule_set"]["changed"] is None
    same = diff_gap_reports(r, r, a_rule_set="1.6.0", b_rule_set="1.6.0")["rule_set"]
    assert same["changed"] is False
    assert same["changes"] == []


def test_framework_rows_are_included_and_eu_key_skipped():
    a = _report(_row("Art. 9", M))
    b = _report(_row("Art. 9", M))
    extra_a = {
        "EU_AI_ACT": _fw("EU_AI_ACT", _row("Art. 9", X)),
        "NIST_AI_RMF": _fw("NIST_AI_RMF", _row("NIST_AI_RMF:GOVERN 1.1", M)),
    }
    extra_b = {
        "EU_AI_ACT": _fw("EU_AI_ACT", _row("Art. 9", X)),
        "NIST_AI_RMF": _fw("NIST_AI_RMF", _row("NIST_AI_RMF:GOVERN 1.1", X)),
    }
    d = diff_gap_reports(a, b, extra_a=extra_a, extra_b=extra_b)
    assert [c["article"] for c in d["changed"]] == ["NIST_AI_RMF:GOVERN 1.1"]
    assert d["unchanged_count"] == 1  # Art. 9 stays MET; EU_AI_ACT key ignored
    # duplicated id: worst status wins
    dup = _report(_row("Z", M), _row("Z", X))
    assert diff_gap_reports(dup, dup)["unchanged_count"] == 1
    assert diff_gap_reports(_report(_row("Z", M)), dup)["changed"][0]["to"] == "missing"


def test_output_is_deterministic_and_sorted():
    a = _report(_row("B", M), _row("A", M), _row("C", M))
    b = _report(_row("C", X), _row("A", X), _row("B", X), _row("E", M), _row("D", M))
    d1, d2 = diff_gap_reports(a, b), diff_gap_reports(a, b)
    assert json.dumps(d1) == json.dumps(d2)
    assert [c["article"] for c in d1["changed"]] == ["A", "B", "C"]
    assert [r["article"] for r in d1["added"]] == ["D", "E"]
    assert d1["regressions"] == ["A", "B", "C"]
