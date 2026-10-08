"""
Per-agent dispute report: what an agent was told, decided and why, for a window.

Pure functions over `ImportedRecord`s (from `bridges.agt` or a native agent
decision log). No clock: the window is explicit and no generation date is
printed (E-14), so the same input gives identical bytes. The report is evidence
only, labelled with the log's integrity label, and capped at PARTIAL.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from pathlib import Path

from opencomplai_core.agent_log_verify import decision_fields
from opencomplai_core.bridges.agt import (
    _MAX,
    _SAMPLES,
    CAVEATS,
    ImportedRecord,
    ImportResult,
    cap_status,
    json_lines,
)
from opencomplai_core.models import GapStatus

NATIVE_INTEGRITY = (
    "format-valid, not verified here (use `opencomplai agents verify-log`)"
)
# E-15: report limitation sentences are flagged data, no legal commentary.
NATIVE_CAVEATS = (
    "Integrity is not verified by this report; verify the chain with `agents verify-log`.",
    "A chain cannot show that the newest entries were not removed.",
    CAVEATS[3],
)


def _s(value) -> str | None:
    if value is None:
        return None
    text = value if isinstance(value, str) else json.dumps(value, sort_keys=True)
    return text[:_MAX]


def normalise_native(entries: list[dict]) -> list[ImportedRecord]:
    out = []
    for i, entry in enumerate(entries, 1):
        f = decision_fields(entry)
        body = entry.get("payload")
        body = body if isinstance(body, dict) else entry
        flag = f["outside_mandate"]
        out.append(
            ImportedRecord(
                line=i,
                ts=_s(f["ts"]),
                agent_id=_s(f["agent_id"]),
                action=_s(f["tool"]),
                decision=_s(body.get("outcome")),
                rule=_s(body.get("mandate_ref")),
                told=_s(body.get("intent")),
                approver=None,
                raw_sha256=hashlib.sha256(
                    json.dumps(entry, sort_keys=True).encode("utf-8")
                ).hexdigest(),
                outside_mandate=flag if isinstance(flag, bool) else None,
            )
        )
    return out


def import_native(path: Path) -> ImportResult:
    data = Path(path).read_bytes()
    entries, samples, total = [], [], 0
    for no, _raw, obj, reason in json_lines(data):
        total += 1
        if obj is None:
            if len(samples) < _SAMPLES:
                samples.append((no, reason))
        else:
            entries.append(obj)
    records = normalise_native(entries)
    return ImportResult(
        records=tuple(records),
        total_lines=total,
        rejected=total - len(entries),
        rejected_samples=tuple(samples),
        file_sha256=hashlib.sha256(data).hexdigest(),
        status=cap_status(GapStatus.MET) if records else GapStatus.UNVERIFIED,
        integrity=NATIVE_INTEGRITY,
        caveats=NATIVE_CAVEATS,
    )


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def parse_bound(value: str, *, end: bool) -> datetime:
    """ISO date or datetime (UTC when naive); a date-only `end` is the end of that day."""
    try:
        if len(value) == 10:
            d = date.fromisoformat(value)
            return datetime.combine(d, time.max if end else time.min, tzinfo=UTC)
        return _utc(datetime.fromisoformat(value))
    except ValueError:
        raise ValueError(f"invalid date or datetime: {value!r}") from None


def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class DisputeReport:
    start: datetime
    end: datetime
    agent_id: str | None
    source_label: str
    file_sha256: str
    integrity: str
    rows: tuple[dict, ...]
    undated: int
    rejected: int
    per_decision: dict[str, int]
    per_agent: dict[str, int]
    caveats: tuple[str, ...]

    def to_json_dict(self) -> dict:
        return {
            "window": {"from": _fmt(self.start), "to": _fmt(self.end)},
            "agent_filter": self.agent_id,
            "source": self.source_label,
            "file_sha256": self.file_sha256,
            "integrity": self.integrity,
            "evidence_status": GapStatus.PARTIAL.value,
            "counts": {
                "in_window": len(self.rows),
                "undated": self.undated,
                "rejected": self.rejected,
            },
            "per_decision": self.per_decision,
            "per_agent": self.per_agent,
            "rows": list(self.rows),
            "limits": list(self.caveats),
        }


def _when(ts: str | None) -> datetime | None:
    try:
        return _utc(datetime.fromisoformat(ts)) if ts else None
    except ValueError:
        return None


def build_dispute_report(
    records,
    *,
    start: datetime,
    end: datetime,
    agent_id: str | None = None,
    source_label: str,
    file_sha256: str,
    integrity: str,
    rejected: int = 0,
    caveats: tuple[str, ...] = CAVEATS,
) -> DisputeReport:
    dated, undated = [], 0
    for r in records:
        when = _when(r.ts)
        if when is None:
            undated += 1
        elif start <= when <= end and (agent_id is None or r.agent_id == agent_id):
            dated.append((when, r.line, r))
    dated.sort(key=lambda t: (t[0], t[1]))
    rows = tuple(
        {
            "ts": _fmt(w),
            "agent": r.agent_id,
            "action": r.action,
            "told": r.told,
            "decision": r.decision,
            "why": r.rule,
            "approver": r.approver,
            "outside_mandate": r.outside_mandate,
        }
        for w, _n, r in dated
    )
    by_decision = Counter(r["decision"] or "(none)" for r in rows)
    by_agent = Counter(r["agent"] or "(unknown)" for r in rows)
    return DisputeReport(
        start=_utc(start),
        end=_utc(end),
        agent_id=agent_id,
        source_label=source_label,
        file_sha256=file_sha256,
        integrity=integrity,
        rows=rows,
        undated=undated,
        rejected=rejected,
        per_decision=dict(sorted(by_decision.items())),
        per_agent=dict(sorted(by_agent.items())),
        caveats=caveats,
    )


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _table(head: list[str], body: list[list]) -> list[str]:
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    lines += ["| " + " | ".join(_cell(c) for c in row) + " |" for row in body]
    return lines


_COLS = (
    "ts",
    "agent",
    "action",
    "told",
    "decision",
    "why",
    "approver",
    "outside_mandate",
)


def render_markdown(report: DisputeReport) -> str:
    win = report.to_json_dict()["window"]
    out = [
        "# Agent dispute report",
        "",
        f"- Window (UTC, inclusive): {win['from']} to {win['to']}",
        f"- Agent filter: {report.agent_id or 'all agents'}",
        f"- Source: {report.source_label} (sha256 {report.file_sha256})",
        f"- Records: {len(report.rows)} in window, {report.undated} undated, "
        f"{report.rejected} rejected",
        f"- Integrity: {report.integrity}",
        "- Evidence status: partial (cap)",
        "",
        "## Summary",
        "",
        *_table(
            ["Decision", "Count"], [[k, v] for k, v in report.per_decision.items()]
        ),
        "",
        *_table(["Agent", "Count"], [[k, v] for k, v in report.per_agent.items()]),
        "",
        "## Timeline",
        "",
        *_table(
            [
                "Time (UTC)",
                "Agent",
                "Action",
                "Told",
                "Decision",
                "Why",
                "Approver",
                "Outside mandate",
            ],
            [[r[c] for c in _COLS] for r in report.rows],
        ),
        "",
        "## Limits",
        "",
        *[f"- {c}" for c in report.caveats],
        "",
    ]
    return "\n".join(out)
