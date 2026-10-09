"""llama-cpp backend — shared by all GGUF models."""

from __future__ import annotations

import json
import logging
import math
import os
import threading
import warnings

from pydantic import ValidationError

from opencomplai_ai.models import (
    IntentAnnotation,
    apply_subject_gate_backstop,
    derive_eu_obligations,
    derive_risk_tier,
)

logger = logging.getLogger(__name__)

_TIMEOUT_ENV_VAR = "OPENCOMPLAI_AI_TIMEOUT_SECONDS"
_DEFAULT_TIMEOUT_SECONDS = 10.0


def _resolve_timeout_seconds() -> float:
    """Read the per-completion timeout from OPENCOMPLAI_AI_TIMEOUT_SECONDS.

    Falls back to the documented default (and warns) on anything that isn't
    a positive number, rather than letting a typo turn into an unbounded
    wait or an instant timeout.
    """
    raw = os.environ.get(_TIMEOUT_ENV_VAR)
    if not raw:
        return _DEFAULT_TIMEOUT_SECONDS
    try:
        value = float(raw)
    except ValueError:
        warnings.warn(
            f"{_TIMEOUT_ENV_VAR}={raw!r} is not a number; "
            f"using default {_DEFAULT_TIMEOUT_SECONDS}s.",
            stacklevel=2,
        )
        return _DEFAULT_TIMEOUT_SECONDS
    if not math.isfinite(value) or value <= 0:
        # isfinite() also rejects nan: float("inf") would otherwise pass the
        # positivity check and later crash Event.wait(timeout=inf) with an
        # OverflowError that escapes classify() entirely.
        warnings.warn(
            f"{_TIMEOUT_ENV_VAR}={raw!r} must be a positive, finite number; "
            f"using default {_DEFAULT_TIMEOUT_SECONDS}s.",
            stacklevel=2,
        )
        return _DEFAULT_TIMEOUT_SECONDS
    return value


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
        # json.loads accepts the bare NaN/Infinity tokens, and int() on a
        # non-finite float raises instead of converting — which would escape
        # the ValidationError-only guard around this function's caller.
        area = int(area) if math.isfinite(area) and area == int(area) else None
    if not isinstance(area, int) or area not in range(1, 9):
        area = None

    art5 = bool(data.get("art5_prohibited", False))
    art6_3 = bool(data.get("art6_3_profiling", False))
    autonomy = data.get("decision_autonomy", "unknown")
    subject = data.get("subject_type", "unknown")
    consequential = data.get("consequential", "unknown")
    explanation = data.get("explanation")
    limited = not art5 and area is None and data.get("risk_tier") == "limited_risk"

    area, art6_3, backstop_explanation = apply_subject_gate_backstop(
        area, subject, art6_3
    )
    if backstop_explanation and not explanation:
        explanation = backstop_explanation

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
        # Guards the completion itself, not just _load(). llama-cpp's
        # Llama.__call__ is not thread-safe on one instance, and a
        # timed-out call leaves its worker running as an abandoned daemon
        # thread (see classify()). This lock is acquired by the *caller*
        # and released from *inside the worker* — so a still-running zombie
        # keeps holding it, and the next classify() call can detect that and
        # refuse to start a second, concurrent completion instead of racing
        # the first.
        self._inference_lock = threading.Lock()
        self.timeout_seconds = _resolve_timeout_seconds()
        #: What kept the most recent classify() call from returning a real
        #: annotation: "timeout" | "backend_busy" | "model_load_failed" |
        #: "crash" | "malformed_json" | "invalid_schema" | None (last call
        #: succeeded, or none has run yet). Read by callers that want to
        #: distinguish these instead of a bare None.
        self.last_failure: str | None = None
        self.timeout_count = 0

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
        gate_reason: str | None = None,
        legacy: bool = False,
        import_only: bool = False,
    ) -> IntentAnnotation | None:
        try:
            with self._lock:
                self._load()
        except Exception:
            logger.exception("IntentExplainer(%s): model load failed", self._model_id)
            return self._fail("model_load_failed", legacy)

        # Built before acquiring the inference lock: if this ever raised
        # (it can't today — detector always passes plain strings) after the
        # acquire, the lock would leak and every later call would see a
        # permanent, spurious "backend_busy".
        prompt = _build_prompt(snippet, declared_purpose, location)

        if not self._inference_lock.acquire(blocking=False):
            # A previous call's worker never returned (almost certainly a
            # timed-out completion still running in the background). Starting
            # a second completion now would call self._llama concurrently
            # with that zombie, which is not thread-safe — refuse instead.
            logger.warning(
                "IntentExplainer(%s): a previous completion has not "
                "returned yet (likely timed out); refusing to start a "
                "concurrent one against the same llama instance.",
                self._model_id,
            )
            self.last_failure = "backend_busy"
            return None

        raw_text, crashed = self._run_completion(prompt)

        if raw_text is None and not crashed:
            self.timeout_count += 1
            self.last_failure = "timeout"
            logger.warning(
                "IntentExplainer(%s): completion timed out after %.1fs "
                "(location=%s) — returning no annotation rather than "
                "fabricating one; the worker keeps running in the "
                "background.",
                self._model_id,
                self.timeout_seconds,
                location or "unknown",
            )
            # A timeout means "we don't know", never "minimal risk" — this
            # is the one failure mode that must not fall back to a
            # fabricated annotation even in legacy mode.
            return None

        if crashed:
            return self._fail("crash", legacy)

        data = self._parse_json(raw_text)
        if data is None:
            return self._fail("malformed_json", legacy)

        try:
            ann = _parse_annotation(data, self._model_id, confidence=0.75)
        except ValidationError:
            # Syntactically-valid JSON can still carry schema-invalid values
            # (e.g. decision_autonomy="semi_automated", not in its Literal) —
            # a distinct failure mode from malformed_json (which never even
            # produced a parseable dict). Without this guard the
            # ValidationError raised while constructing IntentAnnotation
            # escaped classify() entirely, and scan_engine's phase-level
            # except then discarded every AI-intent finding for the scan.
            logger.warning(
                "IntentExplainer(%s): model output was valid JSON but failed "
                "schema validation",
                self._model_id,
                exc_info=True,
            )
            return self._fail("invalid_schema", legacy)
        if ai_usage_type and ann.ai_usage_type is None:
            ann = ann.model_copy(update={"ai_usage_type": ai_usage_type})
        if gate_reason and ann.gate_reason is None:
            ann = ann.model_copy(update={"gate_reason": gate_reason})
        self.last_failure = None
        if ann.risk_tier == "minimal" and not legacy:
            return None
        return ann

    def _run_completion(self, prompt: str) -> tuple[str | None, bool]:
        """Run one completion on a worker thread with a bounded wait.

        The inference lock taken by ``classify()`` is released *inside* the
        worker, not by the caller — so on a timeout the lock stays held by
        the still-running worker, and the next ``classify()`` call sees it
        busy rather than invoking ``self._llama`` concurrently.

        Returns ``(raw_text, crashed)``; ``raw_text`` is ``None`` on timeout
        (``crashed`` is only meaningful once the worker has actually run).
        """
        result: str | None = None
        crashed = False
        completed = threading.Event()

        def _run() -> None:
            nonlocal result, crashed
            try:
                output = self._llama(
                    prompt,
                    max_tokens=300,
                    temperature=0.0,
                    stop=["```"],
                )
                result = output["choices"][0]["text"]
            except Exception:
                crashed = True
                logger.exception(
                    "IntentExplainer(%s): llama completion raised",
                    self._model_id,
                )
            finally:
                # Release before signaling completion: a caller that wakes
                # up on `completed` must already be able to re-acquire the
                # lock, or a fast next call would see a false "busy".
                self._inference_lock.release()
                completed.set()

        thread = threading.Thread(target=_run, daemon=True)
        try:
            thread.start()
        except Exception:
            # The worker never ran, so it will never release the lock —
            # release it here or every later call is permanently "busy".
            self._inference_lock.release()
            raise
        if not completed.wait(timeout=self.timeout_seconds):
            return None, False
        return result, crashed

    def _parse_json(self, raw_text: str) -> dict | None:
        raw = raw_text.strip()
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start == -1 or end == 0:
            logger.warning(
                "IntentExplainer(%s): model output had no JSON object: %r",
                self._model_id,
                raw[:200],
            )
            return None
        try:
            return json.loads(raw[start:end])
        except json.JSONDecodeError:
            logger.warning(
                "IntentExplainer(%s): model output was not valid JSON: %r",
                self._model_id,
                raw[start:end][:200],
            )
            return None

    def _fail(self, kind: str, legacy: bool) -> IntentAnnotation | None:
        """Uniform bookkeeping for a non-timeout failure, plus the historical
        legacy-mode fallback of always returning *some* annotation."""
        self.last_failure = kind
        if legacy:
            return IntentAnnotation(model_id=self._model_id, risk_tier="minimal")
        return None
