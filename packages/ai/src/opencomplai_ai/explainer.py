"""llama-cpp backend — shared by all GGUF models."""

from __future__ import annotations

import json
import threading

from opencomplai_ai.models import IntentAnnotation, derive_eu_obligations

_PROMPT_TEMPLATE = """\
You are a code compliance analyst. Analyse the following code snippet and answer three questions as JSON.

Code:
```
{snippet}
```

Respond ONLY with a JSON object (no markdown, no explanation):
{{
  "decision_autonomy": "<autonomous|advisory|human_in_loop|display_only>",
  "subject_type": "<natural_person|legal_entity|system>",
  "consequential": "<yes|no>",
  "explanation": "<one sentence>"
}}

Rules:
- decision_autonomy "autonomous": AI output directly drives a decision without human review.
- decision_autonomy "advisory": AI output is a recommendation a human can override.
- decision_autonomy "human_in_loop": AI output requires explicit human approval.
- decision_autonomy "display_only": AI output is shown to user with no system effect.
- subject_type: who is affected — natural_person, legal_entity, or system.
- consequential: does the decision affect rights, access, benefits, or risks (yes/no)?
"""


class IntentExplainer:
    def __init__(self, model_id: str) -> None:
        from opencomplai_ai.downloader import ensure_model

        self._model_id = model_id
        self._model_path = ensure_model(model_id)
        self._llama = None
        self._lock = threading.Lock()

    def _load(self) -> None:
        if self._llama is not None:
            return
        try:
            from llama_cpp import Llama
        except ImportError as exc:
            raise ImportError(
                "llama-cpp-python is required for GGUF models. "
                "Run: pip install 'opencomplai-ai[deep]'"
            ) from exc

        self._llama = Llama(
            model_path=str(self._model_path),
            n_ctx=2048,
            verbose=False,
        )

    def classify(self, snippet: str) -> IntentAnnotation:
        try:
            with self._lock:
                self._load()

            prompt = _PROMPT_TEMPLATE.format(snippet=snippet[:500])

            result = None
            completed = threading.Event()

            def _run() -> None:
                nonlocal result
                try:
                    output = self._llama(
                        prompt,
                        max_tokens=256,
                        temperature=0.0,
                        stop=["```"],
                    )
                    result = output["choices"][0]["text"]
                except Exception:
                    result = None
                finally:
                    completed.set()

            t = threading.Thread(target=_run, daemon=True)
            t.start()
            completed.wait(timeout=10)

            if result is None:
                return IntentAnnotation(model_id=self._model_id)

            raw = result.strip()
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start == -1 or end == 0:
                return IntentAnnotation(model_id=self._model_id)

            data = json.loads(raw[start:end])
            autonomy = data.get("decision_autonomy", "unknown")
            subject = data.get("subject_type", "unknown")
            consequential = data.get("consequential", "unknown")
            explanation = data.get("explanation")
            obligations = derive_eu_obligations(autonomy, subject, consequential)  # type: ignore[arg-type]
            return IntentAnnotation(
                decision_autonomy=autonomy,  # type: ignore[arg-type]
                subject_type=subject,  # type: ignore[arg-type]
                consequential=consequential,  # type: ignore[arg-type]
                eu_obligation=obligations,
                explanation=explanation,
                model_id=self._model_id,
                confidence=0.75,
            )
        except Exception:
            return IntentAnnotation(model_id=self._model_id)
