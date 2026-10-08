"""Mapped-only regimes (EU AI Act article -> DORA / EBA citation).

Loads `data/mapped_regimes.json`, fail-loud like `framework_crosswalk`. A row is
a citation, never a verdict: `MappedEntry` has no status field, every row is
`confidence="low"` and `needs_founder_review=true`. DORA and EBA are not
compliance targets and have no probes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_DATA_PATH = Path(__file__).resolve().parent / "data" / "mapped_regimes.json"

MAPPED_REGIMES = ("DORA", "EBA")

_TEXT_FIELDS = ("eu_ai_act_article", "regime", "citation", "topic", "source", "notes")


@dataclass(frozen=True)
class MappedEntry:
    eu_ai_act_article: str
    regime: str
    citation: str
    topic: str
    source: str
    confidence: str
    needs_founder_review: bool
    notes: str


@lru_cache(maxsize=1)
def get_mapped_regimes() -> dict[str, tuple[MappedEntry, ...]]:
    """Return validated rows keyed by regime; raises ValueError on any defect."""
    try:
        raw = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"mapped_regimes: cannot read {_DATA_PATH}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"mapped_regimes: invalid JSON in {_DATA_PATH}: {exc}"
        ) from exc

    rows = raw.get("rows") if isinstance(raw, dict) else None
    if not isinstance(rows, list) or not rows:
        raise ValueError("mapped_regimes: 'rows' is missing or empty")

    out: dict[str, list[MappedEntry]] = {regime: [] for regime in MAPPED_REGIMES}
    seen: set[tuple[str, str, str]] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"mapped_regimes: row is not an object: {row!r}")
        fields: dict[str, str] = {}
        for key in _TEXT_FIELDS:
            value = row.get(key)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"mapped_regimes: row has an empty {key}: {row!r}")
            fields[key] = value
        regime = fields["regime"]
        if regime not in out:
            raise ValueError(
                f"mapped_regimes: unknown regime {regime!r} (expected {MAPPED_REGIMES})"
            )
        ident = (fields["eu_ai_act_article"], fields["citation"])
        if (regime, *ident) in seen:
            raise ValueError(f"mapped_regimes: duplicate row {regime} {ident!r}")
        seen.add((regime, *ident))
        if row.get("confidence") != "low":
            raise ValueError(
                f"mapped_regimes: {ident!r} must have confidence 'low', "
                f"got {row.get('confidence')!r}"
            )
        if row.get("needs_founder_review") is not True:
            raise ValueError(
                f"mapped_regimes: {ident!r} must have needs_founder_review=true"
            )
        out[regime].append(
            MappedEntry(confidence="low", needs_founder_review=True, **fields)
        )
    return {regime: tuple(entries) for regime, entries in out.items()}


def rows_for(regimes: list[str]) -> dict[str, dict[str, list[MappedEntry]]]:
    """article -> regime -> entries, for the requested regimes only."""
    data = get_mapped_regimes()
    result: dict[str, dict[str, list[MappedEntry]]] = {}
    for regime in regimes:
        for entry in data[regime]:
            result.setdefault(entry.eu_ai_act_article, {}).setdefault(
                regime, []
            ).append(entry)
    return result
