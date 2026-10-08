"""Presentation-only backlog ordering for gap rows (`--sort priority`).

Order: actionable rows first, then earliest deadline, worst status, smallest
effort, original position. Deadlines are read from the regulatory timeline
(`regulatory_timeline.py`, per-article `applies_from`, nulls ignored); this
module never writes dates. Effort (S/M/L) is a maintainer engineering estimate
stored in `template_map.json`, not a compliance claim. No clock is read, so no
relative days exist anywhere (E-14). `build_gap_report` and `GapReport.articles`
keep article order; only renderers call `sort_rows`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from enum import StrEnum
from typing import Any

from opencomplai_core.gap_report import STATUS_SEVERITY
from opencomplai_core.models import ArticleGapStatus, GapStatus
from opencomplai_core.regulatory_timeline import timeline_for_articles

EFFORT_RANK = {"S": 0, "M": 1, "L": 2}


class SortOrder(StrEnum):
    article = "article"
    priority = "priority"


def effort_for(article: str) -> str | None:
    # Lazy import: recommend_engine imports this module.
    from opencomplai_core.recommend_engine import load_template_map

    return load_template_map().get(article, {}).get("effort")


def deadline_for(article: str) -> date | None:
    """Earliest known `applies_from` for an EU article, else None."""
    if not article.startswith("Art. "):
        return None
    known = [e.applies_from for e in timeline_for_articles([article]) if e.applies_from]
    return date.fromisoformat(min(known)) if known else None


def _deadline(article: str, deadlines: Mapping[str, date] | None) -> date | None:
    return deadlines.get(article) if deadlines is not None else deadline_for(article)


def sort_rows(
    rows: Sequence[ArticleGapStatus],
    order: SortOrder = SortOrder.article,
    *,
    deadlines: Mapping[str, date] | None = None,
) -> list[ArticleGapStatus]:
    if order is not SortOrder.priority:
        return list(rows)

    def key(item: tuple[int, ArticleGapStatus]) -> tuple[Any, ...]:
        index, row = item
        return (
            row.status is GapStatus.MET,
            _deadline(row.article, deadlines) or date.max,
            -STATUS_SEVERITY[row.status],
            EFFORT_RANK.get(effort_for(row.article) or "", 99),
            index,
        )

    return [row for _, row in sorted(enumerate(rows), key=key)]


def build_backlog(
    rows: Sequence[ArticleGapStatus], *, deadlines: Mapping[str, date] | None = None
) -> list[dict[str, Any]]:
    ordered = sort_rows(rows, SortOrder.priority, deadlines=deadlines)
    todo = [r for r in ordered if r.status is not GapStatus.MET]
    out: list[dict[str, Any]] = []
    for rank, row in enumerate(todo, start=1):
        due = _deadline(row.article, deadlines)
        out.append(
            {
                "rank": rank,
                "article": row.article,
                "status": row.status.value,
                "deadline": due.isoformat() if due else None,
                "effort": effort_for(row.article),
            }
        )
    return out
