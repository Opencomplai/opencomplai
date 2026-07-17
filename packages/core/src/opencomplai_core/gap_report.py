"""Build a per-article Met/Partial/Missing/Unverified gap report (opencomplai gaps).

This module performs no new analysis — it is a pure, deterministic projection of
already-computed rule (`RiskResult`), obligation (`compliance_checker` catalog),
scan (`CorroborationReport`), and evaluator (`EvalReport`) outputs onto the EU AI
Act article taxonomy, plus thin artifact path probes. The Article -> source mapping
lives in `data/gap_article_map.json`.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from opencomplai_core.compliance_checker.catalog import load_obligations
from opencomplai_core.gap_probes import artifact_gap_status
from opencomplai_core.models import (
    ArticleGapSource,
    ArticleGapStatus,
    ConfidenceLabel,
    CorroborationReport,
    EvalReport,
    GapReport,
    GapStatus,
    RiskResult,
)

_DATA_DIR = Path(__file__).resolve().parent / "data"


@lru_cache(maxsize=1)
def load_gap_article_map() -> dict[str, Any]:
    path = _DATA_DIR / "gap_article_map.json"
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _with_honesty(
    row: ArticleGapStatus,
    *,
    confidence: float | None,
    label: ConfidenceLabel,
) -> ArticleGapStatus:
    return row.model_copy(
        update={
            "confidence": confidence,
            "confidence_label": label,
            "disclaimer_ref": "DISCLAIMER_V1",
        }
    )


def _rule_status(rule_id: str, risk_result: RiskResult) -> ArticleGapStatus | None:
    for rule in risk_result.rule_results:
        if rule.rule_id == rule_id:
            return _with_honesty(
                ArticleGapStatus(
                    article="",
                    status=GapStatus.MET if rule.passed else GapStatus.MISSING,
                    source=ArticleGapSource.RULE,
                    evidence_ref=rule.rule_id,
                    rationale=rule.rationale,
                ),
                confidence=0.9,
                label=ConfidenceLabel.MEASURED,
            )
    return None


def _obligation_status(obligation_id: str) -> ArticleGapStatus | None:
    obligations = load_obligations()
    obligation = obligations.get(obligation_id)
    if obligation is None:
        return None
    return _with_honesty(
        ArticleGapStatus(
            article="",
            status=GapStatus.UNVERIFIED,
            source=ArticleGapSource.OBLIGATION,
            evidence_ref=obligation_id,
            rationale=f"Obligation '{obligation.title}' applies; no automated verification run.",
        ),
        confidence=None,
        label=ConfidenceLabel.NOT_ASSESSED,
    )


def _scan_status(
    signal_category: str, corroboration_report: CorroborationReport
) -> ArticleGapStatus | None:
    matched = [
        finding
        for finding in corroboration_report.findings
        if finding.signal_category.value == signal_category
    ]
    if not matched:
        return None

    is_discrepancy = signal_category in corroboration_report.discrepancies
    if is_discrepancy:
        return _with_honesty(
            ArticleGapStatus(
                article="",
                status=GapStatus.MISSING,
                source=ArticleGapSource.SCAN,
                evidence_ref=matched[0].finding_id,
                rationale=(
                    f"Scan detected '{signal_category}' evidence not reflected in the "
                    f"declared manifest purpose ({len(matched)} finding(s))."
                ),
            ),
            confidence=0.6,
            label=ConfidenceLabel.HEURISTIC_ESTIMATE,
        )
    return _with_honesty(
        ArticleGapStatus(
            article="",
            status=GapStatus.MET,
            source=ArticleGapSource.SCAN,
            evidence_ref=matched[0].finding_id,
            rationale=(
                f"{len(matched)} scan finding(s) for signal category '{signal_category}', "
                "consistent with declaration."
            ),
        ),
        confidence=0.65,
        label=ConfidenceLabel.HEURISTIC_ESTIMATE,
    )


def _evaluator_status(evaluator_id: str, eval_report: EvalReport) -> ArticleGapStatus | None:
    for result in eval_report.results:
        if result.evaluator_id == evaluator_id:
            if result.outcome.value == "pass":
                status = GapStatus.MET
            elif result.outcome.value == "skipped":
                status = GapStatus.UNVERIFIED
            else:
                status = GapStatus.MISSING if result.outcome.value == "fail" else GapStatus.PARTIAL
            label = (
                ConfidenceLabel.NOT_ASSESSED
                if result.outcome.value == "skipped"
                else ConfidenceLabel.MEASURED
            )
            return _with_honesty(
                ArticleGapStatus(
                    article="",
                    status=status,
                    source=ArticleGapSource.EVALUATOR,
                    evidence_ref=result.evidence_hash,
                    rationale=f"{evaluator_id} ({result.reference}): {result.outcome.value}.",
                ),
                confidence=result.score if result.outcome.value != "skipped" else None,
                label=label,
            )
    return None


def build_gap_report(
    system_id: str,
    commit_ref: str,
    risk_result: RiskResult | None = None,
    corroboration_report: CorroborationReport | None = None,
    eval_report: EvalReport | None = None,
    repo_root: Path | None = None,
) -> GapReport:
    """Project rule/obligation/scan/eval/artifact outputs into a per-article gap report."""
    article_map = load_gap_article_map()
    articles: list[ArticleGapStatus] = []

    for article, config in article_map.items():
        sources = config.get("sources", [])
        row: ArticleGapStatus | None = None

        for source in sources:
            kind = source["kind"]
            ref = source["ref"]
            candidate: ArticleGapStatus | None = None

            if kind == "rule" and risk_result is not None:
                candidate = _rule_status(ref, risk_result)
            elif kind == "obligation":
                candidate = _obligation_status(ref)
            elif kind == "scan" and corroboration_report is not None:
                candidate = _scan_status(ref, corroboration_report)
            elif kind == "evaluator" and eval_report is not None:
                candidate = _evaluator_status(ref, eval_report)
            elif kind == "artifact":
                candidate = artifact_gap_status(ref, repo_root)

            if candidate is None:
                continue

            if row is None:
                row = candidate
            elif candidate.status in (GapStatus.MISSING, GapStatus.PARTIAL) and row.status not in (
                GapStatus.MISSING,
                GapStatus.PARTIAL,
            ):
                row = candidate

        if row is None:
            fallback_kind = sources[0]["kind"] if sources else "rule"
            try:
                source_enum = ArticleGapSource(fallback_kind)
            except ValueError:
                source_enum = ArticleGapSource.RULE
            row = _with_honesty(
                ArticleGapStatus(
                    article=article,
                    status=GapStatus.UNVERIFIED,
                    source=source_enum,
                    evidence_ref="none",
                    rationale="No source data supplied for this article in this run.",
                ),
                confidence=None,
                label=ConfidenceLabel.NOT_ASSESSED,
            )
        else:
            row = row.model_copy(update={"article": article})

        articles.append(row)

    return GapReport(
        system_id=system_id,
        commit_ref=commit_ref,
        generated_at=datetime.now(UTC).isoformat(),
        articles=articles,
    )
