"""
Rule registry and base rule interface.

Rules are deterministic: the same input always produces the same RuleResult.
The RULE_REGISTRY list is the authoritative set of rules evaluated by the engine.
Add new rules by subclassing BaseRule and appending to RULE_REGISTRY.

Phase 10 adds:
  - AnnexIIIClassifierRule (REQ-RISK-001)
  - ProfilingDetectionRule (REQ-RISK-002)
  - SubstantialModificationRule (REQ-RISK-003)
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod

from opencomplai_core.models import AssessmentInput, RuleResult


def normalize_text(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace for substring matching."""
    lowered = text.lower()
    cleaned = re.sub(r"[^\w\s]", " ", lowered, flags=re.UNICODE)
    return re.sub(r"\s+", " ", cleaned).strip()


class BaseRule(ABC):
    """Base class for all assessment rules."""

    @property
    @abstractmethod
    def rule_id(self) -> str:
        """Unique rule identifier, e.g. EU_AIA_ART6_HIGH_RISK."""
        ...

    @property
    @abstractmethod
    def rule_name(self) -> str:
        """Human-readable rule name."""
        ...

    @property
    @abstractmethod
    def reference(self) -> str:
        """EU AI Act article or clause reference."""
        ...

    @abstractmethod
    def evaluate(self, input: AssessmentInput) -> RuleResult:
        """Evaluate the rule against the given input and return a RuleResult."""
        ...


_PACK_AREA_NAME_REMAP: dict[str, str] = {
    "biometrics": "biometric",
    "justice_democracy": "justice",
}


def _keyword_variants(keyword: str) -> list[str]:
    """Derive matchable forms from a pack keyword (suffix-stripped, pack-sourced)."""
    variants: list[str] = [keyword]
    lower = keyword.lower()
    for sfx in (" ai", " system", " algorithm", " model"):
        if lower.endswith(sfx):
            variants.append(lower[: -len(sfx)].strip())
    return variants


_PACK_TOKEN_DENYLIST: frozenset[str] = frozenset(
    {
        "support",
        "system",
        "systems",
        "model",
        "models",
        "engine",
        "online",
        "detection",
        "filtering",
        "monitoring",
        "management",
        "application",
        "applications",
        "assessment",
        "evaluation",
        "prediction",
        "analysis",
        "control",
        "document",
        "network",
        "service",
        "services",
        "automated",
        "learning",
        "student",
        "worker",
        "employee",
        "personal",
        "public",
        "remote",
        "digital",
        "decision",
        "decisions",
        "influence",
        "influencing",
        "materially",
        "process",
        "outcome",
        "outcomes",
        "reliability",
        "credibility",
        "verification",
        "eligibility",
        "forecasting",
        "recommendation",
        "captioning",
        "accessibility",
        "customer",
        "retail",
        "weather",
        "detect",
        "filter",
        "access",
        "screen",
        "score",
        "predict",
        "monitor",
        "rank",
        "match",
        "verify",
        "check",
        "classify",
    }
)


def _expand_pack_phrase(phrase: str) -> list[str]:
    """Expand a pack phrase into matchable forms (full phrase, suffix-stripped, tokens)."""
    normalized = normalize_text(phrase.replace("_", " "))
    expanded: list[str] = [normalized]
    expanded.extend(_keyword_variants(normalized))
    words = normalized.split()
    if len(words) >= 2:
        for i in range(len(words) - 1):
            a, b = words[i], words[i + 1]
            if (
                len(a) >= 4
                and len(b) >= 4
                and a not in _PACK_TOKEN_DENYLIST
                and b not in _PACK_TOKEN_DENYLIST
            ):
                expanded.append(f"{a} {b}")
    for word in words:
        if len(word) >= 6 and word not in _PACK_TOKEN_DENYLIST:
            expanded.append(word)
    return expanded


def _build_annex_iii_categories() -> dict[str, frozenset[str]]:
    """Build Annex III keyword sets from the knowledge pack (single source of truth)."""
    result: dict[str, list[str]] = {}
    try:
        from opencomplai_ai.knowledge.annex_iii import ANNEX_III

        for entry in ANNEX_III:
            area_name = _PACK_AREA_NAME_REMAP.get(entry.area_name, entry.area_name)
            if area_name not in result:
                result[area_name] = []
            result[area_name].append(area_name.replace("_", " "))
            for phrase in (entry.title, *entry.keywords):
                result[area_name].extend(_expand_pack_phrase(phrase))
            for signal in entry.code_signals:
                normalized = normalize_text(signal.replace("_", " "))
                result[area_name].append(normalized)
                for word in normalized.split():
                    if len(word) >= 7 and word not in _PACK_TOKEN_DENYLIST:
                        result[area_name].append(word)
    except ImportError:
        pass
    return {k: frozenset(v) for k, v in result.items()}


def _build_subject_gated_keywords() -> frozenset[str]:
    """Keywords sourced from Annex III entries scoped to natural persons.

    Built per-entry (not per-area-name) because some area_names mix gated
    and non-gated sub-points — e.g. "essential_services" covers 5(b) credit
    scoring (natural persons only) and 5(d) emergency dispatch (not person-
    scoped). Gating must follow the matched keyword back to its specific
    sub-point, not the coarse area bucket used for display grouping.
    """
    result: list[str] = []
    try:
        from opencomplai_ai.knowledge.annex_iii import ANNEX_III

        for entry in ANNEX_III:
            if not entry.subject_gated:
                continue
            for phrase in (entry.title, *entry.keywords):
                result.extend(_expand_pack_phrase(phrase))
            for signal in entry.code_signals:
                normalized = normalize_text(signal.replace("_", " "))
                result.append(normalized)
                for word in normalized.split():
                    if len(word) >= 7 and word not in _PACK_TOKEN_DENYLIST:
                        result.append(word)
    except ImportError:
        pass
    return frozenset(result)


_NATURAL_PERSON_CUES: frozenset[str] = frozenset()
_PRODUCT_OR_ENTITY_CUES: frozenset[str] = frozenset()
try:
    from opencomplai_ai.models import NATURAL_PERSON_CUES as _NATURAL_PERSON_CUES
    from opencomplai_ai.models import PRODUCT_OR_ENTITY_CUES as _PRODUCT_OR_ENTITY_CUES
except ImportError:
    pass


def _subject_looks_non_person(use_case: str) -> bool:
    """True when the use case text has a product/entity cue and no person cue.

    Mirrors opencomplai_ai.models.subject_looks_like_natural_person but
    inlined against normalize_text's tokenization so rules.py does not take
    a hard dependency on opencomplai-ai beyond the optional import above.
    Ambiguous text (no cue either way) returns False — i.e. stays high-risk
    by default, since a missed flag is worse than an over-flagged one.
    """
    if not _PRODUCT_OR_ENTITY_CUES:
        return False
    tokens = set(use_case.split())
    if tokens & _NATURAL_PERSON_CUES:
        return False
    return bool(tokens & _PRODUCT_OR_ENTITY_CUES)


def _build_unacceptable_risk_signals() -> frozenset[str]:
    """Build Art. 5 prohibited signals from the knowledge pack."""
    signals: list[str] = []
    try:
        from opencomplai_ai.knowledge.prohibited import PROHIBITED

        for entry in PROHIBITED:
            signals.append(entry.title)
            signals.extend(entry.keywords)
    except ImportError:
        pass
    return frozenset(signals)


def _build_profiling_signals() -> frozenset[str]:
    """Build Art. 6(3) profiling signals from pack entries flagged art6_3_profiling."""
    signals: list[str] = []
    try:
        from opencomplai_ai.knowledge.annex_iii import ANNEX_III

        for entry in ANNEX_III:
            if entry.art6_3_profiling:
                for phrase in (entry.title, *entry.keywords):
                    signals.extend(_expand_pack_phrase(phrase))
    except ImportError:
        pass
    return frozenset(signals)


ANNEX_III_CATEGORIES: dict[str, frozenset[str]] = _build_annex_iii_categories()
UNACCEPTABLE_RISK_SIGNALS: frozenset[str] = _build_unacceptable_risk_signals()
SUBJECT_GATED_KEYWORDS: frozenset[str] = _build_subject_gated_keywords()


class AnnexIIIClassifierRule(BaseRule):
    rule_id = "EU_AIA_ART6_HIGH_RISK"
    rule_name = "High-Risk System Classification (Article 6 / Annex III)"
    reference = "EU AI Act, Article 6, Annex III"

    def evaluate(self, input: AssessmentInput) -> RuleResult:
        use_case = normalize_text(input.model.use_case)
        matched_categories: list[str] = []
        gated_only: list[str] = []
        subject_non_person = _subject_looks_non_person(use_case)

        for category, keywords in ANNEX_III_CATEGORIES.items():
            matched_kw = [kw for kw in keywords if normalize_text(kw) in use_case]
            if not matched_kw:
                continue
            if subject_non_person and all(
                normalize_text(kw) in SUBJECT_GATED_KEYWORDS for kw in matched_kw
            ):
                # Every keyword that fired for this category came from a
                # natural-person-scoped sub-point, and the use case text has
                # a positive product/entity cue with no person cue (e.g.
                # "counterparty", "portfolio", "vendor"). Don't classify
                # product/service scoring as Annex III high-risk.
                gated_only.append(category)
                continue
            matched_categories.append(category)

        is_high_risk = len(matched_categories) > 0

        rationale = (
            f"Use case '{input.model.use_case}' matches Annex III categories: "
            f"{', '.join(matched_categories)}."
            if is_high_risk
            else f"Use case '{input.model.use_case}' does not match any "
            f"Annex III high-risk categories."
        )
        if gated_only:
            rationale += (
                f" (Matched natural-person-scoped vocabulary for {', '.join(gated_only)} "
                "but the use case describes scoring a product, portfolio, or "
                "commercial entity, not a natural person — Annex III does not apply.)"
            )

        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            passed=not is_high_risk,
            rationale=rationale,
            reference=self.reference,
        )


class UnacceptableRiskRule(BaseRule):
    rule_id = "EU_AIA_ART5_UNACCEPTABLE"
    rule_name = "Prohibited AI Practice Detection (Article 5)"
    reference = "EU AI Act, Article 5"

    def evaluate(self, input: AssessmentInput) -> RuleResult:
        use_case = normalize_text(input.model.use_case)
        matched = [
            s for s in UNACCEPTABLE_RISK_SIGNALS if normalize_text(s) in use_case
        ]
        is_unacceptable = len(matched) > 0

        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            passed=not is_unacceptable,
            rationale=(
                f"Use case '{input.model.use_case}' contains prohibited practice signals: "
                f"{', '.join(matched)}. This use case is prohibited under EU AI Act Article 5."
                if is_unacceptable
                else f"No prohibited practice signals detected in '{input.model.use_case}'."
            ),
            reference=self.reference,
        )


class ProfilingDetectionRule(BaseRule):
    rule_id = "EU_AIA_ART6_PROFILING"
    rule_name = "Profiling Detection — Force High-Risk (Article 6(3))"
    reference = "EU AI Act, Article 6(3), Recital 34"

    PROFILING_SIGNALS: frozenset[str] = _build_profiling_signals()

    def evaluate(self, input: AssessmentInput) -> RuleResult:
        if input.answers.get("profiling_detected") is True:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                passed=False,
                rationale=(
                    "Profiling explicitly declared in assessment answers. "
                    "System is classified as high-risk per Article 6(3)."
                ),
                reference=self.reference,
            )

        use_case = normalize_text(input.model.use_case)
        matched = [s for s in self.PROFILING_SIGNALS if normalize_text(s) in use_case]

        if matched and _subject_looks_non_person(use_case):
            # Art. 6(3) / Recital 34 profiling is defined as profiling of
            # *natural persons*. A product/entity cue with no person cue
            # (e.g. "portfolio", "counterparty") means these signals describe
            # scoring a non-person subject — Art. 6(3) does not force
            # high-risk here.
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                passed=True,
                rationale=(
                    f"Profiling vocabulary detected ({', '.join(matched)}) but the use "
                    "case describes scoring a product, portfolio, or commercial entity, "
                    "not a natural person — Article 6(3) profiling does not apply."
                ),
                reference=self.reference,
            )

        if matched:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                passed=False,
                rationale=(
                    f"Profiling signals detected in use case: {', '.join(matched)}. "
                    f"System is classified as high-risk per Article 6(3)."
                ),
                reference=self.reference,
            )

        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            passed=True,
            rationale="No profiling signals detected in use case or answers.",
            reference=self.reference,
        )


class SubstantialModificationRule(BaseRule):
    rule_id = "EU_AIA_ART25_MODIFICATION_TRAP"
    rule_name = "Substantial Modification Trap (Article 25 / Article 3(23))"
    reference = "EU AI Act, Article 25, Article 3(23), Recital 66"

    def evaluate(self, input: AssessmentInput) -> RuleResult:
        is_modified = input.answers.get("substantial_modification", False)

        if is_modified:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                passed=False,
                rationale=(
                    "Substantial modification detected. A new conformity assessment is required "
                    "before this system can be re-deployed. Deployment is frozen until HITL "
                    "approval is obtained. (TRAP_DETECTED — exit code 4)"
                ),
                reference=self.reference,
            )

        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            passed=True,
            rationale="No substantial modification declared in assessment answers.",
            reference=self.reference,
        )


RULE_REGISTRY: list[BaseRule] = [
    UnacceptableRiskRule(),
    AnnexIIIClassifierRule(),
    ProfilingDetectionRule(),
    SubstantialModificationRule(),
]

# Monotonically incrementing version for the rule set.
# Bump when any rule logic, keyword list, or reference changes.
# Every generated dossier references this version for Annex IV traceability
# per EU AI Act Art. 11 and post-market monitoring (Art. 72).
RULE_SET_VERSION = "1.2.0"
