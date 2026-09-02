"""
Secret and PII redaction for snippets leaving the process (AI-EGRESS).

The ``saas`` intent backend POSTs source snippets to a remote API. Those
snippets are taken from the user's own repository, so they can carry API keys,
private keys, connection strings, and PII sitting in fixtures or test data —
previously sent verbatim (finding 75). This module scrubs them first.

**What this is and is not.** Pattern-based redaction catches the shapes secrets
usually take; it cannot catch a credential that looks like ordinary prose, and
it is not a substitute for keeping secrets out of source control. It is a
mitigation, not a guarantee, and callers must not describe it as one. The
honest control for a regulated deployment is ``OPENCOMPLAI_OFFLINE=1`` (see
``egress.py``), which sends nothing at all.

**Bias.** Patterns are deliberately tuned to over-redact rather than
under-redact. A false positive costs a little classification accuracy on one
snippet; a false negative leaks a live credential to a third party. Where a
pattern could plausibly go either way, it redacts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

#: Placeholder written in place of a match. The kind is kept so a reader (and
#: the remote classifier) can still tell a key apart from an email — replacing
#: everything with one opaque token would destroy the structural signal the
#: classifier depends on.
_PLACEHOLDER = "[REDACTED:{kind}]"


def _luhn_ok(digits: str) -> bool:
    """Luhn checksum, used to keep long ordinary digit runs from being flagged."""
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


@dataclass(frozen=True)
class _Rule:
    kind: str
    pattern: re.Pattern[str]
    #: When set, the match is redacted only if this returns True. Used for
    #: checksum-gated rules where the shape alone is too weak.
    guard: object = None
    #: When set, only this capture group is replaced, so surrounding context
    #: (e.g. the variable name that gives the classifier its signal) survives.
    group: int = 0


# Ordering matters: earlier rules win, so specific shapes are listed before the
# generic assignment catch-all that would otherwise swallow them.
_RULES: tuple[_Rule, ...] = (
    # Whole PEM blocks, including the body — matching only the header would
    # leave the actual key material in the payload.
    _Rule(
        "private_key",
        re.compile(
            r"-----BEGIN[ A-Z]*PRIVATE KEY-----.*?-----END[ A-Z]*PRIVATE KEY-----",
            re.DOTALL,
        ),
    ),
    _Rule("aws_access_key_id", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    _Rule("github_token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}\b")),
    _Rule("github_token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{22,}\b")),
    _Rule("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    _Rule("stripe_key", re.compile(r"\b(?:sk|pk|rk)_(?:live|test)_[A-Za-z0-9]{10,}\b")),
    _Rule("openai_key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b")),
    _Rule("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    _Rule(
        "jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+")
    ),
    # Credentials embedded in a URL. Only the userinfo is replaced so the
    # scheme and host still tell the classifier what kind of service it is.
    _Rule(
        "connection_string_credentials",
        re.compile(r"(?<=://)([^/\s:@]+:[^/\s:@]+)(?=@)"),
        group=1,
    ),
    # Generic secret-ish assignment: `api_key = "..."`, `PASSWORD: '...'`,
    # `token=...`. Only the value is replaced, so the key name survives.
    _Rule(
        "secret_assignment",
        re.compile(
            r"""(?ix)
            \b(?:api[_-]?key|secret[_-]?key|access[_-]?token|auth[_-]?token
               |client[_-]?secret|private[_-]?key|passwd|password|secret|token)
            \b \s* [:=] \s*
            (["'][^"'\n]{4,}["'] | [^\s"',;)]{8,})
            """
        ),
        group=1,
    ),
    _Rule("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    _Rule(
        "us_ssn", re.compile(r"\b(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b")
    ),
    _Rule(
        "credit_card",
        re.compile(r"\b(?:\d[ -]?){12,18}\d\b"),
        guard=lambda m: _luhn_ok(re.sub(r"\D", "", m.group(0))),
    ),
)


@dataclass
class RedactionResult:
    text: str
    #: kind -> number of matches replaced. Empty when nothing was found.
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def redacted(self) -> bool:
        return bool(self.counts)

    def summary(self) -> str:
        """Human-readable one-liner, e.g. ``2 email, 1 aws_access_key_id``."""
        if not self.counts:
            return "nothing redacted"
        return ", ".join(
            f"{count} {kind}" for kind, count in sorted(self.counts.items())
        )


def redact(text: str) -> RedactionResult:
    """
    Replace secret- and PII-shaped substrings in ``text``.

    Rules are applied in order and each rule sees the output of the previous
    one, so an already-redacted span cannot be matched again — the placeholder
    contains no characters the later patterns accept as a secret body.
    """
    counts: dict[str, int] = {}
    result = text

    for rule in _RULES:
        replacement = _PLACEHOLDER.format(kind=rule.kind)

        def _sub(
            match: re.Match[str], rule: _Rule = rule, replacement: str = replacement
        ) -> str:
            if rule.guard is not None and not rule.guard(match):
                return match.group(0)
            counts[rule.kind] = counts.get(rule.kind, 0) + 1
            if rule.group == 0:
                return replacement
            # Preserve everything around the captured group.
            whole, group = match.group(0), match.group(rule.group)
            start = match.start(rule.group) - match.start(0)
            return whole[:start] + replacement + whole[start + len(group) :]

        result = rule.pattern.sub(_sub, result)

    return RedactionResult(text=result, counts=counts)


__all__ = ["RedactionResult", "redact"]
