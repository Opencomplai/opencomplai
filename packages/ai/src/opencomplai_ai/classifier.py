"""CodeBERT-ONNX intent classification backend — deterministic code_signals matcher."""

from __future__ import annotations

import re
from dataclasses import dataclass

from opencomplai_ai.models import (
    IntentAnnotation,
    derive_eu_obligations,
)


@dataclass(frozen=True)
class _AnnexMatch:
    area: int
    art6_3: bool
    matched_signals: tuple[str, ...]
    entry_title: str
    regulation_ref: str
    subject_gated: bool = False
    declared_purpose_used: bool = False


@dataclass(frozen=True)
class _ProhibitedMatch:
    matched_signals: tuple[str, ...]
    entry_title: str
    regulation_ref: str


def _normalize_purpose(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def _purpose_suggests_area(declared_purpose: str) -> int | None:
    """Map manifest declared purpose to likely Annex III area."""
    purpose = _normalize_purpose(declared_purpose)
    if not purpose:
        return None
    hints: list[tuple[tuple[str, ...], int]] = [
        (("credit", "loan", "lending", "creditworthiness", "insurance premium"), 5),
        (("recruit", "hiring", "employment", "worker", "resume", "candidate"), 4),
        (("biometric", "face", "facial", "emotion", "fingerprint"), 1),
        (("student", "grading", "exam", "education", "proctor"), 3),
        (("asylum", "visa", "border", "migration"), 7),
        (("police", "criminal", "law enforcement", "recidivism"), 6),
        (("court", "judicial", "legal outcome", "election", "voting"), 8),
        (("infrastructure", "grid", "water supply", "scada"), 2),
    ]
    for keywords, area in hints:
        if any(kw in purpose for kw in keywords):
            return area
    return None


def _find_annex_match(search: str, tokens: set[str]) -> _AnnexMatch | None:
    from opencomplai_core.scanner.detectors._signals import match_code_signal

    from opencomplai_ai.knowledge.annex_iii import ANNEX_III

    best: _AnnexMatch | None = None
    best_score = -1

    for entry in ANNEX_III:
        for sig in sorted(entry.code_signals, key=len, reverse=True):
            if match_code_signal(search, sig):
                score = 1000 + len(sig)
            else:
                continue
            if score > best_score:
                best_score = score
                best = _AnnexMatch(
                    area=entry.area,
                    art6_3=entry.art6_3_profiling,
                    matched_signals=(sig,),
                    entry_title=entry.title,
                    regulation_ref=f"Art. 6(2), Annex III pt.{entry.subpoint}",
                    subject_gated=entry.subject_gated,
                )
        for kw in sorted(entry.keywords, key=len, reverse=True):
            if kw in search:
                score = 50 + len(kw)
                if score > best_score:
                    best_score = score
                    best = _AnnexMatch(
                        area=entry.area,
                        art6_3=entry.art6_3_profiling,
                        matched_signals=(kw,),
                        entry_title=entry.title,
                        regulation_ref=f"Art. 6(2), Annex III pt.{entry.subpoint}",
                        subject_gated=entry.subject_gated,
                    )
    return best


def _match_annex_iii(
    text: str,
    declared_purpose: str = "",
    *,
    token: str = "",
) -> _AnnexMatch | None:
    from opencomplai_ai.knowledge.annex_iii import lookup_by_area

    search_texts = [token.lower()] if token else []
    search_texts.append(text.lower())

    for search in search_texts:
        if not search:
            continue
        tokens = set(re.split(r"[^a-z0-9_]", search))
        match = _find_annex_match(search, tokens)
        if match is not None:
            return match

    combined = f"{token} {text}".lower()
    ambiguous_verbs = ("score", "rank", "predict", "classify")
    if any(v in combined for v in ambiguous_verbs):
        area = _purpose_suggests_area(declared_purpose)
        if area is not None:
            entries = lookup_by_area(area)
            if entries:
                entry = entries[0]
                matched = next((v for v in ambiguous_verbs if v in combined), "score")
                return _AnnexMatch(
                    area=area,
                    art6_3=entry.art6_3_profiling,
                    matched_signals=(matched,),
                    entry_title=entry.title,
                    regulation_ref=f"Art. 6(2), Annex III area {area}",
                    subject_gated=entry.subject_gated,
                    declared_purpose_used=True,
                )

    return None


def _match_prohibited(text: str, *, token: str = "") -> _ProhibitedMatch | None:
    from opencomplai_core.scanner.detectors._signals import match_code_signal

    from opencomplai_ai.knowledge.prohibited import PROHIBITED

    for search in (token, text):
        if not search:
            continue
        search_lower = search.lower()
        for entry in PROHIBITED:
            for sig in entry.code_signals:
                if match_code_signal(search, sig):
                    return _ProhibitedMatch(
                        matched_signals=(sig,),
                        entry_title=entry.title,
                        regulation_ref=entry.article,
                    )
            for kw in entry.keywords:
                if kw in search_lower:
                    return _ProhibitedMatch(
                        matched_signals=(kw,),
                        entry_title=entry.title,
                        regulation_ref=entry.article,
                    )
    return None


def _match_limited_risk(text: str, *, token: str = "") -> list:
    from opencomplai_ai.knowledge.limited_risk import match_limited_risk

    combined = f"{token} {text}"
    return match_limited_risk(combined)


def _infer_autonomy(text: str) -> str:
    text_lower = text.lower()
    if any(
        t in text_lower for t in ("approve", "reject", "decide", "automat", "trigger")
    ):
        return "autonomous"
    if any(t in text_lower for t in ("recommend", "suggest", "advisory", "assist")):
        return "advisory"
    if any(t in text_lower for t in ("review", "confirm", "approve_human", "manual")):
        return "human_in_loop"
    return "advisory"


def _limited_match_signal(entry, token: str, snippet: str) -> str:
    combined = f"{token} {snippet}".lower()
    for sig in entry.code_signals:
        if sig in combined:
            return sig
    for kw in entry.keywords:
        if kw in combined:
            return kw
    return entry.trigger_type


class IntentClassifier:
    """Deterministic Annex III signal matcher for the codebert-onnx slot."""

    def __init__(self) -> None:
        from opencomplai_ai.downloader import ensure_model

        model_path = ensure_model("codebert-onnx")
        self._model_path = model_path
        self._session = None
        self._tokenizer = None

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
    ) -> IntentAnnotation | None:
        tok = token or snippet.split("\n")[0][:80]
        annex = _match_annex_iii(snippet, declared_purpose, token=tok)
        prohibited = _match_prohibited(snippet, token=tok)
        limited_entries = _match_limited_risk(snippet, token=tok)

        if prohibited is not None:
            autonomy = _infer_autonomy(snippet)
            obligations = derive_eu_obligations(
                autonomy,  # type: ignore[arg-type]
                "natural_person",
                "no",
                annex_iii_area=None,
            )
            from opencomplai_ai.rationale import build_flag_rationale

            ann = IntentAnnotation(
                annex_iii_area=None,
                art5_prohibited=True,
                art6_3_profiling=True,
                risk_tier="prohibited",
                ai_usage_type=ai_usage_type,
                decision_autonomy=autonomy,  # type: ignore[arg-type]
                subject_type="natural_person",
                consequential="no",
                eu_obligation=obligations,
                matched_signals=list(prohibited.matched_signals),
                gate_reason=gate_reason,
                knowledge_entry_title=prohibited.entry_title,
                regulation_ref=prohibited.regulation_ref,
                model_id="codebert-onnx",
                confidence=0.8,
            )
            rationale = build_flag_rationale(
                ann, gate_reason=gate_reason, declared_purpose=declared_purpose
            )
            return ann.model_copy(
                update={
                    "explanation": rationale.summary,
                    "needed_action": rationale.needed_action,
                }
            )

        if annex is not None:
            from opencomplai_ai.models import subject_looks_like_natural_person

            autonomy = _infer_autonomy(snippet)

            subject_is_person = None
            if annex.subject_gated:
                subject_is_person = subject_looks_like_natural_person(
                    f"{tok} {snippet} {declared_purpose}"
                )

            if annex.subject_gated and subject_is_person is False:
                # Positive evidence (portfolio/vendor/counterparty/... cue, no
                # person cue) that the scored subject is not a natural person —
                # this Annex III sub-point does not apply. Downgrade rather than
                # silently high-risk a product/entity scoring model.
                subject_type = "legal_entity"
                consequential = "no"
                risk_tier = "minimal"
                confidence = 0.6
            else:
                subject_type = "natural_person"
                consequential = "yes"
                risk_tier = "high_risk"
                confidence = 0.8

            obligations = derive_eu_obligations(
                autonomy,  # type: ignore[arg-type]
                subject_type,  # type: ignore[arg-type]
                consequential,  # type: ignore[arg-type]
                annex_iii_area=annex.area if risk_tier == "high_risk" else None,
            )
            from opencomplai_ai.rationale import build_flag_rationale

            ann = IntentAnnotation(
                annex_iii_area=annex.area if risk_tier == "high_risk" else None,
                art5_prohibited=False,
                art6_3_profiling=annex.art6_3 if risk_tier == "high_risk" else False,
                risk_tier=risk_tier,  # type: ignore[arg-type]
                ai_usage_type=ai_usage_type,
                decision_autonomy=autonomy,  # type: ignore[arg-type]
                subject_type=subject_type,  # type: ignore[arg-type]
                consequential=consequential,  # type: ignore[arg-type]
                eu_obligation=obligations,
                matched_signals=list(annex.matched_signals),
                gate_reason=gate_reason,
                knowledge_entry_title=annex.entry_title,
                regulation_ref=annex.regulation_ref,
                declared_purpose_used=annex.declared_purpose_used,
                model_id="codebert-onnx",
                confidence=confidence,
            )
            if risk_tier == "minimal":
                ann = ann.model_copy(
                    update={
                        "explanation": (
                            f'Matched "{annex.entry_title}" vocabulary but the '
                            "scored subject appears to be a product, portfolio, "
                            "or commercial entity, not a natural person — "
                            "Annex III does not apply to this use. Re-check if "
                            "the code actually scores an individual."
                        ),
                        "needed_action": (
                            "No Annex III action required as classified. If this "
                            "model's output does affect a natural person "
                            "(e.g. feeds into a consumer decision), update the "
                            "code or declared_purpose to make that explicit so "
                            "the scanner can re-classify it correctly."
                        ),
                    }
                )
                return ann
            rationale = build_flag_rationale(
                ann, gate_reason=gate_reason, declared_purpose=declared_purpose
            )
            return ann.model_copy(
                update={
                    "explanation": rationale.summary,
                    "needed_action": rationale.needed_action,
                }
            )

        if limited_entries:
            entry = limited_entries[0]
            signal = _limited_match_signal(entry, tok, snippet)
            from opencomplai_ai.rationale import build_flag_rationale

            ann = IntentAnnotation(
                decision_autonomy="display_only",
                subject_type="natural_person",
                consequential="no",
                risk_tier="limited_risk",
                ai_usage_type=ai_usage_type,
                eu_obligation=[entry.obligation],
                matched_signals=[signal],
                gate_reason=gate_reason,
                knowledge_entry_title=entry.title,
                regulation_ref=entry.article,
                model_id="codebert-onnx",
                confidence=0.75,
            )
            rationale = build_flag_rationale(
                ann, gate_reason=gate_reason, declared_purpose=declared_purpose
            )
            return ann.model_copy(
                update={
                    "explanation": rationale.summary,
                    "needed_action": rationale.needed_action,
                }
            )

        if legacy:
            return IntentAnnotation(
                decision_autonomy="display_only",
                subject_type="system",
                consequential="no",
                risk_tier="minimal",
                ai_usage_type=ai_usage_type,
                eu_obligation=["Art.50 transparency disclosure if user-facing"],
                model_id="codebert-onnx",
                confidence=0.5,
            )
        return None
