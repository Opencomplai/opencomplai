"""NIST AI RMF 1.0 core subcategory taxonomy (Govern/Map/Measure/Manage).

Loads and validates `data/nist_ai_rmf_subcategories.json`, mirroring
`harmonised_standards.get_catalog()`'s fail-loud convention: a malformed or
missing data file raises `ValueError` rather than silently degrading to an
empty or partial taxonomy.

This is TAXONOMY data only (the RMF 1.0 subcategory catalogue) -- it carries
no verdict and is not itself compliance-facing content in the way the
crosswalk is. `nist_rmf_report.py` is what re-projects existing
EU-AI-Act-native evidence onto this taxonomy via `framework_crosswalk.py`.
See the data file's `_meta` block for the research date and the
pending-NIST-revision caveat (GOVERN 3 / MEASURE 2.12 in particular).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from opencomplai_core.models import RmfFunction

_DATA_PATH = Path(__file__).resolve().parent / "data" / "nist_ai_rmf_subcategories.json"

_VALID_FUNCTIONS = {f.value for f in RmfFunction}


@dataclass(frozen=True)
class RmfSubcategoryEntry:
    id: str
    function: str
    category: str
    category_title: str
    outcome: str


@lru_cache(maxsize=1)
def get_subcategories() -> dict[str, RmfSubcategoryEntry]:
    """Return the validated RMF subcategory taxonomy, keyed by subcategory id.

    Fails loud (raises ValueError) on a missing file, invalid JSON, or any
    row missing/mis-typing a required field, or whose `id`/`category`/
    `function` are mutually inconsistent (e.g. id "GOVERN 1.1" under category
    "GOVERN 2") -- never returns a silently empty or malformed taxonomy.
    """
    try:
        raw = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(
            f"nist_ai_rmf_subcategories: cannot read {_DATA_PATH}: {exc}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"nist_ai_rmf_subcategories: invalid JSON in {_DATA_PATH}: {exc}"
        ) from exc

    rows = raw.get("subcategories") if isinstance(raw, dict) else None
    if not isinstance(rows, list) or not rows:
        raise ValueError(
            "nist_ai_rmf_subcategories: 'subcategories' is missing or empty"
        )

    taxonomy: dict[str, RmfSubcategoryEntry] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(
                f"nist_ai_rmf_subcategories: row is not an object: {row!r}"
            )

        subcat_id = row.get("id")
        if not isinstance(subcat_id, str) or not subcat_id.strip():
            raise ValueError(f"nist_ai_rmf_subcategories: malformed id {subcat_id!r}")
        if subcat_id in taxonomy:
            raise ValueError(f"nist_ai_rmf_subcategories: duplicate id {subcat_id!r}")

        function = row.get("function")
        if function not in _VALID_FUNCTIONS:
            raise ValueError(
                f"nist_ai_rmf_subcategories: entry {subcat_id!r} has invalid "
                f"function {function!r} (must be one of {sorted(_VALID_FUNCTIONS)})"
            )
        if not subcat_id.startswith(f"{function} "):
            raise ValueError(
                f"nist_ai_rmf_subcategories: entry {subcat_id!r} does not start "
                f"with its own function {function!r}"
            )

        category = row.get("category")
        if not isinstance(category, str) or not category.strip():
            raise ValueError(
                f"nist_ai_rmf_subcategories: entry {subcat_id!r} has an empty category"
            )
        # "GOVERN 1.1" -> major number "1" -> expected category "GOVERN 1".
        number = subcat_id[len(function) + 1 :]
        major = number.split(".", 1)[0]
        expected_category = f"{function} {major}"
        if category != expected_category:
            raise ValueError(
                f"nist_ai_rmf_subcategories: entry {subcat_id!r} has category "
                f"{category!r}, expected {expected_category!r}"
            )

        category_title = row.get("category_title")
        if not isinstance(category_title, str) or not category_title.strip():
            raise ValueError(
                f"nist_ai_rmf_subcategories: entry {subcat_id!r} has an empty category_title"
            )

        outcome = row.get("outcome")
        if not isinstance(outcome, str) or not outcome.strip():
            raise ValueError(
                f"nist_ai_rmf_subcategories: entry {subcat_id!r} has an empty outcome"
            )

        taxonomy[subcat_id] = RmfSubcategoryEntry(
            id=subcat_id,
            function=function,
            category=category,
            category_title=category_title,
            outcome=outcome,
        )

    return taxonomy
