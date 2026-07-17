"""Calibration metrics evaluator (v1 — deterministic, GPAI documentation support).

Measures Expected Calibration Error (ECE): how well a model's confidence scores
(`EvalSampleSet.predictions`, treated as probabilities in [0, 1]) match the actual
outcome rate (`EvalSampleSet.labels`, treated as binary ground truth). Opt-in only —
calibration is GPAI-specific, not universal, so it must not slow down default
`opencomplai eval` runs for non-GPAI systems (gated the same way as 2.4's bundled bias
probe: via an explicit `threshold_overrides` flag, never triggered implicitly).
"""

from __future__ import annotations

from opencomplai_core.evaluators._hashing import evaluator_evidence_hash
from opencomplai_core.evaluators.base import BaseEvaluator
from opencomplai_core.models import (
    EvalSampleSet,
    EvaluatorCategory,
    EvaluatorOutcome,
    EvaluatorResult,
)

_DEFAULT_THRESHOLD = 0.9  # 1.0 - max_acceptable_ECE (ECE <= 0.10 passes by default)
_WARN_BAND = 0.02
_NUM_BINS = 10


def _expected_calibration_error(predictions: list[float], labels: list[float]) -> float:
    """Standard equal-width-bin ECE over confidence scores in [0, 1]."""
    bins: list[list[tuple[float, float]]] = [[] for _ in range(_NUM_BINS)]
    for pred, label in zip(predictions, labels, strict=True):
        clamped = min(max(pred, 0.0), 1.0)
        bin_idx = min(int(clamped * _NUM_BINS), _NUM_BINS - 1)
        bins[bin_idx].append((clamped, label))

    n = len(predictions)
    ece = 0.0
    for bucket in bins:
        if not bucket:
            continue
        bucket_size = len(bucket)
        avg_confidence = sum(p for p, _ in bucket) / bucket_size
        avg_accuracy = sum(label for _, label in bucket) / bucket_size
        ece += (bucket_size / n) * abs(avg_confidence - avg_accuracy)
    return ece


class CalibrationEvaluator(BaseEvaluator):
    @property
    def evaluator_id(self) -> str:
        return "EVAL_CALIBRATION_V1"

    @property
    def category(self) -> EvaluatorCategory:
        return EvaluatorCategory.CALIBRATION

    @property
    def reference(self) -> str:
        return "GPAI documentation support / EU AI Act Art.15 accuracy metrics"

    def evaluate(self, sample_set: EvalSampleSet) -> EvaluatorResult:
        threshold = sample_set.threshold_overrides.get("calibration", _DEFAULT_THRESHOLD)

        # Opt-in only: calibration is GPAI-specific, must never run implicitly on a
        # generic sample set that happens to have predictions/labels populated for a
        # different purpose (e.g. the bias evaluator's binary_classification data).
        if sample_set.threshold_overrides.get("include_calibration") != 1.0:
            return self._skipped(sample_set, threshold, "calibration_not_requested")

        preds = sample_set.predictions
        labels = sample_set.labels

        if not preds or not labels or len(preds) != len(labels):
            return self._skipped(sample_set, threshold, "missing_or_mismatched_predictions_labels")

        ece = _expected_calibration_error(preds, labels)
        score = round(1.0 - ece, 6)

        if score < threshold:
            outcome = EvaluatorOutcome.FAIL
        elif score < threshold + _WARN_BAND:
            outcome = EvaluatorOutcome.WARN
        else:
            outcome = EvaluatorOutcome.PASS

        findings = [f"expected_calibration_error={round(ece, 6)}", f"num_bins={_NUM_BINS}"]

        return self._result(sample_set, threshold, outcome, score, findings)

    def _skipped(
        self, sample_set: EvalSampleSet, threshold: float, reason: str
    ) -> EvaluatorResult:
        return self._result(
            sample_set, threshold, EvaluatorOutcome.SKIPPED, 1.0, [], reason
        )

    def _result(
        self,
        sample_set: EvalSampleSet,
        threshold: float,
        outcome: EvaluatorOutcome,
        score: float,
        findings: list[str],
        skip_reason: str | None = None,
    ) -> EvaluatorResult:
        result = EvaluatorResult(
            evaluator_id=self.evaluator_id,
            category=self.category,
            outcome=outcome,
            score=round(score, 6),
            threshold=threshold,
            metric_name="expected_calibration_error_complement",
            sample_count=len(sample_set.predictions),
            skip_reason=skip_reason,
            findings=findings,
            reference=self.reference,
            evidence_hash="",
        )
        result.evidence_hash = evaluator_evidence_hash(
            self.evaluator_id, sample_set.eval_set_id, result
        )
        return result
