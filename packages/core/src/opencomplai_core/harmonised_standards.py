"""Harmonised-standards catalogue (EU AI Act Art. 40 / CEN-CENELEC JTC 21).

Loads and validates `data/harmonised_standards.json`, mirroring
`control_catalog.get_catalog()`'s fail-loud convention: a malformed or
missing catalogue raises `ValueError` rather than silently degrading to an
empty result. Consumed by Annex IV Section 7 validation
(`services/doc-generator`'s `_build_section7`) to warn — never hard-fail —
when a provider-supplied standards entry doesn't match a known catalogue id.

Every row in the data file is `needs_founder_review=true`: this is
compliance-facing content sourced from live research, not a human-confirmed
legal determination. See the data file's `_meta` block for the research date
and status definitions.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_DATA_PATH = Path(__file__).resolve().parent / "data" / "harmonised_standards.json"

_VALID_STATUSES = {"harmonised", "published", "draft"}


@dataclass(frozen=True)
class HarmonisedStandardEntry:
    id: str
    title: str
    status: str
    source_url: str
    articles_covered: tuple[str, ...]
    needs_founder_review: bool


@lru_cache(maxsize=1)
def get_catalog() -> dict[str, HarmonisedStandardEntry]:
    """Return the validated harmonised-standards catalogue, keyed by id.

    Fails loud (raises ValueError) on a missing file, invalid JSON, or any
    row missing/mis-typing a required field — never returns a silently
    empty or partial catalogue.
    """
    try:
        raw = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(
            f"harmonised_standards: cannot read {_DATA_PATH}: {exc}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"harmonised_standards: invalid JSON in {_DATA_PATH}: {exc}"
        ) from exc

    rows = raw.get("standards") if isinstance(raw, dict) else None
    if not isinstance(rows, list) or not rows:
        raise ValueError("harmonised_standards: 'standards' is missing or empty")

    catalog: dict[str, HarmonisedStandardEntry] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"harmonised_standards: row is not an object: {row!r}")

        row_id = row.get("id")
        if not isinstance(row_id, str) or not row_id.strip():
            raise ValueError(f"harmonised_standards: malformed id {row_id!r}")
        if row_id in catalog:
            raise ValueError(f"harmonised_standards: duplicate id {row_id!r}")

        title = row.get("title")
        if not isinstance(title, str) or not title.strip():
            raise ValueError(
                f"harmonised_standards: entry {row_id!r} has an empty title"
            )

        status = row.get("status")
        if status not in _VALID_STATUSES:
            raise ValueError(
                f"harmonised_standards: entry {row_id!r} has invalid status "
                f"{status!r} (must be one of {sorted(_VALID_STATUSES)})"
            )

        source_url = row.get("source_url")
        if (
            not isinstance(source_url, str)
            or not source_url.strip()
            or not source_url.startswith(("http://", "https://"))
        ):
            raise ValueError(
                f"harmonised_standards: entry {row_id!r} has an invalid "
                f"source_url {source_url!r}"
            )

        articles = row.get("articles_covered")
        if (
            not isinstance(articles, list)
            or not articles
            or not all(isinstance(a, str) and a.strip() for a in articles)
        ):
            raise ValueError(
                f"harmonised_standards: entry {row_id!r} has invalid "
                f"articles_covered {articles!r}"
            )

        # Mandatory per epic CP-4: nothing in this catalogue has been
        # confirmed by a human reviewer yet, so no row may claim otherwise.
        if row.get("needs_founder_review") is not True:
            raise ValueError(
                f"harmonised_standards: entry {row_id!r} must have "
                "needs_founder_review=true"
            )

        catalog[row_id] = HarmonisedStandardEntry(
            id=row_id,
            title=title,
            status=status,
            source_url=source_url,
            articles_covered=tuple(articles),
            needs_founder_review=True,
        )

    return catalog
