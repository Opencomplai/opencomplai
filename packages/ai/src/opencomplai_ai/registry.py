"""ModelRegistry — resolves model_id to the correct intent backend."""

from __future__ import annotations

from typing import ClassVar

from opencomplai_ai._saas_client import SaaSIntentClient
from opencomplai_ai.classifier import IntentClassifier
from opencomplai_ai.explainer import IntentExplainer
from opencomplai_ai.models import MODEL_CATALOG, IntentAnnotation


class ModelNotInstalledError(RuntimeError):
    pass


class _IntentBackendProtocol:
    def classify(self, snippet: str) -> IntentAnnotation: ...


class ModelRegistry:
    _instances: ClassVar[dict[str, _IntentBackendProtocol]] = {}

    @classmethod
    def resolve(cls, model_id: str) -> _IntentBackendProtocol:
        if model_id not in MODEL_CATALOG:
            raise ValueError(
                f"Unknown model '{model_id}'. Valid options: {', '.join(MODEL_CATALOG)}"
            )

        if model_id in cls._instances:
            return cls._instances[model_id]

        spec = MODEL_CATALOG[model_id]

        if spec.requires_deep:
            try:
                import llama_cpp  # noqa: F401
            except ImportError:
                raise ModelNotInstalledError(
                    f"Model '{model_id}' requires llama-cpp-python.\n"
                    f"Run: pip install 'opencomplai-ai[deep]'\n"
                    f"Or choose a lighter model: opencomplai ai configure"
                ) from None

        if model_id == "codebert-onnx":
            backend: _IntentBackendProtocol = IntentClassifier()
        elif model_id == "saas":
            backend = SaaSIntentClient()
        else:
            backend = IntentExplainer(model_id)

        cls._instances[model_id] = backend
        return backend

    @classmethod
    def clear_cache(cls) -> None:
        cls._instances.clear()
