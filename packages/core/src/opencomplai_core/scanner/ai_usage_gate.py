"""Callsite-level AI usage gate — only AI-related sites enter EU Act classification."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from enum import StrEnum

from opencomplai_core.models import EvidenceScope
from opencomplai_core.scanner.detectors._signals import match_token_identifier
from opencomplai_core.scanner.feature_types import CallsiteRef, FeatureStore, ImportRef
from opencomplai_core.scanner.file_ai_context import FileAiContext
from opencomplai_core.scanner.snippet_cache import SnippetCache

_AI_LIBRARY_CATEGORIES = (
    "ai_sdks",
    "ml_frameworks",
    "orchestration",
    "vector_embedding",
    "biometric",
)
_SCORING_CATEGORY = "scoring"
_INFERENCE_VERBS = frozenset(
    {
        "predict",
        "predict_proba",
        "infer",
        "inference",
        "embed",
        "embedding",
        "generate",
        "completion",
        "complete",
        "classify",
        "fit",
        "transform",
        "forward",
        "encode",
        "decode",
        "chat",
        "completions",
    }
)

_DENYLIST_TOKENS = frozenset(
    {
        "apirouter",
        "fastapi",
        "blueprint",
        "asgitransport",
        "testclient",
        "httpx",
        "depends",
        "httpexception",
        "basemodel",
        "pytest",
        "mock",
        "patch",
        "session",
        "router",
        "middleware",
        "response",
        "request",
        "status",
        "json",
        "loads",
        "dumps",
        "open",
        "read",
        "write",
        "print",
        "logger",
        "logging",
        "path",
        "pathlib",
        "os",
        "sys",
        "typing",
        "enum",
        "dataclass",
        "field",
        "staticmethod",
        "classmethod",
        "property",
        "super",
        "isinstance",
        "len",
        "str",
        "int",
        "float",
        "bool",
        "list",
        "dict",
        "set",
        "tuple",
        "range",
        "enumerate",
        "zip",
        "map",
        "filter",
        "sorted",
        "min",
        "max",
        "abs",
        "round",
        "format",
        "repr",
        "hash",
        "id",
        "type",
        "any",
        "all",
    }
)


class AiUsageType(StrEnum):
    LLM_INFERENCE = "llm_inference"
    ML_INFERENCE = "ml_inference"
    EMBEDDING = "embedding"
    TRAINING = "training"
    ORCHESTRATION = "orchestration"
    BIOMETRIC = "biometric"
    SCORING = "scoring"
    UNKNOWN_AI = "unknown_ai"


@dataclass(frozen=True)
class AiUsageMatch:
    usage_type: AiUsageType
    token: str
    reason: str


def _file_of(ref) -> str:
    return ref.location.rpartition(":")[0]


def _token(ref) -> str:
    return (getattr(ref, "name", None) or getattr(ref, "module", "") or "").lower()


def _token_base_name(token: str) -> str:
    """Last segment of dotted identifier (e.g. openai.Client.chat -> chat)."""
    return token.rpartition(".")[-1]


def _is_denied(token: str) -> bool:
    base = _token_base_name(token)
    if base in _DENYLIST_TOKENS:
        return True
    if token in _DENYLIST_TOKENS:
        return True
    return False


def _matches_ai_library(token: str) -> tuple[str, AiUsageType] | None:
    for cat in _AI_LIBRARY_CATEGORIES:
        matched = match_token_identifier(token, cat)
        if matched:
            if cat == "ai_sdks":
                return matched, AiUsageType.LLM_INFERENCE
            if cat == "ml_frameworks":
                return matched, AiUsageType.ML_INFERENCE
            if cat == "orchestration":
                return matched, AiUsageType.ORCHESTRATION
            if cat == "vector_embedding":
                return matched, AiUsageType.EMBEDDING
            if cat == "biometric":
                return matched, AiUsageType.BIOMETRIC
    return None


def _matches_pack_code_signal(token: str) -> bool:
    try:
        from opencomplai_ai.knowledge.annex_iii import all_code_signals
        from opencomplai_ai.knowledge.prohibited import PROHIBITED

        from opencomplai_core.scanner.detectors._signals import match_any_code_signal

        signals = all_code_signals()
        if match_any_code_signal(token, signals) is not None:
            return True
        for entry in PROHIBITED:
            if match_any_code_signal(token, entry.code_signals) is not None:
                return True
    except ImportError:
        pass
    return False


def _has_inference_verb(token: str, snippet: str) -> bool:
    combined = f"{token} {snippet}".lower()
    tokens = set(re.split(r"[^a-z0-9_]", combined))
    return bool(tokens & _INFERENCE_VERBS)


def _matches_scoring(token: str, ctx: FileAiContext) -> bool:
    if not (ctx.has_ml_sdk or ctx.artifact_refs):
        return False
    matched = match_token_identifier(token, _SCORING_CATEGORY)
    return matched is not None


def is_ai_usage_callsite(
    ref,
    snippet: str,
    ctx: FileAiContext,
) -> AiUsageMatch | None:
    """Return AiUsageMatch if callsite/import is provably AI-related, else None."""
    token = _token(ref)
    if not token:
        return None

    if _is_denied(token):
        return None

    # Import statements: AI library import is sufficient
    if isinstance(ref, ImportRef):
        lib = _matches_ai_library(token)
        if lib:
            matched, usage = lib
            return AiUsageMatch(usage_type=usage, token=matched, reason="ai_import")
        return None

    # Test scaffolding without AI signal in snippet
    if ref.scope == EvidenceScope.TEST:
        has_ai_in_snippet = any(
            match_token_identifier(snippet.lower(), cat)
            for cat in (*_AI_LIBRARY_CATEGORIES, _SCORING_CATEGORY)
        )
        if not has_ai_in_snippet and not ctx.has_ml_sdk and not ctx.artifact_refs:
            if not _has_inference_verb(token, snippet):
                return None

    lib = _matches_ai_library(token)
    if lib:
        matched, usage = lib
        return AiUsageMatch(usage_type=usage, token=matched, reason="ai_callsite")

    if _matches_pack_code_signal(token):
        if ctx.has_ml_sdk or ctx.artifact_refs or ctx.has_lexical_ai_evidence:
            return AiUsageMatch(
                usage_type=AiUsageType.SCORING,
                token=_token_base_name(token),
                reason="pack_code_signal",
            )

    if _matches_scoring(token, ctx):
        matched = match_token_identifier(token, _SCORING_CATEGORY) or token
        return AiUsageMatch(
            usage_type=AiUsageType.SCORING,
            token=matched,
            reason="scoring_with_ml_context",
        )

    if ctx.has_ml_sdk or ctx.artifact_refs or ctx.has_lexical_ai_evidence:
        if _has_inference_verb(token, snippet):
            usage = AiUsageType.ML_INFERENCE
            if any(match_token_identifier(t, "ai_sdks") for t in ctx.ai_imports):
                usage = AiUsageType.LLM_INFERENCE
            return AiUsageMatch(
                usage_type=usage,
                token=_token_base_name(token),
                reason="inference_verb_with_file_context",
            )

    return None


@dataclass
class GatedFeatures:
    """Feature store subset plus per-location usage matches."""

    features: FeatureStore
    usage_matches: dict[str, AiUsageMatch]


def gate_features_for_intent(
    features: FeatureStore,
    file_contexts: dict[str, FileAiContext],
    *,
    snippet_cache: SnippetCache | None = None,
) -> GatedFeatures:
    """Filter callsites/imports to AI-related sites only."""
    from opencomplai_core.scanner.config_ai_sites import derive_config_ai_callsites

    cache = snippet_cache or SnippetCache()
    usage_matches: dict[str, AiUsageMatch] = {}
    gated_callsites: list[CallsiteRef] = []
    gated_imports: list[ImportRef] = []

    for ref in features.imports:
        snippet = cache.read(ref.location)
        ctx = file_contexts.get(_file_of(ref), FileAiContext(file_path=_file_of(ref)))
        match = is_ai_usage_callsite(ref, snippet, ctx)
        if match:
            usage_matches[ref.location] = match
            gated_imports.append(ref)

    for ref in features.callsites:
        snippet = cache.read(ref.location)
        ctx = file_contexts.get(_file_of(ref), FileAiContext(file_path=_file_of(ref)))
        match = is_ai_usage_callsite(ref, snippet, ctx)
        if match:
            usage_matches[ref.location] = match
            gated_callsites.append(ref)

    config_callsites, config_matches = derive_config_ai_callsites(features)
    for ref in config_callsites:
        if ref.location not in usage_matches:
            usage_matches[ref.location] = config_matches[ref.location]
            gated_callsites.append(ref)

    gated = replace(
        features,
        callsites=gated_callsites,
        imports=gated_imports,
    )
    return GatedFeatures(features=gated, usage_matches=usage_matches)
