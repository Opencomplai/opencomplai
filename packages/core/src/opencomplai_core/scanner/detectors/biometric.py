"""Biometric signal detector."""

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


class BiometricDetector(BaseDetector):
    @property
    def detector_id(self) -> str:
        return "DET_BIOMETRIC_V1"

    @property
    def detector_version(self) -> str:
        return "1.0.0"

    @property
    def supported_languages(self) -> frozenset[str]:
        return frozenset({"python"})

    @property
    def evidence_kinds(self) -> frozenset[str]:
        return frozenset({"import", "callsite", "dependency"})

    def detect(self, features: FeatureStore) -> list[EvidenceItem]:
        evidence: list[EvidenceItem] = []
        for pkg in features.packages:
            token = match_token_identifier(pkg.name, "biometric")
            if token:
                evidence.append(
                    build_evidence(
                        detector_id=self.detector_id,
                        detector_version=self.detector_version,
                        evidence_kind=EvidenceKind.DEPENDENCY,
                        category=SignalCategory.BIOMETRIC,
                        token_label=token,
                        location=pkg.location,
                        scope=pkg.scope,
                        rationale_code="biometric_dependency",
                        confidence=0.75 if pkg.scope.value == "prod" else 0.35,
                    )
                )
        for imp in features.imports:
            token = match_token_identifier(imp.module, "biometric")
            if token:
                reach = (
                    Reachability.REACHABLE_ENTRYPOINT
                    if imp.scope.value == "prod"
                    else Reachability.IMPORT_ONLY
                )
                evidence.append(
                    build_evidence(
                        detector_id=self.detector_id,
                        detector_version=self.detector_version,
                        evidence_kind=EvidenceKind.IMPORT,
                        category=SignalCategory.BIOMETRIC,
                        token_label=token,
                        location=imp.location,
                        scope=imp.scope,
                        rationale_code="biometric_import",
                        confidence=0.85 if imp.scope.value == "prod" else 0.4,
                        reachability=reach,
                    )
                )
        return evidence
