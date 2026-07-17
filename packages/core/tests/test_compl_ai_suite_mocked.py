"""Mocked Inspect path for run_compl_ai_suite."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from opencomplai_core.bridges.compl_ai import curated_task_names, run_compl_ai_suite
from opencomplai_core.models import EvaluatorOutcome


def test_curated_task_names():
    names = curated_task_names()
    assert names == ["strong_reject", "bbq", "bigbench_calibration"]


def test_run_compl_ai_suite_with_mocked_inspect():
    fake_log = SimpleNamespace(
        results=SimpleNamespace(
            scores=[SimpleNamespace(metrics={"accuracy": SimpleNamespace(value=0.95)})],
            completed_samples=10,
        )
    )
    fake_inspect = MagicMock()
    fake_inspect.eval.return_value = [fake_log, fake_log, fake_log]

    with patch("opencomplai_core.bridges.compl_ai._require_inspect", return_value=fake_inspect):
        results = run_compl_ai_suite(
            ["strong_reject", "bbq", "bigbench_calibration"],
            model="openai/gpt-4o-mini",
            api_key="sk-test",
        )
    assert len(results) == 3
    assert all(r.outcome == EvaluatorOutcome.PASS for r in results)
    fake_inspect.eval.assert_called_once()


def test_unknown_task_raises():
    with patch("opencomplai_core.bridges.compl_ai._require_inspect", return_value=MagicMock()):
        with pytest.raises(ValueError, match="Unknown COMPL-AI"):
            run_compl_ai_suite(["not_a_real_task"], model="m", api_key="")
