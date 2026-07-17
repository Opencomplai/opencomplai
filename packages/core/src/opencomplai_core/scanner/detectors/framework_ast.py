"""Framework-object AST detector — distinguishes "imports X" from "constructs and
invokes an X orchestration object" (LangChain AgentExecutor, CrewAI Crew, AutoGen
ConversableAgent, LangGraph StateGraph, etc.).

Supplements (does not replace) the lexical `AstUsageDetector`, which remains the
fast-path/fallback signal for orchestration-library import visibility. This detector
only fires on `FeatureStore.framework_objects` — the joined instantiation+invocation
records produced by `extractors/ast.py::extract_ast_framework_objects`.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from opencomplai_core.models import EvidenceItem, EvidenceKind, Reachability, SignalCategory
from opencomplai_core.scanner.base import BaseDetector
from opencomplai_core.scanner.detectors._common import build_evidence
from opencomplai_core.scanner.feature_types import FeatureStore

_DATA_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "framework_object_signals.json"
)


@lru_cache(maxsize=1)
def load_framework_class_names() -> frozenset[str]:
    data = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    names: set[str] = set()
    for class_list in data.get("framework_classes", {}).values():
        names.update(class_list)
    return frozenset(names)


class FrameworkAstDetector(BaseDetector):
    """Detects framework object construction + invocation (not just import)."""

    @property
    def detector_id(self) -> str:
        return "DET_FRAMEWORK_AST_V1"

    @property
    def detector_version(self) -> str:
        return "1.0.0"

    @property
    def supported_languages(self) -> frozenset[str]:
        return frozenset({"python"})

    @property
    def evidence_kinds(self) -> frozenset[str]:
        return frozenset({"callsite"})

    def detect(self, features: FeatureStore) -> list[EvidenceItem]:
        evidence: list[EvidenceItem] = []
        for ref in features.framework_objects:
            reach = (
                Reachability.REACHABLE_ENTRYPOINT
                if ref.scope.value == "prod"
                else Reachability.IMPORT_ONLY
            )
            evidence.append(
                build_evidence(
                    detector_id=self.detector_id,
                    detector_version=self.detector_version,
                    evidence_kind=EvidenceKind.CALLSITE,
                    category=SignalCategory.AGENT_FRAMEWORK,
                    token_label=ref.class_name,
                    location=ref.invocation_location,
                    scope=ref.scope,
                    rationale_code="framework_object_invoked",
                    confidence=0.9 if ref.scope.value == "prod" else 0.5,
                    reachability=reach,
                )
            )
        return evidence
