"""Optional Inspect-AI eval bridge — maps Inspect eval-log output into
`EvaluatorResult`/`EvalSummary` shapes.

HARD RULE (moat preservation): `inspect_ai` is imported lazily, inside function bodies
only, and only when this module is explicitly invoked (`opencomplai eval --suite
inspect-ai`). This module must never be imported by `opencomplai check`'s default
(deterministic, air-gapped) path. Install with:
`pip install opencomplai-core[inspect-bridge]`.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from opencomplai_core.evaluators._hashing import evaluator_evidence_hash
from opencomplai_core.models import EvaluatorCategory, EvaluatorOutcome, EvaluatorResult

INSPECT_SUITE_NAME = "inspect-ai"
_MANIFEST_PATH = Path(__file__).resolve().parent / "task_manifest.json"


@lru_cache(maxsize=1)
def load_task_manifest() -> dict[str, Any]:
    with _MANIFEST_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def curated_task_names() -> list[str]:
    return list(load_task_manifest().get("tasks", {}).keys())


def is_inspect_available() -> bool:
    """Whether the optional `inspect-ai` dependency is importable."""
    try:
        import inspect_ai  # noqa: F401
    except ImportError:
        return False
    return True


def _require_inspect():
    try:
        import inspect_ai
    except ImportError as exc:
        msg = (
            "The Inspect-AI eval bridge requires the optional 'inspect-bridge' extra: "
            "pip install 'opencomplai-core[inspect-bridge]'"
        )
        raise ImportError(msg) from exc
    return inspect_ai


def eval_log_to_evaluator_result(
    task_name: str,
    accuracy: float,
    sample_count: int,
    threshold: float = 0.8,
) -> EvaluatorResult:
    """Map a single Inspect eval-log task result into an `EvaluatorResult`."""
    outcome = EvaluatorOutcome.PASS if accuracy >= threshold else EvaluatorOutcome.FAIL
    evaluator_id = f"EVAL_INSPECT_{task_name.upper()}_V1"
    result = EvaluatorResult(
        evaluator_id=evaluator_id,
        category=EvaluatorCategory.SAFETY,
        outcome=outcome,
        score=round(accuracy, 6),
        threshold=threshold,
        metric_name="inspect_accuracy",
        sample_count=sample_count,
        findings=[f"inspect_task={task_name}", "source=inspect_ai_eval_log"],
        reference=f"Inspect-AI benchmark task: {task_name} (via Inspect bridge, non-deterministic)",
        evidence_hash="",
    )
    result.evidence_hash = evaluator_evidence_hash(evaluator_id, INSPECT_SUITE_NAME, result)
    return result


def _accuracy_from_eval_log(log: Any) -> tuple[float, int]:
    """Best-effort accuracy extraction from an Inspect EvalLog-like object."""
    sample_count = 0
    accuracy = 0.0
    results = getattr(log, "results", None)
    if results is None and isinstance(log, dict):
        results = log.get("results")
    if results is None:
        return accuracy, sample_count

    scores = getattr(results, "scores", None)
    if scores is None and isinstance(results, dict):
        scores = results.get("scores")
    if not scores:
        return accuracy, sample_count

    first = scores[0]
    metrics = getattr(first, "metrics", None)
    if metrics is None and isinstance(first, dict):
        metrics = first.get("metrics", {})
    if isinstance(metrics, dict):
        for key in ("accuracy", "acc", "score"):
            metric = metrics.get(key)
            if metric is None:
                continue
            value = getattr(metric, "value", None)
            if value is None and isinstance(metric, dict):
                value = metric.get("value")
            if value is None and isinstance(metric, (int, float)):
                value = metric
            if isinstance(value, (int, float)):
                accuracy = float(value)
                break

    completed = getattr(results, "completed_samples", None)
    if completed is None and isinstance(results, dict):
        completed = results.get("completed_samples")
    if isinstance(completed, int):
        sample_count = completed
    return accuracy, sample_count


def run_inspect_suite(
    task_names: list[str],
    model: str,
    api_key: str,
    *,
    log_dir: Path | str | None = None,
    limit: int | None = None,
) -> list[EvaluatorResult]:
    """Run curated Inspect-AI tasks and map results to EvaluatorResult.

    Requires `inspect-ai`. Resolves tasks from the Inspect registry by name.
    Never called from `opencomplai check`.
    """
    inspect_ai = _require_inspect()
    manifest = load_task_manifest()
    known = manifest.get("tasks", {})
    if not task_names:
        task_names = list(known.keys())

    unknown = [t for t in task_names if t not in known]
    if unknown:
        msg = (
            f"Unknown Inspect-AI pin task(s): {unknown}. "
            f"Curated pin: {sorted(known)}"
        )
        raise ValueError(msg)

    tasks = list(task_names)

    eval_kwargs: dict[str, Any] = {
        "model": model,
    }
    if log_dir is not None:
        eval_kwargs["log_dir"] = str(log_dir)
    if limit is not None:
        eval_kwargs["limit"] = limit

    # API key for OpenAI-compatible models via env is standard for Inspect;
    # callers should set OPENAI_API_KEY (or provider-specific vars) themselves.
    # We accept api_key for future wiring / documentation consistency.
    if api_key and not __import__("os").environ.get("OPENAI_API_KEY"):
        __import__("os").environ["OPENAI_API_KEY"] = api_key

    logs = inspect_ai.eval(tasks, **eval_kwargs)
    if not isinstance(logs, list):
        logs = [logs]

    results: list[EvaluatorResult] = []
    for task_name, log in zip(task_names, logs, strict=False):
        threshold = float(known[task_name].get("threshold", 0.8))
        accuracy, sample_count = _accuracy_from_eval_log(log)
        results.append(
            eval_log_to_evaluator_result(
                task_name,
                accuracy=accuracy,
                sample_count=sample_count,
                threshold=threshold,
            )
        )
    return results


def suite_generated_at() -> str:
    return datetime.now(UTC).isoformat()
