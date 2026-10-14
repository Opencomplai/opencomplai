"""opencomplai-ai — optional EU AI Act intent analysis plugin.

The `codebert-onnx` matcher is deterministic and needs no model download;
local GGUF models need the `[deep]` extra.
"""

from __future__ import annotations

__version__ = "0.13.1"

from opencomplai_ai.models import MODEL_CATALOG, IntentAnnotation
from opencomplai_ai.registry import ModelRegistry

__all__ = ["MODEL_CATALOG", "IntentAnnotation", "ModelRegistry", "__version__"]
