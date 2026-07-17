"""Evaluator registry — authoritative set run by eval_engine."""

from __future__ import annotations

from opencomplai_core.evaluators.adversarial import AdversarialEvaluator
from opencomplai_core.evaluators.bias import BiasEvaluator
from opencomplai_core.evaluators.calibration import CalibrationEvaluator
from opencomplai_core.evaluators.leakage import DataLeakageEvaluator
from opencomplai_core.evaluators.safety import SafetyEvaluator

EVAL_SET_VERSION = "1.0.0"

EVALUATOR_REGISTRY: list = [
    SafetyEvaluator(),
    BiasEvaluator(),
    DataLeakageEvaluator(),
    AdversarialEvaluator(),
    CalibrationEvaluator(),
]
