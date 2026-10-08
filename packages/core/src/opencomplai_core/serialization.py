"""Table-driven omission of optional fields from serialised models.

Pydantic keeps one ``model_serializer`` per model, so each model declares a
``{field: rule}`` table and calls :func:`omit_by_table` from that serializer.
Adding an optional field that must vanish from legacy bytes is one table row.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

OmitRule = Literal["none", "empty", "default"]

OMIT_NONE: OmitRule = "none"  # drop when the value is None
OMIT_EMPTY: OmitRule = "empty"  # drop when None or an empty str/container
OMIT_DEFAULT: OmitRule = "default"  # drop when equal to the field default


def _is_empty(value: Any) -> bool:
    # Never treat 0 or False as empty: later fields may be ints or bools.
    if value is None:
        return True
    return isinstance(value, (str, bytes, list, tuple, dict, set, frozenset)) and (
        len(value) == 0
    )


def omit_by_table(
    model: BaseModel, data: dict[str, Any], table: dict[str, OmitRule]
) -> dict[str, Any]:
    """Pop the fields of ``data`` that the table says are unset.

    ``dict.pop`` only, so the key order of everything else is untouched.
    A field name missing from the model raises ``KeyError`` (typo'd row).
    """
    fields = type(model).model_fields
    for name, rule in table.items():
        field = fields[name]
        value = getattr(model, name)
        if (
            (rule == OMIT_NONE and value is None)
            or (rule == OMIT_EMPTY and _is_empty(value))
            or (
                rule == OMIT_DEFAULT
                and value == field.get_default(call_default_factory=True)
            )
        ):
            data.pop(name, None)
    return data
