"""Synthetic AI usage callsites from config/endpoint hints (REST LLM integrations)."""

from __future__ import annotations

import re

from opencomplai_core.scanner.ai_usage_gate import AiUsageMatch, AiUsageType
from opencomplai_core.scanner.feature_types import CallsiteRef, ConfigRef, FeatureStore

_LLM_CONFIG_RULES: tuple[tuple[re.Pattern[str], str, AiUsageType], ...] = (
    (
        re.compile(r"generativelanguage\.googleapis\.com", re.I),
        "gemini_api",
        AiUsageType.LLM_INFERENCE,
    ),
    (re.compile(r"gemini_api_key", re.I), "gemini_api", AiUsageType.LLM_INFERENCE),
    (re.compile(r"google_api_key", re.I), "google_api", AiUsageType.LLM_INFERENCE),
    (
        re.compile(r"generatecontent", re.I),
        "generateContent",
        AiUsageType.LLM_INFERENCE,
    ),
    (re.compile(r"api\.openai\.com", re.I), "openai_api", AiUsageType.LLM_INFERENCE),
    (re.compile(r"openai_api_key", re.I), "openai_api", AiUsageType.LLM_INFERENCE),
    (
        re.compile(r"anthropic_api_key", re.I),
        "anthropic_api",
        AiUsageType.LLM_INFERENCE,
    ),
    (
        re.compile(r"api\.anthropic\.com", re.I),
        "anthropic_api",
        AiUsageType.LLM_INFERENCE,
    ),
)


def match_config_llm_usage(cfg: ConfigRef) -> AiUsageMatch | None:
    """Return AI usage match when a config line indicates LLM API usage."""
    for pattern, token, usage in _LLM_CONFIG_RULES:
        if pattern.search(cfg.key):
            return AiUsageMatch(
                usage_type=usage,
                token=token,
                reason="config_llm_signal",
            )
    return None


def derive_config_ai_callsites(
    features: FeatureStore,
) -> tuple[list[CallsiteRef], dict[str, AiUsageMatch]]:
    """Build synthetic callsites from config/endpoint matches for AI intent gating."""
    callsites: list[CallsiteRef] = []
    usage_matches: dict[str, AiUsageMatch] = {}
    seen_locations: set[str] = set()

    for cfg in features.configs:
        match = match_config_llm_usage(cfg)
        if match is None or cfg.location in seen_locations:
            continue
        seen_locations.add(cfg.location)
        ref = CallsiteRef(name=match.token, location=cfg.location, scope=cfg.scope)
        callsites.append(ref)
        usage_matches[cfg.location] = match

    return callsites, usage_matches
