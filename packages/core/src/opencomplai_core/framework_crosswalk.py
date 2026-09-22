"""Framework crosswalk (EU AI Act article -> ISO/IEC 42001:2023 / NIST AI RMF).

Loads and validates `data/framework_crosswalk.json`, mirroring
`harmonised_standards.get_catalog()`'s fail-loud convention: a malformed or
missing crosswalk raises `ValueError` rather than silently degrading to an
empty result. Consumed by `control_catalog` (to attach per-article ISO/NIST
references), `opencomplai gaps`'s "Mapped" column, and the dossier
generator's Section 5/7 crosswalk citations.

Every row is a MAPPING, not a computed verdict: it says "this article
corresponds to that clause/subcategory", with a source and a confidence
label. Only `EU_AI_ACT` gets a deterministic pass/gap verdict from
opencomplai today (D-3, `PLAN/CLOSE-P1/00-OVERVIEW.md`). Every row is also
`needs_founder_review=true`: this is compliance-facing content that has not
been confirmed by a human reviewer. See the data file's `_meta` block for
research date, confidence definitions, and articles deliberately left
uncovered.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_DATA_PATH = Path(__file__).resolve().parent / "data" / "framework_crosswalk.json"

_VALID_CONFIDENCES = {"low", "medium", "high"}


@dataclass(frozen=True)
class CrosswalkEntry:
    eu_ai_act_article: str
    iso_42001_clause: str
    iso_42001_annex_a_control: str | None
    nist_ai_rmf_subcategory: str
    source: str
    confidence: str
    needs_founder_review: bool


@lru_cache(maxsize=1)
def get_crosswalk() -> dict[str, CrosswalkEntry]:
    """Return the validated framework crosswalk, keyed by EU AI Act article.

    Fails loud (raises ValueError) on a missing file, invalid JSON, or any
    row missing/mis-typing a required field — never returns a silently
    empty or partial crosswalk. Not every `control_catalog` article has a
    row (see the data file's `_meta.not_covered`); callers must treat a
    missing key as "no mapping yet", not an error.
    """
    try:
        raw = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(
            f"framework_crosswalk: cannot read {_DATA_PATH}: {exc}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"framework_crosswalk: invalid JSON in {_DATA_PATH}: {exc}"
        ) from exc

    rows = raw.get("rows") if isinstance(raw, dict) else None
    if not isinstance(rows, list) or not rows:
        raise ValueError("framework_crosswalk: 'rows' is missing or empty")

    crosswalk: dict[str, CrosswalkEntry] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"framework_crosswalk: row is not an object: {row!r}")

        article = row.get("eu_ai_act_article")
        if not isinstance(article, str) or not article.strip():
            raise ValueError(
                f"framework_crosswalk: malformed eu_ai_act_article {article!r}"
            )
        if article in crosswalk:
            raise ValueError(f"framework_crosswalk: duplicate row for {article!r}")

        iso_clause = row.get("iso_42001_clause")
        if not isinstance(iso_clause, str) or not iso_clause.strip():
            raise ValueError(
                f"framework_crosswalk: entry {article!r} has an empty iso_42001_clause"
            )

        annex_a = row.get("iso_42001_annex_a_control")
        if annex_a is not None and (
            not isinstance(annex_a, str) or not annex_a.strip()
        ):
            raise ValueError(
                f"framework_crosswalk: entry {article!r} has an invalid "
                f"iso_42001_annex_a_control {annex_a!r}"
            )

        nist_subcategory = row.get("nist_ai_rmf_subcategory")
        if not isinstance(nist_subcategory, str) or not nist_subcategory.strip():
            raise ValueError(
                f"framework_crosswalk: entry {article!r} has an empty "
                "nist_ai_rmf_subcategory"
            )

        source = row.get("source")
        if not isinstance(source, str) or not source.strip():
            raise ValueError(
                f"framework_crosswalk: entry {article!r} has an empty source"
            )

        confidence = row.get("confidence")
        if confidence not in _VALID_CONFIDENCES:
            raise ValueError(
                f"framework_crosswalk: entry {article!r} has invalid confidence "
                f"{confidence!r} (must be one of {sorted(_VALID_CONFIDENCES)})"
            )

        # Mandatory per epic CP-5: nothing in this crosswalk has been
        # confirmed by a human reviewer yet, so no row may claim otherwise.
        if row.get("needs_founder_review") is not True:
            raise ValueError(
                f"framework_crosswalk: entry {article!r} must have "
                "needs_founder_review=true"
            )

        crosswalk[article] = CrosswalkEntry(
            eu_ai_act_article=article,
            iso_42001_clause=iso_clause,
            iso_42001_annex_a_control=annex_a,
            nist_ai_rmf_subcategory=nist_subcategory,
            source=source,
            confidence=confidence,
            needs_founder_review=True,
        )

    return crosswalk
