"""Tests for config-derived synthetic AI usage sites."""

from __future__ import annotations

from pathlib import Path

import pytest
from opencomplai_core.models import EvidenceScope
from opencomplai_core.scan_engine import (
    _suggest_repo_root_alternatives,
    validate_scan_repo_root,
)
from opencomplai_core.scanner.ai_usage_gate import AiUsageType, gate_features_for_intent
from opencomplai_core.scanner.config_ai_sites import (
    derive_config_ai_callsites,
    match_config_llm_usage,
)
from opencomplai_core.scanner.feature_types import ConfigRef
from opencomplai_core.scanner.features import ScanConfig, extract_features
from opencomplai_core.scanner.file_ai_context import build_file_ai_context_map
from opencomplai_core.scanner.inventory import build_repo_inventory


def test_validate_scan_repo_root_rejects_missing(tmp_path: Path):
    missing = tmp_path / "does-not-exist"
    with pytest.raises(FileNotFoundError, match="repo-root does not exist"):
        validate_scan_repo_root(missing)


def test_validate_scan_repo_root_suggests_similar_directory(
    tmp_path: Path, monkeypatch
):
    sibling = tmp_path / "opencomplai-website"
    sibling.mkdir()
    wrong = tmp_path / "opecomplai-website"
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError, match="Did you mean:"):
        validate_scan_repo_root(wrong)
    suggestions = _suggest_repo_root_alternatives(wrong)
    assert any("opencomplai-website" in s for s in suggestions)


def test_validate_scan_repo_root_auto_corrects_typo(tmp_path: Path, monkeypatch):
    sibling = tmp_path / "opencomplai-website"
    sibling.mkdir()
    wrong = tmp_path / "opecomplai-website"
    monkeypatch.chdir(tmp_path)
    corrected = validate_scan_repo_root(wrong, auto_correct=True)
    assert corrected == sibling.resolve()


def test_validate_scan_repo_root_rejects_file(tmp_path: Path):
    file_path = tmp_path / "file.txt"
    file_path.write_text("x", encoding="utf-8")
    with pytest.raises(NotADirectoryError, match="not a directory"):
        validate_scan_repo_root(file_path)


def test_config_extractor_finds_gemini_signals(tmp_path: Path):
    route = tmp_path / "src" / "app" / "api" / "oracle"
    route.mkdir(parents=True)
    route_file = route / "route.ts"
    route_file.write_text(
        "const apiKey = process.env.GEMINI_API_KEY;\n"
        "await fetch('https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-2.5-flash:generateContent?key=' + apiKey);\n",
        encoding="utf-8",
    )
    inv = build_repo_inventory(tmp_path)
    features = extract_features(inv, ScanConfig())
    keys = {c.key for c in features.configs}
    assert "gemini_api_key" in keys
    assert "generativelanguage.googleapis.com" in keys


def test_derive_config_ai_callsites_from_gemini_route(tmp_path: Path):
    route = tmp_path / "src" / "app" / "api" / "oracle"
    route.mkdir(parents=True)
    (route / "route.ts").write_text(
        "const apiKey = process.env.GEMINI_API_KEY;\n"
        "await fetch('https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-2.5-flash:generateContent?key=' + apiKey);\n",
        encoding="utf-8",
    )
    inv = build_repo_inventory(tmp_path)
    features = extract_features(inv, ScanConfig())
    callsites, matches = derive_config_ai_callsites(features)
    assert callsites
    assert any(m.usage_type == AiUsageType.LLM_INFERENCE for m in matches.values())
    assert any(m.reason == "config_llm_signal" for m in matches.values())


def test_gate_includes_config_derived_gemini_callsite(tmp_path: Path):
    route = tmp_path / "src" / "app" / "api" / "oracle"
    route.mkdir(parents=True)
    (route / "route.ts").write_text(
        "const apiKey = process.env.GEMINI_API_KEY;\n"
        "await fetch('https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-2.5-flash:generateContent?key=' + apiKey);\n",
        encoding="utf-8",
    )
    inv = build_repo_inventory(tmp_path)
    features = extract_features(inv, ScanConfig())
    contexts = build_file_ai_context_map(features, [])
    gated = gate_features_for_intent(features, contexts)
    assert gated.usage_matches
    assert any(
        m.usage_type == AiUsageType.LLM_INFERENCE and m.reason == "config_llm_signal"
        for m in gated.usage_matches.values()
    )
    assert any("oracle/route.ts" in loc for loc in gated.usage_matches)


def test_match_config_llm_usage_returns_none_for_unrelated_key():
    cfg = ConfigRef(
        key="database_url",
        location="src/db.ts:1",
        scope=EvidenceScope.PROD,
        kind="config_key",
    )
    assert match_config_llm_usage(cfg) is None
