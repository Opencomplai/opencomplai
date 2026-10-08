"""The omit table drops unset optional fields and nothing else."""

from __future__ import annotations

from typing import Any

import pytest
from opencomplai_core.models import (
    _ARTIFACT_OMIT,
    _MANIFEST_OMIT,
    ScanStatusArtifact,
    SystemManifest,
)
from opencomplai_core.serialization import (
    OMIT_DEFAULT,
    OMIT_EMPTY,
    OMIT_NONE,
    omit_by_table,
)
from pydantic import BaseModel, SerializerFunctionWrapHandler, model_serializer

_TABLE = {"a": OMIT_NONE, "b": OMIT_EMPTY, "c": OMIT_DEFAULT}


class _Throwaway(BaseModel):
    first: str = "x"
    a: str | None = None
    b: list[str] = []
    c: int = 7
    last: str = "z"

    @model_serializer(mode="wrap")
    def _omit(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        return omit_by_table(self, handler(self), _TABLE)


def test_throwaway_row_omits_default_and_keeps_set_value():
    assert list(_Throwaway().model_dump()) == ["first", "last"]
    full = _Throwaway(a="v", b=["i"], c=8).model_dump()
    assert list(full) == ["first", "a", "b", "c", "last"]


def test_zero_and_false_are_not_empty():
    class _M(BaseModel):
        n: int = 5
        f: bool = True

        @model_serializer(mode="wrap")
        def _omit(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
            return omit_by_table(
                self, handler(self), {"n": OMIT_EMPTY, "f": OMIT_EMPTY}
            )

    assert _M(n=0, f=False).model_dump() == {"n": 0, "f": False}


def test_unknown_table_field_fails_loud():
    with pytest.raises(KeyError):
        omit_by_table(_Throwaway(), {}, {"nope": OMIT_NONE})


def test_real_models_use_tables():
    assert {"compliance_targets", "framework_inputs"} <= set(_MANIFEST_OMIT)
    assert {"framework_reports"} <= set(_ARTIFACT_OMIT)
    base = {"system_id": "s", "intended_purpose": "p"}
    assert "compliance_targets" not in SystemManifest(**base).model_dump()
    kept = SystemManifest(**base, compliance_targets=["EU_AI_ACT"]).model_dump()
    assert kept["compliance_targets"] == ["EU_AI_ACT"]
    art = ScanStatusArtifact(
        install_id="i",
        system_id="s",
        commit_ref="c",
        result="pass",
        rationale_hash="h",
        duration_ms=1,
    )
    assert "framework_reports" not in art.model_dump()
