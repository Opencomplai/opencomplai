"""AST usage detector — imports and callsites."""

from __future__ import annotations

from opencomplai_core.models import (
    EvidenceItem,
    EvidenceKind,
    Reachability,
    SignalCategory,
)
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


class AstUsageDetector(BaseDetector):
    @property
    def detector_id(self) -> str:
        return "DET_AST_V1"

    @property
    def detector_version(self) -> str:
        return "1.0.0"

    @property
    def supported_languages(self) -> frozenset[str]:
        return frozenset({"python"})

    @property
    def evidence_kinds(self) -> frozenset[str]:
        return frozenset({"import", "callsite"})

    def detect(self, features: FeatureStore) -> list[EvidenceItem]:
        evidence: list[EvidenceItem] = []
        for imp in features.imports:
            for key, category in _CATEGORY_MAP.items():
                token = match_token_identifier(imp.module, key)
                if token:
                    confidence = 0.75 if imp.scope.value == "prod" else 0.4
                    reach = (
                        Reachability.INTERNAL_CALLCHAIN
                        if imp.scope.value == "prod"
                        else Reachability.IMPORT_ONLY
                    )
                    evidence.append(
                        build_evidence(
                            detector_id=self.detector_id,
                            detector_version=self.detector_version,
                            evidence_kind=EvidenceKind.IMPORT,
                            category=category,
                            token_label=token,
                            location=imp.location,
                            scope=imp.scope,
                            rationale_code="import_detected",
                            confidence=confidence,
                            reachability=reach,
                        )
                    )
                    break
        for call in features.callsites:
            for key, category in _CATEGORY_MAP.items():
                token = match_token_identifier(call.name, key)
                if token:
                    confidence = 0.85 if call.scope.value == "prod" else 0.45
                    reach = (
                        Reachability.REACHABLE_ENTRYPOINT
                        if call.scope.value == "prod"
                        else Reachability.IMPORT_ONLY
                    )
                    evidence.append(
                        build_evidence(
                            detector_id=self.detector_id,
                            detector_version=self.detector_version,
                            evidence_kind=EvidenceKind.CALLSITE,
                            category=category,
                            token_label=token,
                            location=call.location,
                            scope=call.scope,
                            rationale_code="callsite_detected",
                            confidence=confidence,
                            reachability=reach,
                        )
                    )
                    break
        return evidence
