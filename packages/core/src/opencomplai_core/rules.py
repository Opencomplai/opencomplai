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
from collections.abc import Iterable

from opencomplai_core.knowledge.subject_cues import (
    NATURAL_PERSON_CUES as _NATURAL_PERSON_CUES,
)
from opencomplai_core.knowledge.subject_cues import (
    PRODUCT_OR_ENTITY_CUES as _PRODUCT_OR_ENTITY_CUES,
)
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
        # Generic engineering/process vocabulary. These are long enough to
        # clear _SOLO_TOKEN_MIN_LEN but carry no Annex III signal, so they are
        # excluded from expansion rather than relied on to be short.
        "performance",
        "testing",
        "sorting",
        "pipeline",
        "pipelines",
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
    """Expand a pack phrase into matchable forms (full phrase, suffix-stripped, bigrams, terms).

    Bare single words ARE emitted, but they never fire a category on their
    own — `_match_pack_keywords` requires two distinct ones to co-occur.
    Dropping them entirely (the previous approach) silently lost the
    distinctive Annex III vocabulary that only ever appears as one word:
    "recidivism", "microtargeting", "ethnicity". Suppressing the vocabulary
    is a false-negative risk, which for a compliance gate is worse than the
    false positives it was meant to avoid; the co-occurrence requirement is
    what makes restoring it safe.
    """
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


def _matches_keyword(keyword: str, use_case: str) -> bool:
    """True when `keyword` occurs in `use_case` on whole-token boundaries.

    Plain substring matching let short pack tokens fire inside unrelated
    words — "fer" (facial emotion recognition) matched "in-FER-ence" and
    "cad" matched "cas-CAD-e" — classifying ordinary engineering work as
    high-risk. Both sides are already normalize_text'd, so anchoring on
    word characters is sufficient.

    Kept as the single-keyword reference implementation, used directly by
    the tests pinning matching semantics; _CompiledKeywordMatcher below is
    the whole-set equivalent used by the rule classes, bounded by text
    length rather than by the number of keywords in the set.
    """
    kw = normalize_text(keyword)
    if not kw:
        return False
    # A trailing plural is still the same term: the pack stores "applicant"
    # and "examination" while use cases say "applicants" and "examinations".
    # Substring matching used to absorb this for free; word boundaries do not.
    return re.search(rf"(?<!\w){re.escape(kw)}(?:e?s)?(?!\w)", use_case) is not None


class _CompiledKeywordMatcher:
    """Precomputed matcher for a fixed keyword set (DOS-LIMITS).

    AnnexIIIClassifierRule/UnacceptableRiskRule/ProfilingDetectionRule each
    used to test every keyword in their set against `use_case` with its own
    `re.search` call — O(keywords * len(use_case)) per request. This tokenizes
    `use_case` into words once and does a dict lookup per word-n-gram, giving
    the same match set in O(len(use_case) * max_phrase_words) instead — a
    small constant (longest pack phrase is 11 words), not the keyword count.

    Matching semantics are byte-for-byte those of `_matches_keyword` called
    once per keyword: every keyword is tested independently against the full
    text, word-boundary anchored, with an optional trailing `e?s` on the
    pluralizable form. This independence matters — "credit", "scoring", and
    "credit scoring" can all match the same span of text simultaneously, so a
    greedy longest-match single-pass regex scan (which finds non-overlapping
    matches) would silently drop the shorter two. Building every contiguous
    word n-gram at each position and checking it against a dict avoids that:
    each n-gram length is checked independently, exactly like the old
    per-keyword loop, just without re-scanning the text once per keyword.
    """

    def __init__(self, keywords: Iterable[str]) -> None:
        by_normalized: dict[str, list[str]] = {}
        max_words = 1
        for kw in keywords:
            norm = normalize_text(kw)
            if not norm:
                continue
            by_normalized.setdefault(norm, []).append(kw)
            max_words = max(max_words, len(norm.split()))
        self._by_normalized = by_normalized
        self._max_words = max_words

    def find_matching_keywords(self, use_case: str) -> list[str]:
        """Original keyword strings whose normalized form matched `use_case`."""
        if not self._by_normalized:
            return []
        words = use_case.split()
        found_norms: set[str] = set()
        for start in range(len(words)):
            for length in range(1, min(self._max_words, len(words) - start) + 1):
                candidate = " ".join(words[start : start + length])
                # Checked independently, not elif/continue: the pack can
                # contain both a stem and its own explicit plural as distinct
                # keyword entries (e.g. "benefit" and "benefits"), and the old
                # per-keyword loop matched both against one occurrence of
                # "benefits" in the text — one testing the stem plus its
                # optional suffix, the other matching the plural verbatim.
                if candidate in self._by_normalized:
                    found_norms.add(candidate)
                for suffix in ("es", "s"):
                    stem = candidate[: -len(suffix)]
                    if candidate.endswith(suffix) and stem in self._by_normalized:
                        found_norms.add(stem)
                        break
        matched: list[str] = []
        for norm in found_norms:
            matched.extend(self._by_normalized[norm])
        return matched


def _match_pack_keywords(
    keywords: Iterable[str] | _CompiledKeywordMatcher, use_case: str
) -> list[str]:
    """Keywords firing for `use_case`, subject to the co-occurrence requirement.

    A multi-word phrase carries its own context and fires alone. A bare
    single token does not: "education" alone matches "self-serve education
    videos about our API" and "migration" alone matches "cloud migration
    planning tool", neither of which is an Annex III system. Requiring two
    distinct single tokens is the signal that they describe one subject
    rather than coincidental words.

    `keywords` accepts a pre-built _CompiledKeywordMatcher (the hot path —
    AnnexIIIClassifierRule/ProfilingDetectionRule pass their module-level
    precompiled matchers so the alternation regex is built once, not per
    request) or a plain iterable of keyword strings (builds one on the fly;
    used by callers exercising matching semantics directly, e.g. tests).

    Returns [] when the category does not fire, so callers can treat the
    result as a boolean.
    """
    matcher = (
        keywords
        if isinstance(keywords, _CompiledKeywordMatcher)
        else _CompiledKeywordMatcher(keywords)
    )
    matched = matcher.find_matching_keywords(use_case)
    has_phrase = any(" " in normalize_text(kw) for kw in matched)
    singles = {normalize_text(kw) for kw in matched if " " not in normalize_text(kw)}
    # Token length is deliberately NOT used to let a single word fire alone:
    # "recidivism" (10) and "inference" (9) are indistinguishable by length,
    # so a length rule readmits exactly the substring-era false positives.
    # Distinctive terms earn their match through a partner token instead,
    # which is why the pack carries the surrounding vocabulary.
    if has_phrase or len(singles) >= 2:
        return matched
    return []


class KnowledgePackError(RuntimeError):
    """Raised when the bundled EU AI Act knowledge pack yields an empty ruleset.

    An empty classification set is never legitimate: it would silently pass
    every use case as non-prohibited and non-high-risk with zero signal.
    """


def _build_annex_iii_categories() -> dict[str, frozenset[str]]:
    """Build Annex III keyword sets from the bundled knowledge pack (single source of truth)."""
    from opencomplai_core.knowledge.annex_iii import ANNEX_III

    result: dict[str, list[str]] = {}
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
    built = {k: frozenset(v) for k, v in result.items()}
    if not built or any(not v for v in built.values()):
        raise KnowledgePackError(
            "Annex III knowledge pack produced an empty ruleset; refusing to "
            "silently classify every use case as non-high-risk."
        )
    return built


def _build_subject_gated_keywords() -> frozenset[str]:
    """Keywords sourced from Annex III entries scoped to natural persons.

    Built per-entry (not per-area-name) because some area_names mix gated
    and non-gated sub-points — e.g. "essential_services" covers 5(b) credit
    scoring (natural persons only) and 5(d) emergency dispatch (not person-
    scoped). Gating must follow the matched keyword back to its specific
    sub-point, not the coarse area bucket used for display grouping.
    """
    from opencomplai_core.knowledge.annex_iii import ANNEX_III

    result: list[str] = []
    for entry in ANNEX_III:
        if not entry.subject_gated:
            continue
        for phrase in (entry.title, *entry.keywords):
            result.extend(_expand_pack_phrase(phrase))
        for signal in entry.code_signals:
            normalized = normalize_text(signal.replace("_", " "))
            result.append(normalized)
    built = frozenset(result)
    if not built:
        raise KnowledgePackError(
            "Subject-gated Annex III keyword set is empty; refusing to "
            "silently disable the person-scoping check."
        )
    return built


def _subject_looks_non_person(use_case: str) -> bool:
    """True when the use case text has a product/entity cue and no person cue.

    Mirrors opencomplai_ai.models.subject_looks_like_natural_person but
    inlined against normalize_text's tokenization. Both cue sets are bundled
    in core (opencomplai_core.knowledge.subject_cues), so this holds
    identically with or without the optional opencomplai-ai plugin
    installed. Ambiguous text (no cue either way) returns False — i.e.
    stays high-risk by default, since a missed flag is worse than an
    over-flagged one.
    """
    tokens = set(use_case.split())
    if tokens & _NATURAL_PERSON_CUES:
        return False
    return bool(tokens & _PRODUCT_OR_ENTITY_CUES)


def _build_unacceptable_risk_signals() -> frozenset[str]:
    """Build Art. 5 prohibited signals from the bundled knowledge pack."""
    from opencomplai_core.knowledge.prohibited import PROHIBITED

    signals: list[str] = []
    for entry in PROHIBITED:
        signals.append(entry.title)
        signals.extend(entry.keywords)
    built = frozenset(signals)
    if not built:
        raise KnowledgePackError(
            "Art. 5 prohibited-practice knowledge pack is empty; refusing to "
            "silently classify every use case as non-prohibited."
        )
    return built


def _build_profiling_signals() -> frozenset[str]:
    """Build Art. 6(3) profiling signals from bundled pack entries flagged art6_3_profiling."""
    from opencomplai_core.knowledge.annex_iii import ANNEX_III

    signals: list[str] = []
    for entry in ANNEX_III:
        if entry.art6_3_profiling:
            for phrase in (entry.title, *entry.keywords):
                signals.extend(_expand_pack_phrase(phrase))
    built = frozenset(signals)
    if not built:
        raise KnowledgePackError(
            "Art. 6(3) profiling knowledge pack is empty; refusing to "
            "silently disable the profiling override."
        )
    return built


ANNEX_III_CATEGORIES: dict[str, frozenset[str]] = _build_annex_iii_categories()
UNACCEPTABLE_RISK_SIGNALS: frozenset[str] = _build_unacceptable_risk_signals()
SUBJECT_GATED_KEYWORDS: frozenset[str] = _build_subject_gated_keywords()

# Compiled once at import time (DOS-LIMITS) — one alternation-regex scan per
# rule per request instead of one re.search per keyword. Rebuilding these per
# request would reintroduce the O(keywords) construction cost this exists to
# remove, so they are module-level singletons keyed to the constants above.
_ANNEX_III_MATCHERS: dict[str, _CompiledKeywordMatcher] = {
    category: _CompiledKeywordMatcher(keywords)
    for category, keywords in ANNEX_III_CATEGORIES.items()
}
_UNACCEPTABLE_RISK_MATCHER = _CompiledKeywordMatcher(UNACCEPTABLE_RISK_SIGNALS)


class AnnexIIIClassifierRule(BaseRule):
    rule_id = "EU_AIA_ART6_HIGH_RISK"
    rule_name = "High-Risk System Classification (Article 6 / Annex III)"
    reference = "EU AI Act, Article 6, Annex III"

    def evaluate(self, input: AssessmentInput) -> RuleResult:
        use_case = normalize_text(input.model.use_case)
        matched_categories: list[str] = []
        gated_only: list[str] = []
        subject_non_person = _subject_looks_non_person(use_case)

        for category in ANNEX_III_CATEGORIES:
            matched_kw = _match_pack_keywords(_ANNEX_III_MATCHERS[category], use_case)
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
        # No co-occurrence requirement here: Art. 5 signals are curated
        # prohibited-practice phrases, not expanded vocabulary, and a single
        # match should surface. Word-boundary matching still applies.
        matched = _UNACCEPTABLE_RISK_MATCHER.find_matching_keywords(use_case)
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
    _MATCHER: _CompiledKeywordMatcher = _CompiledKeywordMatcher(PROFILING_SIGNALS)

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
        matched = _match_pack_keywords(self._MATCHER, use_case)

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
RULE_SET_VERSION = "1.5.0"
