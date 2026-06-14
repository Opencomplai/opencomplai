"""AI dependency detector — manifests and lockfiles."""

from __future__ import annotations

from opencomplai_core.models import EvidenceItem, EvidenceKind, SignalCategory
from opencomplai_core.scanner.base import BaseDetector
from opencomplai_core.scanner.detectors._common import build_evidence
from opencomplai_core.scanner.detectors._signals import match_token_identifier
from opencomplai_core.scanner.feature_types import FeatureStore

_CATEGORY_MAP = {
    "ai_sdks": SignalCategory.AI_SDK,
    "ml_frameworks": SignalCategory.ML_FRAMEWORK,
    "orchestration": SignalCategory.LLM_ORCHESTRATION,
    "vector_embedding": SignalCategory.EMBEDDINGS_VECTOR,
    "biometric": SignalCategory.BIOMETRIC,
    "scoring": SignalCategory.SCORING_PROFILING,
}


class AiDependencyDetector(BaseDetector):
    @property
    def detector_id(self) -> str:
        return "DET_AI_DEP_V1"

    @property
    def detector_version(self) -> str:
        return "1.0.0"

    @property
    def supported_languages(self) -> frozenset[str]:
        return frozenset({"python", "javascript", "typescript", "java", "go", "rust"})

    @property
    def evidence_kinds(self) -> frozenset[str]:
        return frozenset({"dependency", "lockfile_package"})

    def detect(self, features: FeatureStore) -> list[EvidenceItem]:
        evidence: list[EvidenceItem] = []
        for pkg in features.packages:
            for key, category in _CATEGORY_MAP.items():
                token = match_token_identifier(pkg.name, key)
                if token:
                    confidence = (
                        0.5 if pkg.scope.value in ("test", "dev", "docs") else 0.7
                    )
                    evidence.append(
                        build_evidence(
                            detector_id=self.detector_id,
                            detector_version=self.detector_version,
                            evidence_kind=EvidenceKind.DEPENDENCY,
                            category=category,
                            token_label=token,
                            location=pkg.location,
                            scope=pkg.scope,
                            rationale_code="manifest_dependency",
                            confidence=confidence,
                        )
                    )
                    break
        return evidence
