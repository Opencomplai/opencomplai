"""IntentDetector — DET_INTENT_V1, BaseDetector subclass."""

from __future__ import annotations

from typing import TYPE_CHECKING

from opencomplai_core.models import EvidenceItem, EvidenceKind, Reachability
from opencomplai_core.scanner.base import BaseDetector
from opencomplai_core.scanner.detectors._common import build_evidence
from opencomplai_core.scanner.feature_types import FeatureStore, ScanProgressCallback
from opencomplai_core.scanner.snippet_cache import SnippetCache

from opencomplai_ai.registry import ModelRegistry

if TYPE_CHECKING:
    from opencomplai_ai.models import IntentAnnotation


class IntentDetector(BaseDetector):
    def __init__(self, model_id: str) -> None:
        self._model_id = model_id
        self._snippet_cache = SnippetCache()

    @property
    def detector_id(self) -> str:
        return "DET_INTENT_V1"

    @property
    def detector_version(self) -> str:
        return "1.1.0"

    @property
    def supported_languages(self) -> frozenset[str]:
        return frozenset({"python", "javascript", "typescript", "java", "go", "rust"})

    @property
    def evidence_kinds(self) -> frozenset[str]:
        return frozenset({"callsite", "import"})

    def detect(
        self,
        features: FeatureStore,
        progress_cb: ScanProgressCallback | None = None,
        declared_purpose: str = "",
        usage_matches: dict | None = None,
        *,
        ai_legacy: bool = False,
    ) -> list[EvidenceItem]:
        backend = ModelRegistry.resolve(self._model_id)
        evidence: list[EvidenceItem] = []
        usage_matches = usage_matches or {}

        callsites = [*features.callsites, *features.imports]
        for i, ref in enumerate(callsites):
            token = getattr(ref, "name", None) or getattr(ref, "module", "")
            narrow = self._snippet_cache.read_narrow(ref.location, half_window=2)
            if not narrow:
                narrow = token

            usage = usage_matches.get(ref.location)
            ai_usage_type = usage.usage_type.value if usage else None

            classify_kwargs: dict = {
                "declared_purpose": declared_purpose,
                "location": ref.location,
                "token": token,
                "ai_usage_type": ai_usage_type,
                "legacy": ai_legacy,
            }
            if usage:
                classify_kwargs["gate_reason"] = usage.reason
            snippet = self._snippet_cache.read(ref.location) if ai_legacy else narrow
            annotation = backend.classify(snippet, **classify_kwargs)

            if annotation is None:
                if progress_cb:
                    progress_cb.on_step("ai_intent", i + 1, token)
                continue

            if getattr(annotation, "ai_usage_type", None) is None and ai_usage_type:
                annotation = annotation.model_copy(
                    update={"ai_usage_type": ai_usage_type}
                )

            category = _resolve_category(annotation)
            ev = build_evidence(
                detector_id=self.detector_id,
                detector_version=self.detector_version,
                evidence_kind=EvidenceKind.CALLSITE,
                category=category,
                token_label=token or "intent",
                location=ref.location,
                scope=ref.scope,
                rationale_code=f"ai_intent:{annotation.risk_tier}",
                confidence=annotation.confidence if annotation.confidence > 0 else 0.5,
                reachability=Reachability.INTERNAL_CALLCHAIN,
            )
            ev = ev.model_copy(update={"intent_annotation": annotation})
            evidence.append(ev)

            if progress_cb:
                progress_cb.on_step("ai_intent", i + 1, token)

        return evidence


def _resolve_category(annotation: IntentAnnotation):
    """Map regulatory IntentAnnotation to SignalCategory for fusion."""
    from opencomplai_core.models import SignalCategory

    from opencomplai_ai.models import _AREA_TO_SIGNAL_CATEGORY, REGULATORY_RISK_TIERS

    tier = getattr(annotation, "risk_tier", "minimal")
    if tier not in REGULATORY_RISK_TIERS:
        return SignalCategory.AI_SDK

    if annotation.annex_iii_area is not None:
        cat_name = _AREA_TO_SIGNAL_CATEGORY.get(annotation.annex_iii_area)
        if cat_name:
            return getattr(SignalCategory, cat_name)

    if annotation.art6_3_profiling or annotation.art5_prohibited:
        return SignalCategory.SCORING_PROFILING

    if tier == "limited_risk":
        return SignalCategory.PROMPT_AGENT

    return SignalCategory.SCORING_PROFILING
