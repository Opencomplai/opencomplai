"""SU-21b: the committed deployer pack schema is generated from the model."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
from opencomplai_core.deployer_pack import SCHEMA_ID, build_pack, deployer_pack_schema

_SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "src/opencomplai_core/data/deployer_pack.schema.json"
)


def _committed() -> dict:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def test_core_schema_matches_model() -> None:
    assert _committed() == deployer_pack_schema(), (
        "deployer_pack.schema.json has drifted from DeployerPack: call "
        "opencomplai_core.deployer_pack.write_schemas(core_path, vendored_path) "
        "and commit both files, then run schema_drift_check.py --regen"
    )


def _objects(node, path=""):
    if isinstance(node, dict):
        if node.get("type") == "object":
            yield path, node
        for key, value in node.items():
            yield from _objects(value, f"{path}/{key}")
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from _objects(value, f"{path}/{i}")


def test_schema_declares_id_and_closed_objects() -> None:
    schema = _committed()
    assert schema["$id"] == SCHEMA_ID
    assert schema["$schema"].endswith("2020-12/schema")
    for path, obj in _objects(schema):
        if path.endswith("/content"):
            assert obj.get("additionalProperties") is True
        else:
            assert obj.get("additionalProperties") is False, path


def test_built_pack_validates_against_schema() -> None:
    pack = build_pack(
        {"points": [{"point": "a", "populated": False}]},
        system_id="s",
        issued_on="2026-10-07",
        generator_version="0.0.0",
    )
    jsonschema.validate(pack.model_dump(mode="json"), _committed())
