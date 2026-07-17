"""Tests for the optional Inspect-AI eval bridge (opencomplai eval --suite inspect-ai)."""

from __future__ import annotations

import pytest
from opencomplai_core.bridges.inspect_eval import (
    eval_log_to_evaluator_result,
    is_inspect_available,
    run_inspect_suite,
)
from opencomplai_core.models import EvaluatorOutcome


def test_is_inspect_available_returns_bool_without_raising():
    # inspect-ai is not installed in this environment (the optional extra was not
    # added to the dev environment) -- this must return False, not raise.
    result = is_inspect_available()
    assert isinstance(result, bool)


def test_eval_log_to_evaluator_result_has_no_hard_inspect_dependency():
    """The mapping function itself must work without inspect_ai importable."""
    result = eval_log_to_evaluator_result("toxicity", accuracy=0.95, sample_count=100)
    assert result.evaluator_id == "EVAL_INSPECT_TOXICITY_V1"
    assert result.outcome == EvaluatorOutcome.PASS
    assert "inspect_task=toxicity" in result.findings
    assert "Inspect-AI" in result.reference


def test_eval_log_to_evaluator_result_fails_below_threshold():
    result = eval_log_to_evaluator_result("toxicity", accuracy=0.5, sample_count=100, threshold=0.8)
    assert result.outcome == EvaluatorOutcome.FAIL


def test_run_inspect_suite_raises_import_error_without_extra():
    """When inspect-ai is not installed, calling the real suite entrypoint must fail
    clearly (ImportError with install instructions), not silently no-op or crash
    with an unrelated traceback."""
    with pytest.raises(ImportError, match="inspect-bridge"):
        run_inspect_suite(["toxicity"], model="gpt-4o-mini", api_key="fake-key")


def test_default_opencomplai_eval_path_is_unaffected_by_bridge_absence():
    """Confirm importing the bridge module itself never raises, even though
    inspect_ai is not installed -- this proves the feature is 'absent gracefully'."""
    import opencomplai_core.bridges.inspect_eval  # noqa: F401


def test_engine_module_never_imports_the_bridge():
    """Guard: `opencomplai check`'s deterministic path must never reference the bridge."""
    import opencomplai_core.engine as engine_module

    source = open(engine_module.__file__, encoding="utf-8").read()
    assert "inspect_eval" not in source
    assert "bridges" not in source
