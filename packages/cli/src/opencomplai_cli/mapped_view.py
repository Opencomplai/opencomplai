"""`gaps --map-to` view over the mapped-only regimes. Pure functions: nothing
here receives or touches a GapStatus."""

from __future__ import annotations

from dataclasses import asdict

from opencomplai_core.mapped_regimes import MAPPED_REGIMES, rows_for
from rich.table import Table


def parse_map_to(values: list[str] | None) -> list[str]:
    """Case-insensitive, de-duplicated, order-preserving; unknown raises ValueError."""
    regimes: list[str] = []
    for value in values or []:
        regime = value.strip().upper()
        if regime not in MAPPED_REGIMES:
            raise ValueError(
                f"unknown regime {value!r} for --map-to "
                f"(expected one of {', '.join(MAPPED_REGIMES)})"
            )
        if regime not in regimes:
            regimes.append(regime)
    return regimes


def add_mapped_columns(table: Table, regimes: list[str]) -> None:
    for regime in regimes:
        table.add_column(f"{regime} (mapped)", style="dim")


def mapped_cells(article: str, regimes: list[str]) -> list[str]:
    by_regime = rows_for(regimes).get(article, {})
    return [
        "; ".join(e.citation for e in by_regime.get(regime, [])) or "—"
        for regime in regimes
    ]


def mapped_payload(regimes: list[str]) -> dict:
    """regime -> article -> rows, each row carrying its review flag."""
    payload: dict[str, dict[str, list[dict]]] = {}
    for article, by_regime in rows_for(regimes).items():
        for regime, entries in by_regime.items():
            payload.setdefault(regime, {})[article] = [asdict(e) for e in entries]
    return payload
