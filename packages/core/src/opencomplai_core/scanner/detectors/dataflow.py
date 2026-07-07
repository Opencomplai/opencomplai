"""PII/PHI dataflow hint detector near model usage."""

from __future__ import annotations

from opencomplai_core.models import EvidenceItem, EvidenceKind, SignalCategory
from opencomplai_core.scanner.base import BaseDetector
from opencomplai_core.scanner.detectors._common import build_evidence
from opencomplai_core.scanner.detectors._signals import match_token_identifier
from opencomplai_core.scanner.feature_types import FeatureStore


class DataflowDetector(BaseDetector):
    @property
    def detector_id(self) -> str:
        return "DET_DATAFLOW_V1"

    @property
    def detector_version(self) -> str:
        return "1.0.0"

    @property
    def supported_languages(self) -> frozenset[str]:
        return frozenset({"python"})

    @property
    def evidence_kinds(self) -> frozenset[str]:
        return frozenset({"dataflow_hint"})

    def detect(self, features: FeatureStore) -> list[EvidenceItem]:
        evidence: list[EvidenceItem] = []
        ai_locations = {
            c.location.split(":")[0]
            for c in features.callsites
            if match_token_identifier(c.name, "ai_sdks")
            or match_token_identifier(c.name, "ml_frameworks")
        }
        for call in features.callsites:
            if call.location.split(":")[
                0
            ] not in ai_locations and not match_token_identifier(call.name, "ai_sdks"):
                continue
            token = match_token_identifier(call.name, "pii_hints")
            if token:
                evidence.append(
                    build_evidence(
                        detector_id=self.detector_id,
                        detector_version=self.detector_version,
                        evidence_kind=EvidenceKind.DATAFLOW_HINT,
                        category=SignalCategory.PII_DATAFLOW,
                        token_label=token,
                        location=call.location,
                        scope=call.scope,
                        rationale_code="pii_near_model",
                        confidence=0.6 if call.scope.value == "prod" else 0.25,
                    )
                )
        for imp in features.imports:
            token = match_token_identifier(imp.module, "pii_hints")
            if token and imp.location.split(":")[0] in ai_locations:
                evidence.append(
                    build_evidence(
                        detector_id=self.detector_id,
                        detector_version=self.detector_version,
                        evidence_kind=EvidenceKind.DATAFLOW_HINT,
                        category=SignalCategory.PII_DATAFLOW,
                        token_label=token,
                        location=imp.location,
                        scope=imp.scope,
                        rationale_code="pii_import_near_model",
                        confidence=0.55,
                    )
                )
        return evidence
