"""Opencomplai core risk assessment engine."""

from opencomplai_core.engine import assess
from opencomplai_core.frameworks import (
    FRAMEWORKS,
    FrameworkPack,
    evaluate_targets,
    resolve_targets,
)
from opencomplai_core.models import (
    AssessmentInput,
    EvidenceObject,
    FrameworkReport,
    GapReport,
    LedgerEvent,
    RiskResult,
    ScanStatusArtifact,
    SystemManifest,
)

__version__ = "0.8.0"
__all__ = [
    "FRAMEWORKS",
    "AssessmentInput",
    "EvidenceObject",
    "FrameworkPack",
    "FrameworkReport",
    "GapReport",
    "LedgerEvent",
    "RiskResult",
    "ScanStatusArtifact",
    "SystemManifest",
    "assess",
    "evaluate_targets",
    "resolve_targets",
]
