"""Compare two gap reports: added, removed and changed verdicts plus the rule-set delta.

Pure and deterministic: no I/O and no clock.
"""

from __future__ import annotations

from opencomplai_core.gap_report import STATUS_SEVERITY
from opencomplai_core.models import FrameworkReport, GapReport, GapStatus
from opencomplai_core.ruleset_history import entries_between


def _rows(
    report: GapReport, extra: dict[str, FrameworkReport] | None
) -> dict[str, GapStatus]:
    """article id -> status; the worst status wins on a duplicated id."""
    rows = list(report.articles)
    for key, fw in (extra or {}).items():
        if key != "EU_AI_ACT":  # its rows duplicate the main report
            rows.extend(fw.report.articles)
    out: dict[str, GapStatus] = {}
    for r in rows:
        prev = out.get(r.article)
        if prev is None or STATUS_SEVERITY[r.status] > STATUS_SEVERITY[prev]:
            out[r.article] = r.status
    return out


def _rule_set(a: str | None, b: str | None) -> dict:
    changed = None if a is None or b is None else a != b
    changes: list[dict] = []
    if changed:
        try:
            changes = entries_between(a, b)
        except ValueError:  # a non-numeric stamp: still "changed", no entries
            changes = []
    return {"from": a, "to": b, "changed": changed, "changes": changes}


def diff_gap_reports(
    a: GapReport,
    b: GapReport,
    *,
    a_rule_set: str | None = None,
    b_rule_set: str | None = None,
    extra_a: dict[str, FrameworkReport] | None = None,
    extra_b: dict[str, FrameworkReport] | None = None,
) -> dict:
    ra, rb = _rows(a, extra_a), _rows(b, extra_b)
    added = [
        {"article": k, "status": rb[k].value} for k in sorted(rb.keys() - ra.keys())
    ]
    removed = [
        {"article": k, "status": ra[k].value} for k in sorted(ra.keys() - rb.keys())
    ]
    changed = []
    for k in sorted(ra.keys() & rb.keys()):
        if ra[k] == rb[k]:
            continue
        changed.append(
            {
                "article": k,
                "from": ra[k].value,
                "to": rb[k].value,
                "direction": (
                    "worse"
                    if STATUS_SEVERITY[rb[k]] > STATUS_SEVERITY[ra[k]]
                    else "better"
                ),
            }
        )
    regressions = [c["article"] for c in changed if c["direction"] == "worse"]
    return {
        "added": added,
        "removed": removed,
        "changed": changed,
        "unchanged_count": len(ra.keys() & rb.keys()) - len(changed),
        "regressions": regressions,
        "regression": bool(regressions),
        "rule_set": _rule_set(a_rule_set, b_rule_set),
    }
