"""Endpoint and config key detector."""

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


class EndpointDetector(BaseDetector):
    @property
    def detector_id(self) -> str:
        return "DET_ENDPOINT_V1"

    @property
    def detector_version(self) -> str:
        return "1.0.0"

    @property
    def supported_languages(self) -> frozenset[str]:
        return frozenset({"python", "javascript", "typescript", "yaml", "json", "toml"})

    @property
    def evidence_kinds(self) -> frozenset[str]:
        return frozenset({"endpoint", "config_key"})

    def detect(self, features: FeatureStore) -> list[EvidenceItem]:
        evidence: list[EvidenceItem] = []
        for cfg in features.configs:
            kind = (
                EvidenceKind.ENDPOINT
                if cfg.kind == "endpoint"
                else EvidenceKind.CONFIG_KEY
            )
            confidence = 0.8 if cfg.scope.value == "prod" else 0.35
            reach = (
                Reachability.REACHABLE_ENTRYPOINT
                if cfg.scope.value == "prod"
                else Reachability.MANIFEST_ONLY
            )
            evidence.append(
                build_evidence(
                    detector_id=self.detector_id,
                    detector_version=self.detector_version,
                    evidence_kind=kind,
                    category=SignalCategory.INFERENCE_ENDPOINT,
                    token_label=cfg.key,
                    location=cfg.location,
                    scope=cfg.scope,
                    rationale_code="endpoint_or_config",
                    confidence=confidence,
                    reachability=reach,
                )
            )
        return evidence
