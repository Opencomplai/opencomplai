"""Roll up a GapReport's per-article rows into the 6 EU Trustworthy AI principles.

Pure data-driven re-projection of already-computed article statuses (see
`gap_report.py`) — introduces no new analysis logic, no exit-code impact, and no
interaction with signing/evidence.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from opencomplai_core.models import GapReport, GapStatus, PrincipleStatus, PrincipleSummary

_DATA_PATH = Path(__file__).resolve().parent / "data" / "eu_ai_act_principles.json"

_STATUS_SEVERITY = {
    GapStatus.MISSING: 3,
    GapStatus.PARTIAL: 2,
    GapStatus.UNVERIFIED: 1,
    GapStatus.MET: 0,
}


@lru_cache(maxsize=1)
def load_principle_map() -> dict:
    return json.loads(_DATA_PATH.read_text(encoding="utf-8"))


def build_principle_summary(gap_report: GapReport) -> PrincipleSummary:
    """Roll up gap_report.articles into a per-principle worst-case status.

    A principle's status is the most severe status among its mapped articles
    (MISSING > PARTIAL > UNVERIFIED > MET) — matching the existing gap-report
    convention where a MISSING/PARTIAL finding wins over a MET/UNVERIFIED one.
    Articles not present in gap_report.articles are simply not counted.
    """
    principle_map = load_principle_map()["principles"]
    status_by_article = {row.article: row.status for row in gap_report.articles}

    principles: list[PrincipleStatus] = []
    for principle_id, config in principle_map.items():
        mapped_articles = config["articles"]
        present_statuses = [
            status_by_article[article]
            for article in mapped_articles
            if article in status_by_article
        ]
        if not present_statuses:
            rollup_status = GapStatus.UNVERIFIED
        else:
            rollup_status = max(present_statuses, key=lambda s: _STATUS_SEVERITY[s])

        principles.append(
            PrincipleStatus(
                principle_id=principle_id,
                title=config["title"],
                status=rollup_status,
                articles=mapped_articles,
            )
        )

    return PrincipleSummary(principles=principles)
