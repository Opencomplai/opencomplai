# CI connector sub-package (C1.5)

from __future__ import annotations

from collections import Counter

from opencomplai_core.frameworks import EU_AI_ACT, framework_of


def summarize_failed_controls(ids: list[str], limit: int | None = None) -> str:
    """`failed_controls` for a CI message: the EU AI Act ids (the first
    `limit` of them), then "<FW>: N requirement(s)" per gated framework.

    Without prefixed ids this is the plain comma-joined list it always was.
    """
    ids = [str(c) for c in ids]
    eu = [c for c in ids if framework_of(c) == EU_AI_ACT]
    others = Counter(framework_of(c) for c in ids if framework_of(c) != EU_AI_ACT)
    return ", ".join(
        [*eu[:limit], *(f"{fw}: {n} requirement(s)" for fw, n in others.items())]
    )
