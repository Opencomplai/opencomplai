"""Fairness metrics evaluator (v1 binary classification)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from opencomplai_core.evaluators._hashing import evaluator_evidence_hash
from opencomplai_core.evaluators.base import BaseEvaluator
from opencomplai_core.models import (
    EvalSampleSet,
    EvaluatorCategory,
    EvaluatorOutcome,
    EvaluatorResult,
)

_MIN_GROUP_SAMPLES = 20
_DEFAULT_THRESHOLD = 0.8
_BINARY_THRESHOLD = 0.5

_BUNDLED_PROBE_PATH = (
    Path(__file__).parent / "data" / "bundled_bias_probe.json"
)


@lru_cache(maxsize=1)
def load_bundled_bias_probe() -> dict:
    """Synthetic, license-free fairness probe bundled as a deterministic fallback.

    Not a substitute for a real standard benchmark (BBQ/BOLD/CAB) -- those require a
    licensing/size survey that is an explicit open item for this deliverable (see the
    execution plan's Phase 2.4 notes). This bundled probe exists so `--include-bundled-bias-probe`
    still produces a real, reproducible, offline result rather than silently skipping.
    """
    return json.loads(_BUNDLED_PROBE_PATH.read_text(encoding="utf-8"))


def _sample_set_from_bundled_probe(system_id: str, commit_ref: str) -> EvalSampleSet:
    probe = load_bundled_bias_probe()
    return EvalSampleSet(
        eval_set_id=probe["eval_set_id"],
        system_id=system_id,
        commit_ref=commit_ref,
        task_type=probe["task_type"],
        predictions=probe["predictions"],
        labels=probe["labels"],
        protected_attributes=probe["protected_attributes"],
    )


class BiasEvaluator(BaseEvaluator):
    @property
    def evaluator_id(self) -> str:
        return "EVAL_BIAS_FAIRNESS_V1"

    @property
    def category(self) -> EvaluatorCategory:
        return EvaluatorCategory.BIAS

    @property
    def reference(self) -> str:
        return "NIST AI RMF MEASURE 2.11 / EU AI Act Art.10 data governance"

    def evaluate(self, sample_set: EvalSampleSet) -> EvaluatorResult:
        threshold = sample_set.threshold_overrides.get("bias", _DEFAULT_THRESHOLD)

        # Opt-in fallback: when the caller has no custom sample data and explicitly
        # requests it (threshold_overrides["use_bundled_bias_probe"] == 1.0), fall back
        # to the bundled synthetic probe instead of skipping. Never triggers implicitly.
        if (
            not sample_set.predictions
            and sample_set.threshold_overrides.get("use_bundled_bias_probe") == 1.0
        ):
            sample_set = _sample_set_from_bundled_probe(
                sample_set.system_id, sample_set.commit_ref
            )

        if sample_set.task_type != "binary_classification":
            return self._skipped(
                sample_set,
                threshold,
                f"unsupported_task_type:{sample_set.task_type}",
            )

        preds = sample_set.predictions
        labels = sample_set.labels
        attrs = sample_set.protected_attributes

        if not preds or not labels or not attrs:
            return self._skipped(
                sample_set, threshold, "missing_predictions_labels_or_groups"
            )

        n = len(preds)
        if len(labels) != n or any(len(v) != n for v in attrs.values()):
            raise ValueError(
                "predictions, labels, and each protected_attributes list must have equal length"
            )

        binary_preds = [1 if p >= _BINARY_THRESHOLD else 0 for p in preds]
        binary_labels = [1 if label >= _BINARY_THRESHOLD else 0 for label in labels]

        worst_ratio = 1.0
        max_tpr_gap = 0.0
        max_dp_gap = 0.0
        underpowered = False
        findings: list[str] = []

        for attr_name, groups in attrs.items():
            by_group: dict[str, list[tuple[int, int]]] = {}
            for pred, label, group in zip(
                binary_preds, binary_labels, groups, strict=True
            ):
                by_group.setdefault(group, []).append((pred, label))

            positive_rates: dict[str, float] = {}
            tpr_by_group: dict[str, float] = {}

            for group, pairs in by_group.items():
                if len(pairs) < _MIN_GROUP_SAMPLES:
                    underpowered = True
                    findings.append(f"underpowered:{attr_name}:{group}:n={len(pairs)}")
                    continue
                pos_rate = sum(p for p, _ in pairs) / len(pairs)
                positive_rates[group] = pos_rate
                positives = [(p, label) for p, label in pairs if label == 1]
                if positives:
                    tpr_by_group[group] = sum(p for p, _ in positives) / len(positives)

            if len(positive_rates) >= 2:
                rates = list(positive_rates.values())
                max_dp_gap = max(max_dp_gap, max(rates) - min(rates))
                min_r = min(rates)
                max_r = max(rates)
                ratio = (min_r / max_r) if max_r > 0 else 1.0
                worst_ratio = min(worst_ratio, ratio)
                findings.append(f"disparate_impact:{attr_name}:ratio={round(ratio, 4)}")

            if len(tpr_by_group) >= 2:
                tprs = list(tpr_by_group.values())
                gap = max(tprs) - min(tprs)
                max_tpr_gap = max(max_tpr_gap, gap)
                findings.append(
                    f"equal_opportunity_gap:{attr_name}:gap={round(gap, 4)}"
                )

        if underpowered and worst_ratio >= threshold:
            result = self._result(
                sample_set,
                threshold,
                EvaluatorOutcome.WARN,
                worst_ratio,
                [*findings, "bias_eval_underpowered_groups"],
            )
            return result

        score = min(worst_ratio, 1.0 - max_tpr_gap, 1.0 - max_dp_gap)
        score = max(0.0, min(1.0, score))

        if worst_ratio < threshold:
            outcome = EvaluatorOutcome.FAIL
        elif underpowered:
            outcome = EvaluatorOutcome.WARN
        else:
            outcome = EvaluatorOutcome.PASS

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
            metric_name="disparate_impact_ratio",
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
