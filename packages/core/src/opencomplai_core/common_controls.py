"""Common-control read model: which pack rows cite the same evidence source.

A common control is one `(kind, ref)` pair that rows of one or more framework
packs cite in their `sources`. The model lists the rows that share it. It is a
projection of pack data: a verdict is never copied from one row to another.
With an artifact, each row carries the status the artifact holds for that row.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from opencomplai_core.frameworks import (
    CUSTOM_FRAMEWORK_PREFIX,
    FRAMEWORKS,
    FrameworkPack,
    framework_of,
    pack_requirements,
)

# Source kinds that name a piece of evidence. Attestation, rule, obligation
# and crosswalk sources are left out.
CONTROL_KINDS: frozenset[str] = frozenset(
    {"artifact", "evaluator", "scan", "manifest", "record"}
)
_CREDITED = frozenset({"met", "partial"})


@dataclass(frozen=True)
class CommonControlRow:
    framework: str
    requirement_id: str
    title: str
    role: str | None
    status: str | None


@dataclass(frozen=True)
class CommonControl:
    kind: str
    ref: str
    frameworks: list[str] = field(default_factory=list)
    rows: list[CommonControlRow] = field(default_factory=list)
    credited_rows: int = 0


def _article_statuses(report: Any) -> dict[str, str]:
    if not isinstance(report, Mapping):
        return {}
    out: dict[str, str] = {}
    for item in report.get("articles") or []:
        if isinstance(item, Mapping) and "article" in item and "status" in item:
            out[str(item["article"])] = str(item["status"]).lower()
    return out


def artifact_statuses(artifact: Any) -> dict[str, str]:
    """Requirement id -> status held by the artifact's reports.

    EU AI Act rows come from `gap_report`; other rows from `framework_reports`.
    Raises ValueError when the artifact is not a JSON object.
    """
    if not isinstance(artifact, Mapping):
        raise ValueError("artifact must be a JSON object")
    statuses = _article_statuses(artifact.get("gap_report"))
    reports = artifact.get("framework_reports")
    if isinstance(reports, Mapping):
        for entry in reports.values():
            if isinstance(entry, Mapping):
                statuses.update(_article_statuses(entry.get("report")))
    return statuses


def build_common_controls(
    packs: Mapping[str, FrameworkPack] | None = None,
    artifact: Any = None,
) -> list[CommonControl]:
    """Common controls across native packs, most-shared first, then by ref."""
    source_packs = FRAMEWORKS if packs is None else packs
    statuses = artifact_statuses(artifact) if artifact is not None else None

    grouped: dict[tuple[str, str], dict[str, CommonControlRow]] = {}
    for key, pack in source_packs.items():
        if key.startswith(CUSTOM_FRAMEWORK_PREFIX):
            continue
        requirements = pack_requirements(pack)
        if requirements is None:
            continue
        for req_id, entry in requirements.items():
            if not isinstance(entry, Mapping):
                continue
            title = entry.get("title")
            for src in entry.get("sources") or []:
                if not isinstance(src, Mapping):
                    continue
                kind, ref = src.get("kind"), src.get("ref")
                if kind not in CONTROL_KINDS or not isinstance(ref, str):
                    continue
                holder = grouped.setdefault((kind, ref), {})
                holder.setdefault(
                    req_id,
                    CommonControlRow(
                        framework=framework_of(req_id),
                        requirement_id=req_id,
                        title=title if isinstance(title, str) else req_id,
                        role=src.get("role"),
                        status=None if statuses is None else statuses.get(req_id),
                    ),
                )

    controls: list[CommonControl] = []
    for (kind, ref), by_id in grouped.items():
        rows = sorted(by_id.values(), key=lambda r: (r.framework, r.requirement_id))
        frameworks = sorted({r.framework for r in rows})
        credited = sum(1 for r in rows if r.status in _CREDITED)
        controls.append(CommonControl(kind, ref, frameworks, rows, credited))
    controls.sort(key=lambda c: (-len(c.frameworks), c.ref, c.kind))
    return controls
