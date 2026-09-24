"""
Opencomplai Python SDK.

Quickstart:
    from opencomplai import assess, AssessmentInput, ModelMetadata

    result = assess(AssessmentInput(
        model=ModelMetadata(
            name="my-model",
            version="1.0.0",
            modality="text",
            use_case="customer support chatbot",
            deployment_context="production",
        )
    ))
    print(result.risk_level)

To assess a manifest against several frameworks side by side, pass
resolve_targets(manifest) to evaluate_targets; FRAMEWORKS lists the
frameworks this release knows.
"""

from opencomplai_core.engine import assess
from opencomplai_core.frameworks import (
    FRAMEWORKS,
    FrameworkPack,
    evaluate_targets,
    resolve_targets,
)
from opencomplai_core.models import (
    AssessmentInput,
    FrameworkReport,
    GapReport,
    ModelMetadata,
    RiskLevel,
    RiskResult,
    RuleResult,
    ScanResult,
    ScanStatusArtifact,
    SystemManifest,
)

__version__ = "0.8.0"
__all__ = [
    "FRAMEWORKS",
    "AssessmentInput",
    "FrameworkPack",
    "FrameworkReport",
    "GapReport",
    "ModelMetadata",
    "RiskLevel",
    "RiskResult",
    "RuleResult",
    "ScanResult",
    "ScanStatusArtifact",
    "SystemManifest",
    "assess",
    "evaluate_targets",
    "resolve_targets",
]
