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

A subcategory with no EU AI Act evidence to re-project reads UNVERIFIED /
not_assessed until the provider records an attestation under
`framework_inputs.NIST_AI_RMF.attested`, and Met / attested once they do. That
is a subcategory whose `eu_ai_act` list is empty, or whose mapped articles are
all decided by an attestation themselves (GOVERN 2.2 maps only to Art. 4). A
subcategory that has EU AI Act evidence takes no attestation: its verdict comes
from that evidence only.

An EU AI Act row whose status comes from an attestation counts as no evidence
for NIST. Otherwise an attestation of Art. 4, which maps to GOVERN 2.2 and MAP
3.4, would read as a Met NIST subcategory nobody attested (ADR-framework-packs
2026-11c).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime

from opencomplai_core.gap_report import (
    STATUS_SEVERITY,
    attestation_evidence_ref,
    attestation_expiry_text,
    load_gap_article_map,
)
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


def _attestation_only_articles() -> set[str]:
    """EU AI Act articles whose every source is an attestation."""
    return {
        article
        for article, config in load_gap_article_map().items()
        if config.get("sources")
        and all(s["kind"] == "attestation" for s in config["sources"])
    }


def attestable_subcategories() -> set[str]:
    """Prefixed ids of the subcategories that take an attestation: those the
    EU AI Act evidence holds nothing for, because no article maps to them or
    every article that does is decided by an attestation itself."""
    attestation_only = _attestation_only_articles()
    return {
        f"{_PREFIX}{subcat_id}"
        for subcat_id, entry in get_subcategories().items()
        if all(article in attestation_only for article, _ in entry.eu_ai_act)
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
    gap_report: GapReport,
    attested: Mapping[str, Attestation] | None = None,
    today: date | None = None,
) -> NistRmfReport:
    """Re-project `gap_report.articles` into a per-subcategory NIST AI RMF
    report using each subcategory's `eu_ai_act` mapping.

    Every re-projected row cites the exact EU AI Act article(s)
    (`source_eu_ai_act_articles`) and the mapping confidence it was derived
    from -- never a fabricated or silently-upgraded verdict. A subcategory
    whose mapped articles are absent from this run's `gap_report` is
    UNVERIFIED with `confidence_label=NOT_ASSESSED`. `attested` is the
    manifest's `framework_inputs.NIST_AI_RMF.attested`; it is read only for the
    subcategories in `attestable_subcategories()`. An article whose row comes
    from an attestation is no evidence here: it is left out of every
    re-projection and holds the row at Unverified at best, attested or not.
    An attestation whose `valid_until` is before `today`
    (default: the current UTC date) reads Unverified.
    """
    attested = attested or {}
    effective_today = today if today is not None else datetime.now(UTC).date()
    attestable = attestable_subcategories()
    status_by_article: dict[str, ArticleGapStatus] = {}
    set_aside: set[str] = set()
    for row in gap_report.articles:
        if row.source is ArticleGapSource.ATTESTATION:
            set_aside.add(row.article)
        else:
            status_by_article[row.article] = row

    rows: list[RmfSubcategoryStatus] = []
    for subcat_id, entry in get_subcategories().items():
        if f"{_PREFIX}{subcat_id}" in attestable:
            attestation = attested.get(f"{_PREFIX}{subcat_id}")
            expired = (
                attestation_expiry_text(attestation, "NIST_AI_RMF", effective_today)
                if attestation is not None
                else None
            )
            if expired is not None:
                rows.append(
                    _unassessed(subcat_id, entry.function, entry.category, expired, [])
                )
            elif attestation is None:
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

        ignored = [article for article, _ in entry.eu_ai_act if article in set_aside]
        # Said only when it happened, so an ordinary row reads as it always did.
        ignored_note = (
            " Set aside, because an attestation decides it and is no evidence "
            f"for another framework: {', '.join(ignored)}."
            if ignored
            else ""
        )

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
                        f"{ignored_note}"
                    ),
                    mapped,
                )
            )
            continue

        # A set-aside article is no evidence, so it holds the row at Unverified at
        # best, as it did before an attestation could decide it: an attestation
        # never lifts a subcategory through the mapping.
        worst_status = max(
            [status.status for _, status, _ in present]
            + ([GapStatus.UNVERIFIED] if ignored else []),
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
            f"evidence: {citations}.{ignored_note}"
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
    gap_report: GapReport,
    attested: Mapping[str, Attestation] | None = None,
    today: date | None = None,
) -> GapReport:
    """The NIST AI RMF re-projection as a GapReport, for side-by-side runs.

    One row per subcategory, id prefixed "NIST_AI_RMF:", sourced CROSSWALK
    (ATTESTATION for attested rows) and citing the EU AI Act articles it was
    derived from. Verdicts and labels come unchanged from
    `build_nist_rmf_report`; a re-projection carries no numeric confidence. A
    row with an attestation keeps the attestation source and reference even
    when the attestation has expired and the row reads Unverified.
    """
    attested = attested or {}
    nist = build_nist_rmf_report(gap_report, attested, today)
    attestable = attestable_subcategories()
    articles = []
    for row in nist.subcategories:
        rid = f"{_PREFIX}{row.subcategory}"
        attestation = attested.get(rid) if rid in attestable else None
        if attestation is not None:
            source = ArticleGapSource.ATTESTATION
            evidence_ref = attestation_evidence_ref(attestation)
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
