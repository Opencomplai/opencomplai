"""SU-10b: the closed `summaries` block."""

from __future__ import annotations

from pathlib import Path

import pytest
from opencomplai_core import summaries
from opencomplai_core.models import ScanResult, ScanStatusArtifact
from opencomplai_core.signing import verify_artifact
from opencomplai_core.summaries import (
    AgentsSummary,
    ArtifactSummaries,
    IncidentItem,
    IncidentsSummary,
    OversightSummary,
    PackIssuance,
    PacksSummary,
    QmsClauses,
    QmsSummary,
)
from pydantic import BaseModel, ValidationError

_ALL = [
    OversightSummary,
    AgentsSummary,
    QmsClauses,
    QmsSummary,
    IncidentItem,
    IncidentsSummary,
    PackIssuance,
    PacksSummary,
    ArtifactSummaries,
]

# Dump of a fixed artifact taken before `summaries` existed.
_PRE_CHANGE_DUMP = (
    '{"install_id":"i","system_id":"s","commit_ref":"abc1234","result":"pass",'
    '"failed_controls":[],"evidence_hashes":[],"rationale_hash":"' + "0" * 64 + '",'
    '"duration_ms":5,"pending_verifications_count":0,"signature":null,'
    '"eval_summary":null,"scan_summary":null,"gap_report":null,'
    '"nist_rmf_report":null,"controls":null}'
)


def test_extra_key_rejected_on_a_populated_model() -> None:
    with pytest.raises(ValidationError):
        OversightSummary.model_validate(
            {"entries": 0, "approvals": 0, "resumes": 0, "roles": 0, "notes": "x"}
        )


@pytest.mark.parametrize("model", _ALL, ids=lambda m: m.__name__)
def test_extra_keys_forbidden(model: type[BaseModel]) -> None:
    assert model.model_config.get("extra") == "forbid"


def test_free_text_field_not_declared() -> None:
    """Every string leaf is pinned by a pattern or an enum (and is bounded)."""
    for model in _ALL:
        schema = model.model_json_schema()
        nodes = [schema, *schema.get("$defs", {}).values()]
        for node in nodes:
            for name, prop in node.get("properties", {}).items():
                for leaf in prop.get("anyOf", [prop]):
                    if leaf.get("type") == "string":
                        assert "pattern" in leaf or "enum" in leaf, (model, name)
                    if leaf.get("type") == "array":
                        assert "maxItems" in leaf, (model, name)


def test_qms_clauses_are_exactly_a_to_m() -> None:
    assert list(QmsClauses.model_fields) == list("abcdefghijklm")
    assert all(f.is_required() for f in QmsClauses.model_fields.values())
    with pytest.raises(ValidationError):
        QmsClauses(**dict.fromkeys("abcdefghijklmn", "present"))  # type: ignore[arg-type]


def test_module_exposes_only_the_contract_models() -> None:
    assert {
        n
        for n, v in vars(summaries).items()
        if isinstance(v, type)
        and issubclass(v, BaseModel)
        and v.__module__ == summaries.__name__
        and not n.startswith("_")
    } == {m.__name__ for m in _ALL}


def test_artifact_without_summaries_serialises_identically() -> None:
    artifact = ScanStatusArtifact(
        install_id="i",
        system_id="s",
        commit_ref="abc1234",
        result=ScanResult.PASS,
        rationale_hash="0" * 64,
        duration_ms=5,
    )
    assert artifact.model_dump_json() == _PRE_CHANGE_DUMP
    fixture = Path(__file__).parent / "fixtures" / "signed_artifact_v071"
    stored = (fixture / "artifact.json").read_text(encoding="utf-8")
    parsed = ScanStatusArtifact.model_validate_json(stored)
    assert parsed.model_dump_json(indent=2) == stored.rstrip("\n")
    assert verify_artifact(parsed, fixture / "signing.pub") is True


def test_empty_summaries_members_are_omitted() -> None:
    assert ArtifactSummaries().model_dump_json() == "{}"
