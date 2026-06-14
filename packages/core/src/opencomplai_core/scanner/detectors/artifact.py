"""Model artifact detector."""

from __future__ import annotations

from opencomplai_core.models import (
    EvidenceItem,
    EvidenceKind,
    Reachability,
    SignalCategory,
)
from opencomplai_core.scanner.base import BaseDetector
from opencomplai_core.scanner.detectors._common import build_evidence
from opencomplai_core.scanner.feature_types import FeatureStore


class ArtifactDetector(BaseDetector):
    @property
    def detector_id(self) -> str:
        return "DET_ARTIFACT_V1"

    @property
    def detector_version(self) -> str:
        return "1.0.0"

    @property
    def supported_languages(self) -> frozenset[str]:
        return frozenset({"unknown"})

    @property
    def evidence_kinds(self) -> frozenset[str]:
        return frozenset({"model_artifact"})

    def detect(self, features: FeatureStore) -> list[EvidenceItem]:
        evidence: list[EvidenceItem] = []
        for art in features.artifacts:
            confidence = 0.9 if art.scope.value == "prod" else 0.4
            reach = (
                Reachability.REACHABLE_ENTRYPOINT
                if art.scope.value == "prod"
                else Reachability.MANIFEST_ONLY
            )
            evidence.append(
                build_evidence(
                    detector_id=self.detector_id,
                    detector_version=self.detector_version,
                    evidence_kind=EvidenceKind.MODEL_ARTIFACT,
                    category=SignalCategory.MODEL_ARTIFACT,
                    token_label=art.extension.lstrip("."),
                    location=art.location,
                    scope=art.scope,
                    rationale_code="model_artifact",
                    confidence=confidence,
                    reachability=reach,
                )
            )
        return evidence
