"""Data leakage evaluator tests."""

from opencomplai_core.evaluators.leakage import DataLeakageEvaluator
from opencomplai_core.models import EvalSampleSet, EvaluatorOutcome

# Luhn-valid test card (Stripe test PAN)
_TEST_CARD = "4242424242424242"


def test_leakage_fail_email():
    ev = DataLeakageEvaluator()
    sample = EvalSampleSet(
        eval_set_id="l1",
        system_id="sys",
        outputs=["Contact user@example.com for support"],
    )
    result = ev.evaluate(sample)
    assert result.outcome == EvaluatorOutcome.FAIL
    assert "user@example.com" not in " ".join(result.findings)


def test_leakage_fail_credit_card():
    ev = DataLeakageEvaluator()
    sample = EvalSampleSet(
        eval_set_id="l2",
        system_id="sys",
        outputs=[f"Card number {_TEST_CARD}"],
    )
    result = ev.evaluate(sample)
    assert result.outcome == EvaluatorOutcome.FAIL
    assert _TEST_CARD not in " ".join(result.findings)


def test_leakage_pass_clean():
    ev = DataLeakageEvaluator()
    sample = EvalSampleSet(
        eval_set_id="l3",
        system_id="sys",
        outputs=["The model answered without sensitive data."],
        declared_output_fields=["answer", "confidence"],
    )
    result = ev.evaluate(sample)
    assert result.outcome == EvaluatorOutcome.PASS
