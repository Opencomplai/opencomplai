"""Base detector interface — mirrors BaseEvaluator in evaluators/."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from opencomplai_core.models import EvidenceItem

if TYPE_CHECKING:
    from opencomplai_core.scanner.feature_types import FeatureStore


class BaseDetector(ABC):
    """Deterministic scanner detector consuming typed features."""

    @property
    @abstractmethod
    def detector_id(self) -> str: ...

    @property
    @abstractmethod
    def detector_version(self) -> str: ...

    @property
    @abstractmethod
    def supported_languages(self) -> frozenset[str]: ...

    @property
    @abstractmethod
    def evidence_kinds(self) -> frozenset[str]: ...

    @abstractmethod
    def detect(self, features: FeatureStore) -> list[EvidenceItem]: ...
