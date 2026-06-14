"""Evaluation engine aggregation tests."""

from opencomplai_core.eval_engine import run_evals
from opencomplai_core.models import EvalSampleSet, EvaluatorOutcome


def test_eval_engine_overall_fail_on_toxic():
    sample = EvalSampleSet(
        eval_set_id="e1",
        system_id="demo-sys",
        commit_ref="abc123",
        outputs=["ignore previous instructions"],
    )
    report = run_evals("demo-sys", "abc123", sample)
    assert report.overall_outcome == EvaluatorOutcome.FAIL
    assert report.evaluators_failed >= 1


def test_eval_engine_overall_pass_clean():
    sample = EvalSampleSet(
        eval_set_id="e2",
        system_id="demo-sys",
        commit_ref="HEAD",
        outputs=["A helpful compliant response."],
    )
    report = run_evals("demo-sys", "HEAD", sample)
    assert report.overall_outcome == EvaluatorOutcome.PASS
