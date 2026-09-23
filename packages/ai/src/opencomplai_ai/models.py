"""IntentAnnotation pydantic model and MODEL_CATALOG."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from opencomplai_core.knowledge.subject_cues import (
    NATURAL_PERSON_CUES,
    PRODUCT_OR_ENTITY_CUES,
)
from pydantic import BaseModel, Field

DecisionAutonomy = Literal[
    "autonomous", "advisory", "human_in_loop", "display_only", "unknown"
]
SubjectType = Literal["natural_person", "legal_entity", "system", "unknown"]
Consequential = Literal["yes", "no", "unknown"]
RiskTier = Literal["prohibited", "high_risk", "limited_risk", "minimal"]

REGULATORY_RISK_TIERS: frozenset[str] = frozenset(
    {"prohibited", "high_risk", "limited_risk"}
)

# Annex III area → SignalCategory name (used by derive_eu_obligations and detector)
_AREA_TO_SIGNAL_CATEGORY: dict[int, str] = {
    1: "BIOMETRIC",
    2: "SCORING_PROFILING",
    3: "SCORING_PROFILING",
    4: "SCORING_PROFILING",
    5: "SCORING_PROFILING",
    6: "SCORING_PROFILING",
    7: "SCORING_PROFILING",
    8: "SCORING_PROFILING",
}

# ── Natural-person subject gating ────────────────────────────────────────
#
# NATURAL_PERSON_CUES and PRODUCT_OR_ENTITY_CUES (imported above) are
# bundled into core (opencomplai_core.knowledge.subject_cues — see that
# module's docstring for the full rationale) so opencomplai_core.rules
# gates on the same non-empty cue sets whether or not this optional plugin
# is installed. Re-exported here at the same names for backward
# compatibility with existing opencomplai-ai importers; edit the cue
# contents only in core.


def subject_looks_like_natural_person(text: str) -> bool | None:
    """Infer whether ``text`` scores/profiles a natural person from lexical cues.

    Returns True if a person cue is present (regardless of product cues —
    e.g. "score the applicant's company" still concerns a person's credit
    file). Returns False only when a product/entity cue is present AND no
    person cue is present. Returns None when neither list matches, meaning
    the caller should treat the subject as unresolved (default to high-risk
    rather than silently downgrading).
    """
    tokens = set(re.split(r"[^a-z0-9]+", text.lower()))
    has_person = bool(tokens & NATURAL_PERSON_CUES)
    if has_person:
        return True
    has_product = bool(tokens & PRODUCT_OR_ENTITY_CUES)
    if has_product:
        return False
    return None


class ModelNotInstalledError(RuntimeError):
    """Raised when a catalog entry's hard runtime dependency is missing.

    Shared by ``registry.resolve`` (checked at backend construction) and
    ``downloader.ensure_model`` (checked before any download) so both sites
    raise the identical error type with the identical actionable message —
    a base install must fail the same way regardless of which one runs first.
    """


@dataclass(frozen=True)
class ModelSpec:
    model_id: str
    display_name: str
    size_mb: int
    license: str
    runtime: str
    hf_repo: str
    filename: str
    requires_deep: bool
    #: Immutable Hugging Face revision (commit SHA or tag). Downloading from
    #: the default branch means a compromised or taken-over repo silently
    #: serves altered weights that then execute against customer code
    #: (AI-EGRESS, finding 77). Empty means unpinned — `ensure_model` refuses
    #: to download such a spec unless the pin is explicitly waived.
    revision: str = ""
    #: Expected sha256 of `filename`, verified after download AND on every
    #: cache hit. Verifying only on download would let a later local
    #: modification of the cached file go unnoticed forever. Empty means
    #: unverified.
    sha256: str = ""
    #: False for backends that classify() without any local artifact or
    #: setup step: codebert-onnx (a deterministic code-signal matcher — see
    #: classifier.IntentClassifier) and saas (a cloud API client). The
    #: registry never calls ensure_model for either at classification time,
    #: so the CLI's pre-scan preload must not either — for codebert-onnx it
    #: routed into the separate, optional ONNX-export path, which prompts
    #: for a ~440 MB download (or raises in non-interactive runs, silently
    #: disabling --ai-intent) even though the backend needs zero setup.
    needs_preload: bool = True


MODEL_CATALOG: dict[str, ModelSpec] = {
    "codebert-onnx": ModelSpec(
        model_id="codebert-onnx",
        # Deterministic Annex III / prohibited-practice / limited-risk
        # code-signal matcher (see classifier.IntentClassifier) — no model
        # weights are loaded and nothing is downloaded on the classification
        # path. hf_repo/filename/runtime below back only the separate,
        # optional ONNX export exposed via `ensure_model` (e.g. an explicit
        # `opencomplai ai configure` prefetch), which needs the `[onnx]`
        # extra and is not part of normal --ai-intent scanning.
        display_name="CodeBERT code-signal matcher (deterministic, no download)",
        size_mb=0,
        license="MIT",
        runtime="onnxruntime",
        hf_repo="microsoft/codebert-base",
        filename="codebert-base-onnx.tar.gz",
        requires_deep=False,
        needs_preload=False,
    ),
    "qwen2.5-coder-0.5b": ModelSpec(
        model_id="qwen2.5-coder-0.5b",
        display_name="Qwen2.5-Coder-0.5B-Instruct",
        size_mb=400,
        license="Apache-2.0",
        runtime="llama-cpp",
        hf_repo="Qwen/Qwen2.5-Coder-0.5B-Instruct-GGUF",
        filename="qwen2.5-coder-0.5b-instruct-q4_k_m.gguf",
        requires_deep=True,
    ),
    "qwen2.5-coder-1.5b": ModelSpec(
        model_id="qwen2.5-coder-1.5b",
        display_name="Qwen2.5-Coder-1.5B-Instruct (recommended)",
        size_mb=1000,
        license="Apache-2.0",
        runtime="llama-cpp",
        hf_repo="Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF",
        filename="qwen2.5-coder-1.5b-instruct-q4_k_m.gguf",
        requires_deep=True,
    ),
    "smollm2-1.7b": ModelSpec(
        model_id="smollm2-1.7b",
        display_name="SmolLM2-1.7B-Instruct",
        size_mb=1100,
        license="Apache-2.0",
        runtime="llama-cpp",
        hf_repo="HuggingFaceTB/SmolLM2-1.7B-Instruct-GGUF",
        filename="smollm2-1.7b-instruct-q4_k_m.gguf",
        requires_deep=True,
    ),
    "phi-3.5-mini": ModelSpec(
        model_id="phi-3.5-mini",
        display_name="Phi-3.5-mini-instruct",
        size_mb=2200,
        license="MIT",
        runtime="llama-cpp",
        hf_repo="microsoft/Phi-3.5-mini-instruct-gguf",
        filename="Phi-3.5-mini-instruct-Q4_K_M.gguf",
        requires_deep=True,
    ),
    "mistral-7b": ModelSpec(
        model_id="mistral-7b",
        display_name="Mistral-7B-Instruct-v0.3",
        size_mb=4100,
        license="Apache-2.0",
        runtime="llama-cpp",
        hf_repo="MaziyarPanahi/Mistral-7B-Instruct-v0.3-GGUF",
        filename="Mistral-7B-Instruct-v0.3.Q4_K_M.gguf",
        requires_deep=True,
    ),
    "saas": ModelSpec(
        model_id="saas",
        display_name="Cloud API (GPT-4o / Claude)",
        size_mb=0,
        license="—",
        runtime="http",
        hf_repo="",
        filename="",
        requires_deep=False,
        needs_preload=False,
    ),
}


def derive_eu_obligations(
    decision_autonomy: DecisionAutonomy,
    subject_type: SubjectType,
    consequential: Consequential,
    annex_iii_area: int | None = None,
) -> list[str]:
    """Return the EU obligation articles for an AI callsite.

    When ``annex_iii_area`` is resolved (set by the knowledge-grounded classifier),
    obligations are read directly from the Annex III knowledge pack — the exact
    articles from the regulation, not a generic fallback.

    ``decision_autonomy`` / ``subject_type`` / ``consequential`` are retained as
    secondary signals for tier nuance (autonomous → full set, human_in_loop →
    Art.14 emphasis) when no specific area is resolved.

    ``subject_type`` also gates: several Annex III sub-points (credit scoring,
    insurance pricing, employment, education, ...) apply only when the AI
    system scores/profiles a natural person. When the resolved area is
    ``subject_gated`` and the caller has positively identified the subject
    as a ``legal_entity`` or ``system`` (e.g. a product, portfolio, or
    commercial counterparty), the high-risk obligation set does not apply —
    this falls through to the disclosure-level fallback below instead of
    silently returning full Annex III obligations for an out-of-scope use.
    """
    if annex_iii_area is not None:
        from opencomplai_ai.knowledge.annex_iii import lookup_by_area

        entries = lookup_by_area(annex_iii_area)
        if entries:
            entry = entries[0]
            if entry.subject_gated and subject_type in ("legal_entity", "system"):
                return [
                    "Not Annex III high-risk: scoring subject is not a natural "
                    f"person ({entry.title} is scoped to natural persons per "
                    "Annex III). Re-verify if the manifest's declared purpose "
                    "changes.",
                    "Art.50 disclosure if user-facing",
                ]
            base = list(entry.obligation_articles)
            # Art.14 human oversight is already in every pack entry; for human_in_loop
            # emphasise it by noting the override applies.
            if decision_autonomy == "human_in_loop":
                base = [a for a in base if "Art.14" not in a]
                base.insert(0, "Art.14 human oversight (human-in-loop emphasis)")
            return base

    # ── Fallback: no resolved area — use autonomy/subject/consequential heuristic ──
    if decision_autonomy == "autonomous" and subject_type == "natural_person":
        if consequential == "yes":
            return [
                "Art.6(2)+Annex III",
                "Art.9 risk mgmt",
                "Art.13 transparency",
                "Art.14 human oversight",
                "Art.43 conformity assessment",
                "Art.49 EU DB registration",
            ]
        return ["Art.13 transparency", "Art.14 human oversight", "Art.50 disclosure"]

    if decision_autonomy == "advisory" and subject_type == "natural_person":
        if consequential in ("yes", "unknown"):
            return [
                "Art.6(2)+Annex III",
                "Art.9 risk mgmt",
                "Art.13 transparency",
                "Art.14 human oversight",
                "Art.43 conformity assessment",
                "Art.49 EU DB registration",
            ]
        return ["Art.13 transparency", "Art.50 disclosure if user-facing"]

    if decision_autonomy == "human_in_loop" and subject_type == "natural_person":
        return [
            "Art.14 human oversight (human-in-loop emphasis)",
            "Art.13 transparency",
        ]

    if decision_autonomy == "display_only":
        return ["Art.50 transparency disclosure if user-facing"]

    if consequential == "yes" and subject_type == "natural_person":
        return ["Art.13 transparency", "logging required"]

    if decision_autonomy == "autonomous":
        return ["Art.50 disclosure", "human oversight recommended"]

    return ["Art.50 disclosure if user-facing"]


def apply_subject_gate_backstop(
    area: int | None, subject: str, art6_3_profiling: bool
) -> tuple[int | None, bool, str | None]:
    """Defensive backstop shared by the local GGUF backend
    (explainer._parse_annotation) and the cloud backend
    (_saas_client.SaaSIntentClient.classify).

    The system prompt instructs the model to leave annex_iii_area null when
    the scored subject isn't a natural person, but LLM output is
    probabilistic and can be self-inconsistent (area set + subject_type
    correctly "legal_entity"/"system" in the same response). Cross-check
    against the pack's subject_gated flag rather than trusting area and
    subject_type to already agree. art6_3_profiling is only cleared when
    this conflict fires — Art. 6(3) profiling applies regardless of whether
    a specific Annex III area was also resolved, so a null area on its own
    must never suppress the flag.

    Returns (area, art6_3_profiling, explanation_override); the override is
    None unless the backstop fired.
    """
    if area is not None and subject in ("legal_entity", "system"):
        from opencomplai_ai.knowledge.annex_iii import lookup_by_area

        entries = lookup_by_area(area)
        if entries and entries[0].subject_gated:
            return (
                None,
                False,
                "Annex III area suppressed: model reported subject_type="
                f"{subject}, and this area is scoped to natural persons.",
            )
    return area, art6_3_profiling, None


def derive_risk_tier(
    *,
    art5_prohibited: bool = False,
    annex_iii_area: int | None = None,
    limited_risk: bool = False,
) -> RiskTier:
    if art5_prohibited:
        return "prohibited"
    if annex_iii_area is not None:
        return "high_risk"
    if limited_risk:
        return "limited_risk"
    return "minimal"


class IntentAnnotation(BaseModel):
    decision_autonomy: DecisionAutonomy = "unknown"
    subject_type: SubjectType = "unknown"
    consequential: Consequential = "unknown"
    annex_iii_area: int | None = None
    art5_prohibited: bool = False
    art6_3_profiling: bool = False
    risk_tier: RiskTier = "minimal"
    ai_usage_type: str | None = None
    eu_obligation: list[str] = []
    explanation: str | None = None
    needed_action: str | None = None
    matched_signals: list[str] = Field(default_factory=list)
    gate_reason: str | None = None
    knowledge_entry_title: str | None = None
    regulation_ref: str | None = None
    declared_purpose_used: bool = False
    model_id: str = ""
    confidence: float = 0.0
