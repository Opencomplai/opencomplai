"""Pipeline evaluation engine — runs all registered evaluators."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from opencomplai_core.evaluators.registry import EVAL_SET_VERSION, EVALUATOR_REGISTRY
from opencomplai_core.models import (
    EvalReport,
    EvalSampleSet,
    EvaluatorOutcome,
    EvaluatorResult,
)


def threshold_policy_hash(sample_set: EvalSampleSet) -> str:
    canonical = json.dumps(sample_set.threshold_overrides, sort_keys=True)
    return f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"


def validate_eval_sample_set(sample_set: EvalSampleSet) -> None:
    """Raise ValueError when aligned fairness arrays have mismatched lengths."""
    if not sample_set.predictions and not sample_set.labels:
        return
    n = len(sample_set.predictions)
    if len(sample_set.labels) != n:
        raise ValueError(
            "predictions and labels must have equal length when bias eval runs"
        )
    for name, groups in sample_set.protected_attributes.items():
        if len(groups) != n:
            raise ValueError(
                f"protected_attributes[{name!r}] length must match predictions"
            )


def eval_run_id(
    tenant_id: str,
    system_id: str,
    commit_ref: str,
    eval_set_id: str,
    eval_set_version: str,
    threshold_policy_hash: str,
) -> str:
    raw = "|".join(
        [
            tenant_id,
            system_id,
            commit_ref,
            eval_set_id,
            eval_set_version,
            threshold_policy_hash,
        ]
    )
    return f"sha256:{hashlib.sha256(raw.encode()).hexdigest()}"


def run_evals(
    system_id: str,
    commit_ref: str,
    sample_set: EvalSampleSet,
) -> EvalReport:
    """
    Run all registered evaluators against the sample set.

    Deterministic: same input always yields the same EvalReport (modulo generated_at).
    """
    if sample_set.system_id != system_id:
        raise ValueError("sample_set.system_id must match system_id")
    if sample_set.commit_ref != commit_ref:
        raise ValueError("sample_set.commit_ref must match commit_ref")

    validate_eval_sample_set(sample_set)

    policy_hash = threshold_policy_hash(sample_set)
    results: list[EvaluatorResult] = []
    for evaluator in EVALUATOR_REGISTRY:
        results.append(evaluator.evaluate(sample_set))

    failed = [r for r in results if r.outcome == EvaluatorOutcome.FAIL]
    warned = [r for r in results if r.outcome == EvaluatorOutcome.WARN]
    skipped = [r for r in results if r.outcome == EvaluatorOutcome.SKIPPED]

    if failed:
        overall = EvaluatorOutcome.FAIL
    elif warned:
        overall = EvaluatorOutcome.WARN
    else:
        overall = EvaluatorOutcome.PASS

    return EvalReport(
        system_id=system_id,
        commit_ref=commit_ref,
        eval_set_id=sample_set.eval_set_id,
        eval_set_version=EVAL_SET_VERSION,
        threshold_policy_hash=policy_hash,
        results=results,
        evaluators_run=len(results) - len(skipped),
        evaluators_failed=len(failed),
        evaluators_skipped=len(skipped),
        overall_outcome=overall,
        generated_at=datetime.now(UTC).isoformat(),
    )


def eval_summary_from_report(report: EvalReport):
    """Build EvalSummary for ScanStatusArtifact."""
    from opencomplai_core.models import EvalSummary

    failed_ids = [
        r.evaluator_id for r in report.results if r.outcome == EvaluatorOutcome.FAIL
    ]
    skipped = {
        r.evaluator_id: r.skip_reason or "skipped"
        for r in report.results
        if r.outcome == EvaluatorOutcome.SKIPPED
    }
    return EvalSummary(
        eval_set_id=report.eval_set_id,
        eval_set_version=report.eval_set_version,
        threshold_policy_hash=report.threshold_policy_hash,
        overall_outcome=report.overall_outcome,
        failed_evaluator_ids=failed_ids,
        skipped_evaluators=skipped,
        evidence_hashes=[r.evidence_hash for r in report.results],
    )
