"""CodeBERT-ONNX intent classification backend."""

from __future__ import annotations

import math
from pathlib import Path
from typing import TYPE_CHECKING

from opencomplai_ai.models import (
    MODEL_CATALOG,
    IntentAnnotation,
    derive_eu_obligations,
)

if TYPE_CHECKING:
    pass

AUTONOMY_PATTERNS = {
    "autonomous": "AI model output used directly to make a decision without human review",
    "advisory": "AI model output shown as a recommendation a human can override",
    "human_in_loop": "AI model output requires explicit human approval before any action",
    "display_only": "AI model generates content displayed to user with no system effect",
}

SUBJECT_PATTERNS = {
    "natural_person": "affects individual people users persons employees applicants patients",
    "legal_entity": "affects companies organisations businesses corporations entities",
    "system": "internal system pipeline automation infrastructure monitoring",
}

CONSEQUENTIAL_PATTERNS = {
    "yes": "decision has real consequences affects rights access benefits risks outcomes",
    "no": "informational display only no downstream effect no action taken",
}


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class IntentClassifier:
    def __init__(self) -> None:
        from opencomplai_ai.downloader import ensure_model

        model_path = ensure_model("codebert-onnx")
        self._model_path = model_path
        self._session = None
        self._tokenizer = None
        self._pattern_embeddings: dict[str, dict[str, list[float]]] = {}

    def _load(self) -> None:
        if self._session is not None:
            return
        try:
            import onnxruntime as ort
            from transformers import AutoTokenizer
        except ImportError as exc:
            raise ImportError(
                "onnxruntime and transformers are required for codebert-onnx. "
                "Run: pip install onnxruntime transformers"
            ) from exc

        model_dir = self._model_path.parent / "codebert-base"
        if model_dir.is_dir():
            onnx_file = model_dir / "model.onnx"
        else:
            onnx_file = self._model_path

        self._tokenizer = AutoTokenizer.from_pretrained("microsoft/codebert-base")
        self._session = ort.InferenceSession(str(onnx_file))
        self._precompute_pattern_embeddings()

    def _embed(self, text: str) -> list[float]:
        import numpy as np

        tokens = self._tokenizer(
            text, return_tensors="np", truncation=True, max_length=128, padding=True
        )
        inputs = {k: v for k, v in tokens.items() if k in ("input_ids", "attention_mask")}
        outputs = self._session.run(None, inputs)
        embedding = outputs[0][0].mean(axis=0).tolist()
        return embedding

    def _precompute_pattern_embeddings(self) -> None:
        for dim, patterns in [
            ("autonomy", AUTONOMY_PATTERNS),
            ("subject", SUBJECT_PATTERNS),
            ("consequential", CONSEQUENTIAL_PATTERNS),
        ]:
            self._pattern_embeddings[dim] = {
                label: self._embed(text) for label, text in patterns.items()
            }

    def _classify_dim(self, snippet_embedding: list[float], dim: str) -> tuple[str, float]:
        best_label = "unknown"
        best_score = -1.0
        for label, pattern_emb in self._pattern_embeddings.get(dim, {}).items():
            score = _cosine_similarity(snippet_embedding, pattern_emb)
            if score > best_score:
                best_score = score
                best_label = label
        return best_label, max(0.0, best_score)

    def classify(self, snippet: str) -> IntentAnnotation:
        try:
            self._load()
            embedding = self._embed(snippet)
            autonomy, conf_a = self._classify_dim(embedding, "autonomy")
            subject, conf_s = self._classify_dim(embedding, "subject")
            consequential, conf_c = self._classify_dim(embedding, "consequential")
            confidence = round((conf_a + conf_s + conf_c) / 3, 4)
            obligations = derive_eu_obligations(autonomy, subject, consequential)  # type: ignore[arg-type]
            return IntentAnnotation(
                decision_autonomy=autonomy,  # type: ignore[arg-type]
                subject_type=subject,  # type: ignore[arg-type]
                consequential=consequential,  # type: ignore[arg-type]
                eu_obligation=obligations,
                model_id="codebert-onnx",
                confidence=confidence,
            )
        except Exception:
            return IntentAnnotation(model_id="codebert-onnx")
