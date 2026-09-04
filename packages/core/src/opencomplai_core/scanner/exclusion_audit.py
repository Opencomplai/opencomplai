"""
`.ocignore` exclusion auditing (SCAN-OCIGNORE, finding 84).

`.ocignore` is fully repo-owned with no restriction on what it may exclude, and
directory-level excludes were pruned **with no trace at all** — the file-level
branch recorded a skip, the directory branch simply `continue`d. So the audited
party could exclude the exact source tree under audit and produce a clean
`severity=NONE` report that is **byte-identical** to one from a genuinely
AI-free repository.

`config_hash` already makes the config tamper-*evident* — you can prove the
`.ocignore` changed. It does not make an exclusion *suspicious*, which is the
gap this closes. Two independent signals:

1. **Pre-flight (this module).** Flag exclusion patterns that name AI-related
   paths. This is a heuristic and is reported as such: the point is to put a
   human's attention on the exclusion, not to accuse anyone. A legitimate
   `vendor/` exclusion and a self-serving `src/ml/` exclusion look identical to
   a scanner, and only a reviewer can tell them apart.

2. **Baseline comparison.** An AI-related exclusion that is *newly added*
   relative to a baseline is a materially stronger signal than one that has
   always been there, because it is change correlated with an audit.

Neither signal blocks a scan. Both make an exclusion visible in the report, so
"nothing was found" and "we were told not to look there" stop being the same
report.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

#: Path fragments that suggest an exclusion covers AI/ML code. Matched against
#: the pattern text, case-insensitively, on word-ish boundaries so `mlx` does
#: not fire on `html` and `ai` does not fire on every word containing it.
_AI_PATH_HINTS = (
    "ai",
    "ml",
    "llm",
    "genai",
    "gen-ai",
    "model",
    "models",
    "inference",
    "embedding",
    "embeddings",
    "prompt",
    "prompts",
    "openai",
    "anthropic",
    "claude",
    "gpt",
    "gemini",
    "bedrock",
    "langchain",
    "llamaindex",
    "transformers",
    "huggingface",
    "vector",
    "rag",
    "agent",
    "agents",
    "classifier",
    "scoring",
    "biometric",
)

_HINT_RE = re.compile(
    r"(?<![a-z0-9])("
    + "|".join(re.escape(h) for h in _AI_PATH_HINTS)
    + r")(?![a-z0-9])",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ExclusionFlag:
    """One `.ocignore` pattern that warrants a look."""

    pattern: str
    #: Which hint fired, so a reviewer can judge the match rather than trust it.
    matched_hint: str
    #: True when this pattern is absent from the baseline — change correlated
    #: with an audit is a stronger signal than a long-standing exclusion.
    newly_added: bool = False

    def describe(self) -> str:
        prefix = "newly-added exclusion" if self.newly_added else "exclusion"
        return (
            f"{prefix} '{self.pattern}' matches AI-related hint '{self.matched_hint}'"
        )


@dataclass
class ExclusionAudit:
    flagged: list[ExclusionFlag] = field(default_factory=list)
    #: Directory prefixes pruned during the walk, recorded so the report can
    #: say what was not looked at. Previously discarded entirely.
    excluded_directories: list[str] = field(default_factory=list)

    @property
    def has_findings(self) -> bool:
        return bool(self.flagged)

    @property
    def newly_added(self) -> list[ExclusionFlag]:
        return [f for f in self.flagged if f.newly_added]

    def summary(self) -> list[str]:
        return [flag.describe() for flag in self.flagged]


def flag_ai_related_patterns(
    patterns: list[str], baseline_patterns: list[str] | None = None
) -> list[ExclusionFlag]:
    """
    Flag exclusion patterns that appear to cover AI-related paths.

    ``baseline_patterns`` is the previously-accepted set. Anything not in it is
    marked ``newly_added``. Passing ``None`` means "no baseline available", in
    which case nothing is marked new — an absent baseline must not be read as
    "everything is new", which would flood the report on a first scan and train
    reviewers to ignore it.
    """
    baseline = set(baseline_patterns) if baseline_patterns is not None else None
    flags: list[ExclusionFlag] = []

    for pattern in patterns:
        # Comments and negations are not exclusions. A negation (`!foo`) *adds*
        # coverage back, so flagging it would be exactly backwards.
        stripped = pattern.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("!"):
            continue

        match = _HINT_RE.search(stripped)
        if not match:
            continue

        flags.append(
            ExclusionFlag(
                pattern=stripped,
                matched_hint=match.group(1).lower(),
                newly_added=baseline is not None and stripped not in baseline,
            )
        )
    return flags


def audit_exclusions(
    patterns: list[str],
    excluded_directories: list[str] | None = None,
    baseline_patterns: list[str] | None = None,
) -> ExclusionAudit:
    return ExclusionAudit(
        flagged=flag_ai_related_patterns(patterns, baseline_patterns),
        excluded_directories=sorted(set(excluded_directories or [])),
    )


__all__ = [
    "ExclusionAudit",
    "ExclusionFlag",
    "audit_exclusions",
    "flag_ai_related_patterns",
]
