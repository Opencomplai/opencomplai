"""Re-project a GapReport's per-article rows into NIST AI RMF 1.0
subcategory verdicts (CP-16, D-3c; per-subcategory mapping since FWMAP).

Pure re-projection of already-computed EU-AI-Act-native evidence
(`gap_report.py`) -- this module adds NO new scanner, evaluator, or probe.
It mirrors `principle_report.py`'s worst-case rollup pattern (same
`STATUS_SEVERITY` ranking), keyed by each subcategory's own `eu_ai_act`
list in `data/nist_ai_rmf_subcategories.json`, and it additionally
propagates that mapping's confidence: a subcategory mapped only at
`confidence="low"` is never reported as more confident than that, no matter
how "measured" the underlying EU AI Act evidence is.

A subcategory whose `eu_ai_act` list is empty has no EU AI Act evidence to
re-project. It reads UNVERIFIED / not_assessed until the provider records an
attestation under `framework_inputs.NIST_AI_RMF.attested`, and Met /
attested once they do. A subcategory that has EU AI Act evidence takes no
attestation: its verdict comes from that evidence only.
"""

from __future__ import annotations

from collections.abc import Mapping

from opencomplai_core.gap_report import STATUS_SEVERITY
from opencomplai_core.models import (
    ArticleGapSource,
    ArticleGapStatus,
    Attestation,
    ConfidenceLabel,
    GapReport,
    GapStatus,
    NistRmfReport,
    RmfFunction,
    RmfSubcategoryStatus,
)
from opencomplai_core.nist_ai_rmf_subcategories import get_subcategories

_CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2}
_PREFIX = "NIST_AI_RMF:"


def attestable_subcategories() -> set[str]:
    """Prefixed ids of the subcategories that take an attestation: those the
    EU AI Act evidence holds nothing for."""
    return {
        f"{_PREFIX}{subcat_id}"
        for subcat_id, entry in get_subcategories().items()
        if not entry.eu_ai_act
    }


def _unassessed(
    subcat_id: str,
    function: str,
    category: str,
    rationale: str,
    source_articles: list[str],
) -> RmfSubcategoryStatus:
    return RmfSubcategoryStatus(
        subcategory=subcat_id,
        function=RmfFunction(function),
        category=category,
        status=GapStatus.UNVERIFIED,
        mapping_confidence=None,
        confidence_label=ConfidenceLabel.NOT_ASSESSED,
        source_eu_ai_act_articles=source_articles,
        rationale=rationale,
    )


def build_nist_rmf_report(
    gap_report: GapReport, attested: Mapping[str, Attestation] | None = None
) -> NistRmfReport:
    """Re-project `gap_report.articles` into a per-subcategory NIST AI RMF
    report using each subcategory's `eu_ai_act` mapping.

    Every re-projected row cites the exact EU AI Act article(s)
    (`source_eu_ai_act_articles`) and the mapping confidence it was derived
    from -- never a fabricated or silently-upgraded verdict. A subcategory
    whose mapped articles are absent from this run's `gap_report` is
    UNVERIFIED with `confidence_label=NOT_ASSESSED`. `attested` is the
    manifest's `framework_inputs.NIST_AI_RMF.attested`; it is read only for
    subcategories with no EU AI Act mapping.
    """
    attested = attested or {}
    status_by_article: dict[str, ArticleGapStatus] = {
        row.article: row for row in gap_report.articles
    }

    rows: list[RmfSubcategoryStatus] = []
    for subcat_id, entry in get_subcategories().items():
        if not entry.eu_ai_act:
            attestation = attested.get(f"{_PREFIX}{subcat_id}")
            if attestation is None:
                rows.append(
                    _unassessed(
                        subcat_id,
                        entry.function,
                        entry.category,
                        (
                            "The EU AI Act evidence holds nothing for this "
                            "subcategory. Add an attestation under "
                            "framework_inputs.NIST_AI_RMF.attested in the manifest."
                        ),
                        [],
                    )
                )
            else:
                rows.append(
                    RmfSubcategoryStatus(
                        subcategory=subcat_id,
                        function=RmfFunction(entry.function),
                        category=entry.category,
                        status=GapStatus.MET,
                        mapping_confidence=None,
                        confidence_label=ConfidenceLabel.ATTESTED,
                        rationale=attestation.statement,
                    )
                )
            continue

        present = [
            (article, status_by_article[article], confidence)
            for article, confidence in entry.eu_ai_act
            if article in status_by_article
        ]

        if not present:
            mapped = [article for article, _ in entry.eu_ai_act]
            rows.append(
                _unassessed(
                    subcat_id,
                    entry.function,
                    entry.category,
                    (
                        f"{subcat_id} maps to {', '.join(mapped)}, but none of "
                        "those articles are present in this gap report run."
                    ),
                    mapped,
                )
            )
            continue

        worst_status = max(
            (status.status for _, status, _ in present),
            key=lambda s: STATUS_SEVERITY[s],
        )
        # Never upgrade: take the lowest (worst) mapping confidence among the
        # contributing articles -- conservative unless well-established.
        mapping_confidence = min(
            (confidence for _, _, confidence in present),
            key=lambda c: _CONFIDENCE_RANK[c],
        )
        citations = "; ".join(
            f"{article} -> {status.status.value} "
            f"(source={status.source.value}, evidence={status.evidence_ref})"
            for article, status, _ in present
        )
        rationale = (
            f"Re-projected via data/nist_ai_rmf_subcategories.json (mapping "
            f"confidence={mapping_confidence}) from existing EU AI Act "
            f"evidence: {citations}."
        )

        rows.append(
            RmfSubcategoryStatus(
                subcategory=subcat_id,
                function=RmfFunction(entry.function),
                category=entry.category,
                status=worst_status,
                mapping_confidence=mapping_confidence,
                # A re-projection is a heuristic aid regardless of the
                # underlying article evidence's own confidence label -- it is
                # never a legal determination.
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


def nist_rmf_as_gap_report(
    gap_report: GapReport, attested: Mapping[str, Attestation] | None = None
) -> GapReport:
    """The NIST AI RMF re-projection as a GapReport, for side-by-side runs.

    One row per subcategory, id prefixed "NIST_AI_RMF:", sourced CROSSWALK
    (ATTESTATION for attested rows) and citing the EU AI Act articles it was
    derived from. Verdicts and labels come unchanged from
    `build_nist_rmf_report`; a re-projection carries no numeric confidence.
    """
    attested = attested or {}
    nist = build_nist_rmf_report(gap_report, attested)
    articles = []
    for row in nist.subcategories:
        rid = f"{_PREFIX}{row.subcategory}"
        if row.confidence_label is ConfidenceLabel.ATTESTED:
            attestation = attested[rid]
            source = ArticleGapSource.ATTESTATION
            evidence_ref = (
                f"attestation:{attestation.attested_by}@{attestation.attested_at}"
            )
        else:
            source = ArticleGapSource.CROSSWALK
            evidence_ref = ", ".join(row.source_eu_ai_act_articles) or "none"
        articles.append(
            ArticleGapStatus(
                article=rid,
                status=row.status,
                source=source,
                evidence_ref=evidence_ref,
                rationale=row.rationale,
                confidence=None,
                confidence_label=row.confidence_label,
                disclaimer_ref="DISCLAIMER_V2",
            )
        )
    return GapReport(
        system_id=nist.system_id,
        commit_ref=nist.commit_ref,
        generated_at=nist.generated_at,
        articles=articles,
    )
