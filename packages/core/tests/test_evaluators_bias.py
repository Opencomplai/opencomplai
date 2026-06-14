"""Bias evaluator tests."""

import pytest
from opencomplai_core.evaluators.bias import BiasEvaluator
from opencomplai_core.models import EvalSampleSet, EvaluatorOutcome


def test_bias_fail_disparate_impact():
    ev = BiasEvaluator()
    n = 30
    sample = EvalSampleSet(
        eval_set_id="b1",
        system_id="sys",
        task_type="binary_classification",
        predictions=[1.0] * n + [0.0] * n,
        labels=[1.0] * (2 * n),
        protected_attributes={"gender": ["A"] * n + ["B"] * n},
    )
    result = ev.evaluate(sample)
    assert result.outcome == EvaluatorOutcome.FAIL


def test_bias_pass_balanced():
    ev = BiasEvaluator()
    n = 25
    sample = EvalSampleSet(
        eval_set_id="b2",
        system_id="sys",
        predictions=[1.0] * n + [1.0] * n,
        labels=[1.0] * (2 * n),
        protected_attributes={"gender": ["A"] * n + ["B"] * n},
    )
    result = ev.evaluate(sample)
    assert result.outcome == EvaluatorOutcome.PASS


def test_bias_validation_error_on_mismatch():
    ev = BiasEvaluator()
    sample = EvalSampleSet(
        eval_set_id="b3",
        system_id="sys",
        predictions=[1.0, 0.0],
        labels=[1.0],
        protected_attributes={"gender": ["A", "B"]},
    )
    with pytest.raises(ValueError, match="equal length"):
        ev.evaluate(sample)


def test_bias_skipped_without_data():
    ev = BiasEvaluator()
    sample = EvalSampleSet(eval_set_id="b4", system_id="sys")
    result = ev.evaluate(sample)
    assert result.outcome == EvaluatorOutcome.SKIPPED
