"""Per-file AI context built before the callsite usage gate."""

from __future__ import annotations

from dataclasses import dataclass, field

from opencomplai_core.models import EvidenceItem
from opencomplai_core.scanner.detectors._signals import match_token_identifier
from opencomplai_core.scanner.feature_types import FeatureStore

_AI_LIBRARY_CATEGORIES = (
    "ai_sdks",
    "ml_frameworks",
    "orchestration",
    "vector_embedding",
    "biometric",
)
_ML_CATEGORIES = ("ai_sdks", "ml_frameworks", "orchestration", "vector_embedding")
_ARTIFACT_EXTENSIONS = (
    ".pkl",
    ".onnx",
    ".pt",
    ".pth",
    ".joblib",
    ".h5",
    ".safetensors",
)
_ARTIFACT_LOAD_TOKENS = (
    "torch.load",
    "joblib.load",
    "pickle.load",
    "load_model",
    "from_pretrained",
)


@dataclass
class FileAiContext:
    file_path: str
    ai_imports: list[str] = field(default_factory=list)
    has_lexical_ai_evidence: bool = False
    has_ml_sdk: bool = False
    artifact_refs: list[str] = field(default_factory=list)


def build_file_ai_context_map(
    features: FeatureStore,
    lexical_evidence: list[EvidenceItem],
) -> dict[str, FileAiContext]:
    """Build per-file AI context from imports, artifacts, and lexical detectors."""
    contexts: dict[str, FileAiContext] = {}

    def _get(path: str) -> FileAiContext:
        if path not in contexts:
            contexts[path] = FileAiContext(file_path=path)
        return contexts[path]

    for ev in lexical_evidence:
        if ev.detector_id in (
            "DET_AST_V1",
            "DET_AI_DEP_V1",
            "DET_BIOMETRIC_V1",
            "DET_ENDPOINT_V1",
        ):
            for loc in ev.locations:
                _get(loc.rpartition(":")[0]).has_lexical_ai_evidence = True

    from opencomplai_core.scanner.config_ai_sites import match_config_llm_usage

    for cfg in features.configs:
        if match_config_llm_usage(cfg) is not None:
            _get(cfg.location.rpartition(":")[0]).has_lexical_ai_evidence = True

    for imp in features.imports:
        path = imp.location.rpartition(":")[0]
        ctx = _get(path)
        module = imp.module.lower()
        for cat in _AI_LIBRARY_CATEGORIES:
            token = match_token_identifier(module, cat)
            if token:
                ctx.ai_imports.append(token)
                if cat in _ML_CATEGORIES:
                    ctx.has_ml_sdk = True
                break

    for art in features.artifacts:
        path = art.location.rpartition(":")[0]
        ctx = _get(path)
        ext = art.extension.lower()
        if ext in _ARTIFACT_EXTENSIONS or ext in (".pickle",):
            ctx.artifact_refs.append(art.path)

    for call in features.callsites:
        path = call.location.rpartition(":")[0]
        name = call.name.lower()
        if any(tok in name for tok in _ARTIFACT_LOAD_TOKENS):
            _get(path).artifact_refs.append(name)

    return contexts
