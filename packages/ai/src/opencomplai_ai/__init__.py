"""opencomplai-ai — AI-powered EU AI Act intent classification plugin."""

from __future__ import annotations

__version__ = "0.1.0"

from opencomplai_ai.models import MODEL_CATALOG, IntentAnnotation
from opencomplai_ai.registry import ModelRegistry

__all__ = ["MODEL_CATALOG", "IntentAnnotation", "ModelRegistry", "__version__"]
