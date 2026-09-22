"""Re-project a GapReport's per-article rows into NIST AI RMF 1.0
subcategory verdicts via the framework crosswalk (CP-16, D-3c).

Pure re-projection of already-computed EU-AI-Act-native evidence
(`gap_report.py`) -- this module adds NO new scanner, evaluator, or probe.
It mirrors `principle_report.py`'s worst-case rollup pattern (same
`STATUS_SEVERITY` ranking), but keyed by `framework_crosswalk.py` instead of
a fixed principle map, and it additionally propagates the crosswalk row's
own mapping confidence: a subcategory whose only crosswalk row is
`confidence="low"` is never reported as more confident than that, no matter
how "measured" the underlying EU AI Act evidence is (see the "evaluated"
definition in `PLAN/CLOSE-P1/00-OVERVIEW.md`'s D-3).

The crosswalk maps at CATEGORY granularity (e.g. "GOVERN 2", not "GOVERN
2.2"), so every subcategory under a mapped category gets the same
re-projected verdict -- this is the honest consequence of the crosswalk's
own resolution, not something this module invents. A subcategory whose
category has no crosswalk row at all (as of CP-16, this is every MANAGE
subcategory -- CP-5's crosswalk has zero MANAGE rows) is reported
UNVERIFIED / not_assessed, never guessed.
"""

from __future__ import annotations

from opencomplai_core.framework_crosswalk import CrosswalkEntry, get_crosswalk
from opencomplai_core.gap_report import STATUS_SEVERITY
from opencomplai_core.models import (
    ArticleGapStatus,
    ConfidenceLabel,
    GapReport,
    GapStatus,
    NistRmfReport,
    RmfSubcategoryStatus,
)
from opencomplai_core.nist_ai_rmf_subcategories import get_subcategories

_CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2}


def _rows_for_category(
    category: str, crosswalk: dict[str, CrosswalkEntry]
) -> list[CrosswalkEntry]:
    return [
        row for row in crosswalk.values() if row.nist_ai_rmf_subcategory == category
    ]


def _unassessed(
    subcat_id: str,
    function: str,
    category: str,
    rationale: str,
    source_articles: list[str],
) -> RmfSubcategoryStatus:
    return RmfSubcategoryStatus(
        subcategory=subcat_id,
        function=function,
        category=category,
        status=GapStatus.UNVERIFIED,
        mapping_confidence=None,
        confidence_label=ConfidenceLabel.NOT_ASSESSED,
        source_eu_ai_act_articles=source_articles,
        rationale=rationale,
    )


def build_nist_rmf_report(gap_report: GapReport) -> NistRmfReport:
    """Re-project `gap_report.articles` into a per-subcategory NIST AI RMF
    report using `data/framework_crosswalk.json` to key the two taxonomies.

    Every row cites the exact EU AI Act article(s) (`source_eu_ai_act_articles`)
    and crosswalk `mapping_confidence` it was derived from -- never a
    fabricated or silently-upgraded verdict. A subcategory with no crosswalk
    coverage, or whose crosswalk-mapped article(s) are absent from this run's
    `gap_report`, is UNVERIFIED with `confidence_label=NOT_ASSESSED`.
    """
    taxonomy = get_subcategories()
    crosswalk = get_crosswalk()
    status_by_article: dict[str, ArticleGapStatus] = {
        row.article: row for row in gap_report.articles
    }

    rows: list[RmfSubcategoryStatus] = []
    for subcat_id, entry in taxonomy.items():
        mapped_rows = _rows_for_category(entry.category, crosswalk)

        if not mapped_rows:
            rows.append(
                _unassessed(
                    subcat_id,
                    entry.function,
                    entry.category,
                    (
                        f"No row in data/framework_crosswalk.json maps any EU AI Act "
                        f"article to {entry.category} -- there is no EU-AI-Act-native "
                        "evidence to re-project onto this subcategory."
                    ),
                    [],
                )
            )
            continue

        present = [
            (row.eu_ai_act_article, status_by_article[row.eu_ai_act_article], row)
            for row in mapped_rows
            if row.eu_ai_act_article in status_by_article
        ]

        if not present:
            mapped_articles = ", ".join(r.eu_ai_act_article for r in mapped_rows)
            rows.append(
                _unassessed(
                    subcat_id,
                    entry.function,
                    entry.category,
                    (
                        f"{entry.category} maps to {mapped_articles} via the crosswalk, "
                        "but none of those articles are present in this gap report run."
                    ),
                    [r.eu_ai_act_article for r in mapped_rows],
                )
            )
            continue

        worst_status = max(
            (status.status for _, status, _ in present),
            key=lambda s: STATUS_SEVERITY[s],
        )
        # Never upgrade: take the lowest (worst) crosswalk mapping confidence
        # among the contributing rows, exactly as CP-5's own confidence
        # values were assigned -- conservative unless well-established.
        mapping_confidence = min(
            (row.confidence for _, _, row in present),
            key=lambda c: _CONFIDENCE_RANK[c],
        )
        citations = "; ".join(
            f"{article} -> {status.status.value} "
            f"(source={status.source.value}, evidence={status.evidence_ref})"
            for article, status, _ in present
        )
        rationale = (
            f"Re-projected via data/framework_crosswalk.json ({entry.category}, "
            f"mapping confidence={mapping_confidence}) from existing EU AI Act "
            f"evidence: {citations}."
        )

        rows.append(
            RmfSubcategoryStatus(
                subcategory=subcat_id,
                function=entry.function,
                category=entry.category,
                status=worst_status,
                mapping_confidence=mapping_confidence,
                # A crosswalk re-projection is a heuristic aid regardless of
                # the underlying article evidence's own confidence label --
                # it is never a legal determination.
                confidence_label=ConfidenceLabel.HEURISTIC_ESTIMATE,
                source_eu_ai_act_articles=[article for article, _, _ in present],
                rationale=rationale,
            )
        )

    return NistRmfReport(
        system_id=gap_report.system_id,
        commit_ref=gap_report.commit_ref,
        generated_at=gap_report.generated_at,
        subcategories=rows,
    )
