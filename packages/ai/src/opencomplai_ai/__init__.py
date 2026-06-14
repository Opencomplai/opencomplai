"""opencomplai-ai — AI-powered EU AI Act intent classification plugin."""

from __future__ import annotations

__version__ = "0.1.0"

from opencomplai_ai.models import IntentAnnotation, MODEL_CATALOG
from opencomplai_ai.registry import ModelRegistry

__all__ = ["IntentAnnotation", "MODEL_CATALOG", "ModelRegistry", "__version__"]
