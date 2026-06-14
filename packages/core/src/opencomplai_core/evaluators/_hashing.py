"""Canonical hashing for evaluator evidence (no raw samples)."""

from __future__ import annotations

import hashlib
import json

from opencomplai_core.models import EvaluatorResult


def evaluator_evidence_hash(
    evaluator_id: str, sample_set_id: str, result: EvaluatorResult
) -> str:
    canonical = {
        "evaluator_id": evaluator_id,
        "eval_set_id": sample_set_id,
        "outcome": result.outcome.value,
        "score": round(result.score, 6),
        "metric_name": result.metric_name,
        "findings": sorted(result.findings),
        "skip_reason": result.skip_reason,
    }
    digest = hashlib.sha256(
        json.dumps(canonical, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return f"sha256:{digest}"
