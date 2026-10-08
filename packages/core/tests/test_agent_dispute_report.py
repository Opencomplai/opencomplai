"""Agent dispute report: window, determinism, both native layouts, no clock."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import opencomplai_core.agent_dispute_report as adr
import opencomplai_core.bridges.agt as agt
import pytest
from opencomplai_core.agent_dispute_report import (
    build_dispute_report,
    import_native,
    normalise_native,
    parse_bound,
    render_markdown,
)
from opencomplai_core.bridges.agt import INTEGRITY_LABEL, ImportedRecord, import_jsonl

FIX = Path(__file__).parent / "fixtures" / "agt_audit"
AGT = FIX / "sample_agt.jsonl"
NATIVE = FIX / "sample_native.jsonl"


def _report(window=("2026-03-01", "2026-03-03"), agent=None, res=None):
    res = res or import_jsonl(AGT)
    return build_dispute_report(
        res.records,
        start=parse_bound(window[0], end=False),
        end=parse_bound(window[1], end=True),
        agent_id=agent,
        source_label="agt",
        file_sha256=res.file_sha256,
        integrity=res.integrity,
        rejected=res.rejected,
    )


def _rec(line, ts, agent="a"):
    return ImportedRecord(line, ts, agent, "act", "allow", None, None, None, "0" * 64)


def test_markdown_renders_from_agt_fixture():
    md = render_markdown(_report())
    assert md.startswith("# Agent dispute report")
    assert "6 in window, 0 undated, 1 rejected" in md
    assert f"Integrity: {INTEGRITY_LABEL}" in md
    assert "Evidence status: partial (cap)" in md
    for heading in ("## Summary", "## Timeline", "## Limits"):
        assert heading in md
    assert "| agent-alpha | 3 |" in md
    assert "| deny | 1 |" in md
    assert (
        "| 2026-03-02T14:05:30Z | agent-beta | refund_payment | Refund a synthetic order "
        "| approval_required | needs-human-approval | reviewer-one |  |"
    ) in md
    assert md.index("2026-03-01T09:15:00Z") < md.index("2026-03-03T08:30:45Z")


def test_json_shape_is_stable():
    d = _report().to_json_dict()
    assert list(d) == [
        "window",
        "agent_filter",
        "source",
        "file_sha256",
        "integrity",
        "evidence_status",
        "counts",
        "per_decision",
        "per_agent",
        "rows",
        "limits",
    ]
    assert d["evidence_status"] == "partial"
    assert d["counts"] == {"in_window": 6, "undated": 0, "rejected": 1}
    assert list(d["rows"][0]) == [
        "ts",
        "agent",
        "action",
        "told",
        "decision",
        "why",
        "approver",
        "outside_mandate",
    ]
    json.dumps(d)


def test_window_filters_inclusive():
    recs = [
        _rec(1, "2026-03-01T09:59:59Z"),
        _rec(2, "2026-03-01T10:00:00Z"),
        _rec(3, "2026-03-02T23:59:59Z"),
        _rec(4, "2026-03-03T00:00:00Z"),
    ]
    rep = build_dispute_report(
        recs,
        start=parse_bound("2026-03-01T10:00:00", end=False),
        end=parse_bound("2026-03-02", end=True),
        source_label="x",
        file_sha256="0",
        integrity="i",
    )
    assert [r["ts"] for r in rep.rows] == [
        "2026-03-01T10:00:00Z",
        "2026-03-02T23:59:59Z",
    ]
    exact = parse_bound("2026-03-01T10:00:00Z", end=True)
    rep = build_dispute_report(
        recs[1:2],
        start=exact,
        end=exact,
        source_label="x",
        file_sha256="0",
        integrity="i",
    )
    assert len(rep.rows) == 1


def test_date_only_to_covers_whole_day():
    assert parse_bound("2026-03-02", end=True) > datetime(
        2026, 3, 2, 23, 59, 59, tzinfo=UTC
    )
    assert parse_bound("2026-03-02", end=False) == datetime(2026, 3, 2, tzinfo=UTC)
    d = _report(("2026-03-03", "2026-03-03")).to_json_dict()
    assert d["counts"]["in_window"] == 2


def test_agent_filter():
    rep = _report(agent="agent-beta")
    assert {r["agent"] for r in rep.rows} == {"agent-beta"}
    assert len(rep.rows) == 3


def test_undated_records_counted_not_listed():
    recs = [_rec(1, None), _rec(2, "not a date"), _rec(3, "2026-03-01T00:00:00Z")]
    rep = build_dispute_report(
        recs,
        start=parse_bound("2026-03-01", end=False),
        end=parse_bound("2026-03-01", end=True),
        source_label="x",
        file_sha256="0",
        integrity="i",
    )
    assert rep.undated == 2
    assert len(rep.rows) == 1


def test_report_is_deterministic():
    a, b = render_markdown(_report()), render_markdown(_report())
    assert a == b
    assert render_markdown(_report(res=import_jsonl(AGT))) == a


def test_native_log_normalises_both_layouts():
    nested = {
        "seq": 1,
        "ts": "2026-03-01T09:00:00+00:00",
        "payload": {
            "agent_id": "a1",
            "intent": "do it",
            "tool": "search",
            "outcome": "success",
            "mandate_ref": "m1",
            "outside_mandate": True,
        },
    }
    flat = {**nested["payload"], "ts": nested["ts"], "seq": 1}
    a, b = normalise_native([nested])[0], normalise_native([flat])[0]
    for r in (a, b):
        assert (r.told, r.action, r.decision, r.rule) == (
            "do it",
            "search",
            "success",
            "m1",
        )
        assert (r.agent_id, r.ts, r.outside_mandate) == ("a1", nested["ts"], True)
    res = import_native(NATIVE)
    assert len(res.records) == 5
    assert [r.outside_mandate for r in res.records] == [False, True, False, False, True]
    assert res.status.value == "partial"


def test_native_report_has_native_limits():
    res = import_native(NATIVE)
    rep = build_dispute_report(
        res.records,
        start=parse_bound("2026-03-01", end=False),
        end=parse_bound("2026-03-03", end=True),
        source_label="native",
        file_sha256=res.file_sha256,
        integrity=res.integrity,
        caveats=res.caveats,
    )
    assert len(rep.rows) == 5
    assert "agents verify-log" in render_markdown(rep)


def test_report_has_no_current_date():
    for mod in (adr, agt):
        src = Path(mod.__file__).read_text(encoding="utf-8")
        for needle in ("datetime.now", "date.today", "utcnow", "time.time"):
            assert needle not in src, (mod.__name__, needle)


def test_empty_window_still_renders():
    rep = _report(("2030-01-01", "2030-01-02"))
    md = render_markdown(rep)
    assert "0 in window" in md
    assert "## Timeline" in md
    assert "## Limits" in md
    assert rep.to_json_dict()["rows"] == []


@pytest.mark.parametrize("bad", ["", "yesterday", "2026-13-01", "2026-03-01T25:00:00"])
def test_invalid_bound_raises(bad):
    with pytest.raises(ValueError, match="invalid date"):
        parse_bound(bad, end=False)
