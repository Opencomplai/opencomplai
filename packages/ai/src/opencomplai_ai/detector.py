"""IntentDetector — DET_INTENT_V1, BaseDetector subclass."""

from __future__ import annotations

from pathlib import Path

from opencomplai_core.models import EvidenceItem, EvidenceKind, EvidenceScope, Reachability
from opencomplai_core.scanner.base import BaseDetector
from opencomplai_core.scanner.detectors._common import build_evidence
from opencomplai_core.scanner.feature_types import FeatureStore

from opencomplai_ai.registry import ModelRegistry


def _read_snippet(location: str, context_lines: int = 10) -> str:
    if ":" not in location:
        return ""
    file_path, _, line_str = location.rpartition(":")
    try:
        line_no = int(line_str)
    except ValueError:
        return ""
    try:
        lines = Path(file_path).read_text(encoding="utf-8", errors="replace").splitlines()
        start = max(0, line_no - 1 - context_lines // 2)
        end = min(len(lines), line_no + context_lines // 2)
        return "\n".join(lines[start:end])
    except OSError:
        return ""


class IntentDetector(BaseDetector):
    def __init__(self, model_id: str) -> None:
        self._model_id = model_id

    @property
    def detector_id(self) -> str:
        return "DET_INTENT_V1"

    @property
    def detector_version(self) -> str:
        return "1.0.0"

    @property
    def supported_languages(self) -> frozenset[str]:
        return frozenset({"python", "javascript", "typescript", "java", "go", "rust"})

    @property
    def evidence_kinds(self) -> frozenset[str]:
        return frozenset({"callsite", "import"})

    def detect(self, features: FeatureStore) -> list[EvidenceItem]:
        backend = ModelRegistry.resolve(self._model_id)
        evidence: list[EvidenceItem] = []

        callsites = [*features.callsites, *features.imports]
        for ref in callsites:
            snippet = _read_snippet(ref.location)
            if not snippet:
                snippet = ref.name if hasattr(ref, "name") else getattr(ref, "module", "")

            annotation = backend.classify(snippet)

            ev = build_evidence(
                detector_id=self.detector_id,
                detector_version=self.detector_version,
                evidence_kind=EvidenceKind.CALLSITE,
                category=_autonomy_to_category(annotation.decision_autonomy),
                token_label=getattr(ref, "name", None) or getattr(ref, "module", "intent"),
                location=ref.location,
                scope=ref.scope,
                rationale_code=f"ai_intent:{annotation.decision_autonomy}",
                confidence=annotation.confidence if annotation.confidence > 0 else 0.5,
            )
            ev = ev.model_copy(update={"intent_annotation": annotation})
            evidence.append(ev)

        return evidence


def _autonomy_to_category(autonomy: str):
    from opencomplai_core.models import SignalCategory

    return {
        "autonomous": SignalCategory.SCORING_PROFILING,
        "advisory": SignalCategory.PROMPT_AGENT,
        "human_in_loop": SignalCategory.PROMPT_AGENT,
        "display_only": SignalCategory.AI_SDK,
    }.get(autonomy, SignalCategory.AI_SDK)
