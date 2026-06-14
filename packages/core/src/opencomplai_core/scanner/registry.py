"""Detector registry — authoritative set run by scan_engine."""

from __future__ import annotations

from opencomplai_core.scanner.base import BaseDetector
from opencomplai_core.scanner.detectors.ai_dependency import AiDependencyDetector
from opencomplai_core.scanner.detectors.artifact import ArtifactDetector
from opencomplai_core.scanner.detectors.ast_usage import AstUsageDetector
from opencomplai_core.scanner.detectors.biometric import BiometricDetector
from opencomplai_core.scanner.detectors.dataflow import DataflowDetector
from opencomplai_core.scanner.detectors.endpoint import EndpointDetector
from opencomplai_core.scanner.detectors.semantic import SemanticDetector

DETECTOR_REGISTRY: list[BaseDetector] = [
    AiDependencyDetector(),
    AstUsageDetector(),
    EndpointDetector(),
    ArtifactDetector(),
    SemanticDetector(),
    DataflowDetector(),
    BiometricDetector(),
]
