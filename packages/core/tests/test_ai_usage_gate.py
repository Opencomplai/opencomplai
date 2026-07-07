"""Tests for callsite-level AI usage gate."""

from __future__ import annotations

from pathlib import Path

from opencomplai_core.models import EvidenceScope
from opencomplai_core.scanner.ai_usage_gate import (
    AiUsageType,
    gate_features_for_intent,
    is_ai_usage_callsite,
)
from opencomplai_core.scanner.feature_types import CallsiteRef, FeatureStore, ImportRef
from opencomplai_core.scanner.file_ai_context import FileAiContext


def _ctx(**kwargs) -> FileAiContext:
    defaults = {"file_path": "src/app.py"}
    defaults.update(kwargs)
    return FileAiContext(**defaults)


def test_apirouter_rejected():
    ref = CallsiteRef(
        name="APIRouter", location="src/routes.py:5", scope=EvidenceScope.PROD
    )
    assert (
        is_ai_usage_callsite(
            ref, "router = APIRouter()", _ctx(file_path="src/routes.py")
        )
        is None
    )


def test_asgitransport_rejected_even_with_biometric_context():
    ref = CallsiteRef(
        name="ASGITransport",
        location="tests/test_dlp.py:12",
        scope=EvidenceScope.TEST,
    )
    ctx = _ctx(
        file_path="tests/test_dlp.py",
        has_lexical_ai_evidence=True,
        ai_imports=["face_recognition"],
        has_ml_sdk=True,
    )
    assert is_ai_usage_callsite(ref, "transport = ASGITransport(app)", ctx) is None


def test_openai_import_accepted():
    ref = ImportRef(module="openai", location="src/llm.py:1", scope=EvidenceScope.PROD)
    match = is_ai_usage_callsite(ref, "import openai", _ctx(file_path="src/llm.py"))
    assert match is not None
    assert match.usage_type == AiUsageType.LLM_INFERENCE
    assert match.reason == "ai_import"


def test_openai_chat_callsite_accepted():
    ref = CallsiteRef(
        name="client.chat.completions.create",
        location="src/llm.py:4",
        scope=EvidenceScope.PROD,
    )
    ctx = _ctx(file_path="src/llm.py", ai_imports=["openai"], has_ml_sdk=True)
    match = is_ai_usage_callsite(
        ref,
        "response = client.chat.completions.create(model='gpt-4')",
        ctx,
    )
    assert match is not None
    assert match.usage_type == AiUsageType.LLM_INFERENCE


def test_bare_score_rejected_without_ml_context():
    ref = CallsiteRef(
        name="score", location="src/utils.py:10", scope=EvidenceScope.PROD
    )
    assert (
        is_ai_usage_callsite(
            ref, "total = score(items)", _ctx(file_path="src/utils.py")
        )
        is None
    )


def test_score_accepted_with_ml_context(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    risk_file = src / "risk.py"
    risk_file.write_text(
        "import sklearn\n"
        "def rank_applicants(features):\n"
        "    return model.predict_proba(features)\n",
        encoding="utf-8",
    )
    ref = CallsiteRef(
        name="predict_proba",
        location=f"{risk_file}:4",
        scope=EvidenceScope.PROD,
    )
    ctx = _ctx(
        file_path=str(risk_file),
        has_ml_sdk=True,
        ai_imports=["sklearn"],
    )
    match = is_ai_usage_callsite(ref, "return model.predict_proba(features)", ctx)
    assert match is not None
    assert match.usage_type in (AiUsageType.ML_INFERENCE, AiUsageType.SCORING)


def test_gate_filters_router_in_ai_file(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    app_file = src / "app.py"
    app_file.write_text(
        "import openai\n"
        "from fastapi import APIRouter\n\n"
        "router = APIRouter()\n"
        "client = openai.Client()\n"
        "result = client.chat.completions.create()\n",
        encoding="utf-8",
    )

    features = FeatureStore(repo_root=tmp_path)
    features.imports.extend(
        [
            ImportRef(
                module="openai", location=f"{app_file}:1", scope=EvidenceScope.PROD
            ),
            ImportRef(
                module="fastapi", location=f"{app_file}:2", scope=EvidenceScope.PROD
            ),
        ]
    )
    features.callsites.extend(
        [
            CallsiteRef(
                name="APIRouter", location=f"{app_file}:4", scope=EvidenceScope.PROD
            ),
            CallsiteRef(
                name="client.chat.completions.create",
                location=f"{app_file}:6",
                scope=EvidenceScope.PROD,
            ),
        ]
    )

    ctx_map = {
        str(app_file): FileAiContext(
            file_path=str(app_file),
            ai_imports=["openai"],
            has_ml_sdk=True,
        )
    }
    gated = gate_features_for_intent(features, ctx_map)
    tokens = {c.name for c in gated.features.callsites}
    assert "APIRouter" not in tokens
    assert "client.chat.completions.create" in tokens
    assert len(gated.usage_matches) >= 2  # openai import + chat call
