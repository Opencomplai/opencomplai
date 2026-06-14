"""Base evaluator interface — mirrors BaseRule in rules.py."""

from __future__ import annotations

from abc import ABC, abstractmethod

from opencomplai_core.models import EvalSampleSet, EvaluatorResult


class BaseEvaluator(ABC):
    """Deterministic pipeline evaluator."""

    @property
    @abstractmethod
    def evaluator_id(self) -> str: ...

    @property
    @abstractmethod
    def category(self): ...

    @property
    @abstractmethod
    def reference(self) -> str: ...

    @abstractmethod
    def evaluate(self, sample_set: EvalSampleSet) -> EvaluatorResult: ...
