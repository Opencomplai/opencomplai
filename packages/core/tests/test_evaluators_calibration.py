"""Calibration metrics evaluator tests (opt-in, GPAI documentation support)."""

from opencomplai_core.evaluators.calibration import CalibrationEvaluator
from opencomplai_core.models import EvalSampleSet, EvaluatorOutcome


def test_calibration_skipped_by_default_without_opt_in():
    ev = CalibrationEvaluator()
    sample = EvalSampleSet(
        eval_set_id="c1",
        system_id="sys",
        predictions=[0.9, 0.8, 0.1, 0.2],
        labels=[1.0, 1.0, 0.0, 0.0],
    )
    result = ev.evaluate(sample)
    assert result.outcome == EvaluatorOutcome.SKIPPED
    assert result.skip_reason == "calibration_not_requested"


def test_calibration_pass_when_well_calibrated():
    ev = CalibrationEvaluator()
    # Confidence exactly matches outcome rate within each bucket (ECE == 0).
    sample = EvalSampleSet(
        eval_set_id="c2",
        system_id="sys",
        predictions=[0.9] * 10 + [0.1] * 10,
        labels=[1.0] * 9 + [0.0] * 1 + [0.0] * 9 + [1.0] * 1,
        threshold_overrides={"include_calibration": 1.0},
    )
    result = ev.evaluate(sample)
    assert result.outcome == EvaluatorOutcome.PASS


def test_calibration_fail_when_badly_miscalibrated():
    ev = CalibrationEvaluator()
    # High confidence but consistently wrong.
    sample = EvalSampleSet(
        eval_set_id="c3",
        system_id="sys",
        predictions=[0.95] * 20,
        labels=[0.0] * 20,
        threshold_overrides={"include_calibration": 1.0},
    )
    result = ev.evaluate(sample)
    assert result.outcome == EvaluatorOutcome.FAIL


def test_calibration_skipped_without_data_even_when_opted_in():
    ev = CalibrationEvaluator()
    sample = EvalSampleSet(
        eval_set_id="c4",
        system_id="sys",
        threshold_overrides={"include_calibration": 1.0},
    )
    result = ev.evaluate(sample)
    assert result.outcome == EvaluatorOutcome.SKIPPED
    assert result.skip_reason == "missing_or_mismatched_predictions_labels"


def test_calibration_deterministic_evidence_hash():
    ev = CalibrationEvaluator()
    sample = EvalSampleSet(
        eval_set_id="c5",
        system_id="sys",
        predictions=[0.9, 0.1],
        labels=[1.0, 0.0],
        threshold_overrides={"include_calibration": 1.0},
    )
    r1 = ev.evaluate(sample)
    r2 = ev.evaluate(sample)
    assert r1.evidence_hash == r2.evidence_hash


def test_calibration_registered_in_registry():
    from opencomplai_core.evaluators.registry import EVALUATOR_REGISTRY

    ids = [e.evaluator_id for e in EVALUATOR_REGISTRY]
    assert "EVAL_CALIBRATION_V1" in ids
    assert len(ids) == len(set(ids))
