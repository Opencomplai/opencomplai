"""Bundled prompt-injection seed corpus (SU-27b)."""

import pytest
from opencomplai_core.eval_engine import run_evals
from opencomplai_core.evaluators.adversarial import _is_jailbreak_prompt
from opencomplai_core.evaluators.seed_corpus import (
    SEED_EVAL_SET_ID,
    load_seed_corpus,
    seed_sample_set,
)


def _adversarial(report):
    return next(r for r in report.results if r.evaluator_id == "EVAL_ADVERSARIAL_V1")


def test_every_seed_prompt_is_detected_as_adversarial():
    prompts = load_seed_corpus()["prompts"]
    assert 12 <= len(prompts) <= 16
    assert [p for p in prompts if not _is_jailbreak_prompt(p)] == []


def test_seed_corpus_metadata_is_flagged():
    corpus = load_seed_corpus()
    assert corpus["eval_set_id"] == SEED_EVAL_SET_ID
    assert corpus["source"]
    assert corpus["confidence"] == "low"
    assert corpus["needs_founder_review"] is True


def test_seed_without_outputs_skips_adversarial():
    report = run_evals("sys", "HEAD", seed_sample_set("sys", "HEAD"))
    result = _adversarial(report)
    assert result.outcome.value == "skipped"
    assert result.skip_reason == "no_prompt_output_pairs"


def test_seed_with_refusals_passes_and_with_compliance_fails():
    n = len(load_seed_corpus()["prompts"])
    refused = run_evals(
        "sys", "HEAD", seed_sample_set("sys", "HEAD", ["I cannot help with that."] * n)
    )
    assert _adversarial(refused).outcome.value == "pass"
    complied = run_evals(
        "sys", "HEAD", seed_sample_set("sys", "HEAD", ["Sure, here is how to."] * n)
    )
    assert _adversarial(complied).outcome.value == "fail"


def test_seed_outputs_length_mismatch_raises():
    with pytest.raises(ValueError, match="must match"):
        seed_sample_set("sys", "HEAD", ["only one"])
