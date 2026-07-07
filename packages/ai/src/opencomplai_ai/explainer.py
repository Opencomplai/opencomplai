"""llama-cpp backend — shared by all GGUF models."""

from __future__ import annotations

import json
import threading

from opencomplai_ai.models import (
    IntentAnnotation,
    derive_eu_obligations,
    derive_risk_tier,
)

_SYSTEM_PROMPT = """\
You are an EU AI Act (Reg. 2024/1689) code auditor. Classify what the code \
does using the Annex III high-risk areas below. Return JSON only — no markdown, \
no explanation outside the JSON object.

ANNEX III HIGH-RISK AREAS (return the integer id or null):
  1  Biometrics: remote biometric ID, categorisation, emotion recognition
  2  Critical infrastructure: road/water/gas/electricity/digital safety components
  3  Education: admission decisions, grading AI, exam proctoring, level assessment
  4  Employment: recruitment/screening, promotion/termination/monitoring AI
  5  Essential services: public benefit eligibility, creditworthiness/credit scoring \
(not fraud detection), insurance pricing, emergency dispatch
  6  Law enforcement: victim/offending risk, polygraph, evidence reliability, \
recidivism, criminal profiling
  7  Migration: asylum/visa/border risk assessment, border identification
  8  Justice & democracy: judicial decision support, election/voting influence

PROHIBITED (Art. 5) — flag art5_prohibited=true if matched (system is BANNED):
  - Social scoring of natural persons
  - Subliminal or manipulative AI causing harm
  - Exploiting vulnerabilities of persons
  - Predictive criminal risk based solely on profiling/traits
  - Untargeted facial recognition database scraping
  - Emotion inference in workplace or educational institutions
  - Biometric categorisation to infer sensitive attributes
  - Real-time remote biometric identification in public spaces (law enforcement)
  - Non-consensual explicit imagery / CSAM generation

ART. 6(3): set art6_3_profiling=true if the system profiles natural persons \
(combines/infers personal attributes) — such systems are ALWAYS high-risk \
regardless of autonomy level.

CRITICAL — WHO IS BEING SCORED, NOT JUST WHAT VERB IS USED:
Areas 3, 4, 5(a-c), 6(a,d,e), and 7(b,c) only apply when the AI system \
scores, ranks, or assesses a NATURAL PERSON (an individual human — an \
applicant, customer, employee, student, patient, citizen, offender, \
migrant, etc.). The same verbs ("score", "predict", "rank", "assess risk") \
are routinely used for subjects that are NOT natural persons and are \
therefore OUT OF SCOPE for these areas:
  - A credit/risk score for a bond, security, loan portfolio, or corporate \
counterparty (not a consumer) is financial risk modeling, not Annex III \
5(b) creditworthiness of natural persons.
  - A fraud score on a transaction, or a quality/defect score on a product \
or SKU, is not a person-scoring system.
  - An insurance pricing model for a commercial fleet or a business policy \
(not an individual's life/health policy) is not Annex III 5(c).
  - A vendor/supplier risk-monitoring score, or an internal system-health \
or infrastructure-reliability score, is not Annex III at all.
Before setting annex_iii_area to 3, 4, 5, 6, or 7, confirm the object being \
scored is a specific natural person whose access, employment, benefits, \
credit, liberty, or similar individual interest is directly affected. If \
the code scores a company, product, portfolio, transaction, or device, \
set subject_type accordingly ("legal_entity" or "system") and leave \
annex_iii_area null even if scoring/ranking vocabulary is present — explain \
this reasoning in one sentence.\
"""

_USER_TEMPLATE = """\
DECLARED SYSTEM PURPOSE: {declared_purpose}

CODE SNIPPET ({location}):
```
{snippet}
```

Return ONLY this JSON (fill every field):
{{
  "annex_iii_area": <integer 1-8 or null>,
  "art5_prohibited": <true or false>,
  "art6_3_profiling": <true or false>,
  "decision_autonomy": "<autonomous|advisory|human_in_loop|display_only>",
  "subject_type": "<natural_person|legal_entity|system>",
  "consequential": "<yes|no>",
  "risk_tier": "<prohibited|high_risk|limited_risk|minimal>",
  "explanation": "<one sentence citing the area/article>"
}}\
"""


def _build_prompt(snippet: str, declared_purpose: str, location: str) -> str:
    user = _USER_TEMPLATE.format(
        snippet=snippet[:600],
        declared_purpose=declared_purpose or "not specified",
        location=location or "unknown",
    )
    return f"{_SYSTEM_PROMPT}\n\n{user}"


def _parse_annotation(data: dict, model_id: str, confidence: float) -> IntentAnnotation:
    area = data.get("annex_iii_area")
    if isinstance(area, float):
        area = int(area) if area == int(area) else None
    if not isinstance(area, int) or area not in range(1, 9):
        area = None

    art5 = bool(data.get("art5_prohibited", False))
    art6_3 = bool(data.get("art6_3_profiling", False))
    autonomy = data.get("decision_autonomy", "unknown")
    subject = data.get("subject_type", "unknown")
    consequential = data.get("consequential", "unknown")
    explanation = data.get("explanation")
    limited = not art5 and area is None and data.get("risk_tier") == "limited_risk"

    # Defensive backstop: the system prompt instructs the model to leave
    # annex_iii_area null when the scored subject isn't a natural person,
    # but LLM output is probabilistic and can be self-inconsistent (area set
    # + subject_type correctly "legal_entity"/"system" in the same response).
    # Cross-check against the pack's subject_gated flag rather than trusting
    # area and subject_type to already agree.
    if area is not None and subject in ("legal_entity", "system"):
        from opencomplai_ai.knowledge.annex_iii import lookup_by_area

        entries = lookup_by_area(area)
        if entries and entries[0].subject_gated:
            area = None
            art6_3 = False
            if not explanation:
                explanation = (
                    "Annex III area suppressed: model reported subject_type="
                    f"{subject}, and this area is scoped to natural persons."
                )

    obligations = derive_eu_obligations(
        autonomy,  # type: ignore[arg-type]
        subject,  # type: ignore[arg-type]
        consequential,  # type: ignore[arg-type]
        annex_iii_area=area,
    )
    tier = data.get("risk_tier")
    if area is None and tier == "high_risk":
        # The area that justified "high_risk" was just suppressed above;
        # don't keep the LLM's stale tier label.
        tier = None
    if tier not in ("prohibited", "high_risk", "limited_risk", "minimal"):
        tier = derive_risk_tier(
            art5_prohibited=art5,
            annex_iii_area=area,
            limited_risk=limited,
        )
    return IntentAnnotation(
        annex_iii_area=area,
        art5_prohibited=art5,
        art6_3_profiling=art6_3,
        risk_tier=tier,  # type: ignore[arg-type]
        decision_autonomy=autonomy,  # type: ignore[arg-type]
        subject_type=subject,  # type: ignore[arg-type]
        consequential=consequential,  # type: ignore[arg-type]
        eu_obligation=obligations,
        explanation=explanation,
        model_id=model_id,
        confidence=confidence,
    )


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

    def classify(
        self,
        snippet: str,
        declared_purpose: str = "",
        location: str = "",
        *,
        token: str = "",
        ai_usage_type: str | None = None,
        legacy: bool = False,
    ) -> IntentAnnotation | None:
        try:
            with self._lock:
                self._load()

            prompt = _build_prompt(snippet, declared_purpose, location)

            result = None
            completed = threading.Event()

            def _run() -> None:
                nonlocal result
                try:
                    output = self._llama(
                        prompt,
                        max_tokens=300,
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
                return (
                    None
                    if not legacy
                    else IntentAnnotation(model_id=self._model_id, risk_tier="minimal")
                )

            raw = result.strip()
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start == -1 or end == 0:
                return (
                    None
                    if not legacy
                    else IntentAnnotation(model_id=self._model_id, risk_tier="minimal")
                )

            data = json.loads(raw[start:end])
            ann = _parse_annotation(data, self._model_id, confidence=0.75)
            if ai_usage_type and ann.ai_usage_type is None:
                ann = ann.model_copy(update={"ai_usage_type": ai_usage_type})
            if ann.risk_tier == "minimal" and not legacy:
                return None
            return ann
        except Exception:
            return (
                None
                if not legacy
                else IntentAnnotation(model_id=self._model_id, risk_tier="minimal")
            )
