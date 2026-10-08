"""Who carries which obligation in an agent deployment (draft reference data).

Loads and validates `data/agent_responsibility.json`, mirroring
`harmonised_standards.get_catalog()`'s fail-loud convention: a missing or
malformed file raises `ValueError` rather than degrading to an empty result.

Every row is `needs_founder_review=true` and `confidence="low"`: the wording is
unverified and a lawyer is to confirm it. `source` is a citation label only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, fields
from functools import lru_cache
from pathlib import Path

_DATA_PATH = Path(__file__).resolve().parent / "data" / "agent_responsibility.json"

_PARTIES = {"customer", "upstream_model_provider", "shared"}
_CONFIDENCES = {"low", "medium"}
_TEXT_FIELDS = ("id", "duty", "regime_ref", "summary", "source")


@dataclass(frozen=True)
class ResponsibilityRow:
    id: str
    party: str
    duty: str
    regime_ref: str
    summary: str
    source: str
    confidence: str
    needs_founder_review: bool


def _fail(msg: str) -> ValueError:
    return ValueError(f"agent_responsibility: {msg}")


@lru_cache(maxsize=1)
def get_responsibilities() -> tuple[ResponsibilityRow, ...]:
    """Return the validated rows in file order; raise ValueError if malformed."""
    try:
        raw = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    except OSError as exc:
        raise _fail(f"cannot read {_DATA_PATH}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise _fail(f"invalid JSON in {_DATA_PATH}: {exc}") from exc

    rows = raw.get("rows") if isinstance(raw, dict) else None
    if not isinstance(rows, list) or not rows:
        raise _fail("'rows' is missing or empty")

    out: list[ResponsibilityRow] = []
    seen: set[object] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise _fail(f"row is not an object: {row!r}")
        rid = row.get("id")
        for name in _TEXT_FIELDS:
            value = row.get(name)
            if not isinstance(value, str) or not value.strip():
                raise _fail(f"row {rid!r} has an empty or missing {name!r}")
        if rid in seen:
            raise _fail(f"duplicate id {rid!r}")
        seen.add(rid)
        if row.get("party") not in _PARTIES:
            raise _fail(f"row {rid!r} has a bad party {row.get('party')!r}")
        if row.get("confidence") not in _CONFIDENCES:
            raise _fail(f"row {rid!r} has a bad confidence {row.get('confidence')!r}")
        if not isinstance(row.get("needs_founder_review"), bool):
            raise _fail(f"row {rid!r} needs_founder_review is missing or not a bool")
        out.append(
            ResponsibilityRow(
                **{f.name: row[f.name] for f in fields(ResponsibilityRow)}
            )
        )
    return tuple(out)
