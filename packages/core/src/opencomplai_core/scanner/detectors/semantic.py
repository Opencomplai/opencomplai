"""Semantic detector — scoring, prompts, agents from identifiers."""

from __future__ import annotations

import re

from opencomplai_core.models import (
    EvidenceItem,
    EvidenceKind,
    Reachability,
    SignalCategory,
)
from opencomplai_core.scanner.base import BaseDetector
from opencomplai_core.scanner.detectors._common import build_evidence
from opencomplai_core.scanner.detectors._signals import match_token_identifier
from opencomplai_core.scanner.feature_types import FeatureStore

PROMPT_PATTERN = re.compile(r"\b(prompt|agent|tool_call|rag|retrieval)\b", re.I)


class SemanticDetector(BaseDetector):
    @property
    def detector_id(self) -> str:
        return "DET_SEMANTIC_V1"

    @property
    def detector_version(self) -> str:
        return "1.0.0"

    @property
    def supported_languages(self) -> frozenset[str]:
        return frozenset({"python", "javascript", "typescript"})

    @property
    def evidence_kinds(self) -> frozenset[str]:
        return frozenset({"prompt_template", "notebook_cell"})

    def detect(self, features: FeatureStore) -> list[EvidenceItem]:
        evidence: list[EvidenceItem] = []
        for call in features.callsites:
            token = match_token_identifier(call.name, "scoring")
            if token:
                confidence = 0.7 if call.scope.value == "prod" else 0.3
                evidence.append(
                    build_evidence(
                        detector_id=self.detector_id,
                        detector_version=self.detector_version,
                        evidence_kind=EvidenceKind.PROMPT_TEMPLATE,
                        category=SignalCategory.SCORING_PROFILING,
                        token_label=token,
                        location=call.location,
                        scope=call.scope,
                        rationale_code="semantic_scoring",
                        confidence=confidence,
                        reachability=(
                            Reachability.INTERNAL_CALLCHAIN
                            if call.scope.value == "prod"
                            else Reachability.IMPORT_ONLY
                        ),
                    )
                )
        for imp in features.imports:
            path = imp.location.split(":")[0]
            if PROMPT_PATTERN.search(path):
                evidence.append(
                    build_evidence(
                        detector_id=self.detector_id,
                        detector_version=self.detector_version,
                        evidence_kind=EvidenceKind.PROMPT_TEMPLATE,
                        category=SignalCategory.PROMPT_AGENT,
                        token_label="prompt",
                        location=imp.location,
                        scope=imp.scope,
                        rationale_code="semantic_prompt",
                        confidence=0.5,
                    )
                )
        for nb in features.notebooks:
            for label in nb.token_labels:
                cat = (
                    SignalCategory.PROMPT_AGENT
                    if label in ("prompt", "agent")
                    else SignalCategory.AI_SDK
                )
                evidence.append(
                    build_evidence(
                        detector_id=self.detector_id,
                        detector_version=self.detector_version,
                        evidence_kind=EvidenceKind.NOTEBOOK_CELL,
                        category=cat,
                        token_label=label,
                        location=nb.location,
                        scope=nb.scope,
                        rationale_code="notebook_semantic",
                        confidence=0.55,
                    )
                )
        return evidence
