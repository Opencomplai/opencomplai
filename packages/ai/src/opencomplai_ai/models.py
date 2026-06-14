"""IntentAnnotation pydantic model and MODEL_CATALOG."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

DecisionAutonomy = Literal["autonomous", "advisory", "human_in_loop", "display_only", "unknown"]
SubjectType = Literal["natural_person", "legal_entity", "system", "unknown"]
Consequential = Literal["yes", "no", "unknown"]


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


MODEL_CATALOG: dict[str, ModelSpec] = {
    "codebert-onnx": ModelSpec(
        model_id="codebert-onnx",
        display_name="CodeBERT-base (ONNX)",
        size_mb=440,
        license="MIT",
        runtime="onnxruntime",
        hf_repo="microsoft/codebert-base",
        filename="codebert-base-onnx.tar.gz",
        requires_deep=False,
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
    ),
}

_EU_OBLIGATION_MAP: list[tuple[DecisionAutonomy, SubjectType, Consequential, str, list[str]]] = [
    ("autonomous", "natural_person", "yes", "HIGH_RISK",
     ["Art.6(2)+Annex III", "technical dossier required", "conformity assessment", "EU DB registration"]),
    ("advisory", "natural_person", "yes", "HIGH_RISK",
     ["Art.6(2)+Annex III", "technical dossier required", "conformity assessment", "EU DB registration"]),
    ("human_in_loop", "natural_person", "yes", "LIMITED_RISK",
     ["Art.13 transparency", "logging of human overrides required"]),
    ("display_only", "natural_person", "yes", "MINIMAL_RISK",
     ["Art.52 disclosure if user-facing"]),
    ("display_only", "legal_entity", "yes", "MINIMAL_RISK",
     ["Art.52 disclosure if user-facing"]),
    ("display_only", "system", "yes", "MINIMAL_RISK",
     ["Art.52 disclosure if user-facing"]),
    ("display_only", "unknown", "yes", "MINIMAL_RISK",
     ["Art.52 disclosure if user-facing"]),
]


def derive_eu_obligations(
    decision_autonomy: DecisionAutonomy,
    subject_type: SubjectType,
    consequential: Consequential,
) -> list[str]:
    for autonomy, subject, consq, _tier, obligations in _EU_OBLIGATION_MAP:
        if autonomy == decision_autonomy and subject == subject_type and consq == consequential:
            return obligations
    if consequential == "yes" and subject_type == "natural_person":
        return ["Art.13 transparency", "logging required"]
    if decision_autonomy == "autonomous":
        return ["Art.52 disclosure", "human oversight recommended"]
    return ["Art.52 disclosure if user-facing"]


class IntentAnnotation(BaseModel):
    decision_autonomy: DecisionAutonomy = "unknown"
    subject_type: SubjectType = "unknown"
    consequential: Consequential = "unknown"
    eu_obligation: list[str] = []
    explanation: str | None = None
    model_id: str = ""
    confidence: float = 0.0
