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
"""

from opencomplai_core.engine import assess
from opencomplai_core.models import (
    AssessmentInput,
    ModelMetadata,
    RiskResult,
    ScanStatusArtifact,
    SystemManifest,
)

__version__ = "0.1.0-dev"
__all__ = [
    "AssessmentInput",
    "ModelMetadata",
    "RiskResult",
    "ScanStatusArtifact",
    "SystemManifest",
    "assess",
]
